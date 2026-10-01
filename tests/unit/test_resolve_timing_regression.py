from types import SimpleNamespace

from backend.app.cloud_analyze_cli import _normalize_groq
from backend.app.resolve_textplus_timeline import generated_fusion_items
import pytest


def test_subtitle_seconds_are_quantized_like_titles_at_actual_timeline_fps():
    from backend.app.resolve_native_subtitles import normalize_subtitle_rows
    row = normalize_subtitle_rows([{'text':'before highlight','start_seconds':105.17,'end_seconds':105.55}],fps=30)[0]
    assert row['end_frame'] == 3166
    assert row['end_seconds'] == 3166 / 30


def test_timing_snapshot_expires_when_selection_changes(monkeypatch):
    from pathlib import Path
    import backend.app.transcript_intents as module
    from backend.app.editorial_import import digest
    from backend.app.transcript_intents import _signature, load_phrase_intents, planning_chunks_for_coverage
    chunks = [{'id':'one', 'text':'hello', 'start':0,'end':1,
               'words':[{'text':'hello','start':0,'end':1}]}]
    state = {'transcript_signature':_signature(chunks), 'phrases':{'one':{'coverage':False,'coverage_word_indices':[]}}}
    snapshot = {
        'transcript_signature':_signature(chunks), 'selection_digest':digest(state['phrases']),
        'chunks':[{'id':'reviewed-beat'}]}
    monkeypatch.setattr(module, 'normalized_chunks', lambda run: chunks)
    monkeypatch.setattr(module, 'load_phrase_intents', lambda run: state)
    monkeypatch.setattr(module, 'read', lambda path: snapshot)
    monkeypatch.setattr(Path, 'is_file', lambda path: path.name == 'coverage-timing-snapshot.json')
    assert planning_chunks_for_coverage(Path('.')) == [{'id':'reviewed-beat'}]
    state['phrases']['one'].update(coverage=True, coverage_word_indices=[0])
    assert planning_chunks_for_coverage(Path('.'))[0]['id'] == 'one'


def test_zero_duration_recognized_words_are_not_dropped():
    result = _normalize_groq({'words': [{'word':'last','start':1.0,'end':1.0}]})
    word = result['segments'][0]['words'][0]
    assert word['text'] == 'last'
    assert word['end'] - word['start'] >= .039


def test_retiming_preserves_reviewed_text_ids_and_allocates_a_visible_frame():
    from backend.app.transcript_retiming import retime_chunks
    original = [{'id':'selected', 'text':'One two.', 'start':0,'end':2,
                 'words':[{'text':'One','start':0,'end':1},{'text':'two.','start':1,'end':2}]}]
    measured = {'segments':[{'words':[{'text':'one','start':.2,'end':.5},
                                     {'text':'two','start':.2,'end':.21}]}]}
    result, unresolved = retime_chunks(original, measured)
    assert not unresolved
    assert result[0]['id'] == 'selected' and result[0]['text'] == 'One two.'
    a,b=result[0]['words']
    assert a['end'] <= b['start'] and b['end']-b['start'] >= .039
    assert original[0]['words'][0]['start'] == 0


@pytest.mark.parametrize('source_fps', [25, 29.97, 60])
def test_broll_source_frames_use_media_fps_without_changing_record_duration(source_fps):
    from backend.app.resolve_textplus_timeline import append_broll_clips
    received = []
    media = SimpleNamespace(GetClipProperty=lambda name: source_fps)
    item = SimpleNamespace(GetStart=lambda: 108100, GetEnd=lambda: 108211)
    def append(rows):
        received.extend(rows)
        return [item]
    pool = SimpleNamespace(ImportMedia=lambda paths: [media], AppendToTimeline=append)
    timeline = SimpleNamespace(GetTrackCount=lambda kind: 2)
    append_broll_clips(pool, timeline, [{'media_path':'video.mp4', 'asset_id':'clip',
        'track_index':2, 'record_start_frame':100, 'record_end_frame':211,
        'source_start_frame':30, 'source_end_frame':141}], base_frame=108000, fps=30)
    assert received[0]['startFrame'] == pytest.approx(source_fps)
    assert received[0]['endFrame'] == pytest.approx(141*source_fps/30)
    assert received[0]['recordFrame'] == 108100


def test_top_level_asr_words_preserve_actual_speech_timing_and_tail():
    result = _normalize_groq({
        'duration': 10,
        'segments': [{'start': 0, 'end': 9, 'text': 'one two'}],
        'words': [{'word': 'one', 'start': 1.2, 'end': 1.4},
                  {'word': 'two', 'start': 7.1, 'end': 7.3},
                  {'word': 'last', 'start': 9.1, 'end': 9.5}],
    })
    words = [w for s in result['segments'] for w in s['words']]
    assert [(w['text'], w['start'], w['end']) for w in words] == [
        ('one', 1.2, 1.4), ('two', 7.1, 7.3), ('last', 9.1, 9.5)]
    assert result['source_duration_seconds'] == 10


def test_fusion_split_descendants_are_included_in_cleanup():
    def item(identity):
        return SimpleNamespace(GetUniqueId=lambda: identity, GetFusionCompCount=lambda: 1)
    original, inserted, split = item('original'), item('inserted'), item('split-new-id')
    timeline = SimpleNamespace(GetTrackCount=lambda kind: 1 if kind == 'video' else 0,
                               GetItemListInTrack=lambda kind, track: [original, inserted, split])
    assert generated_fusion_items(timeline, {'original'}) == [inserted, split]
