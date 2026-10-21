import pytest
from tests.unit.test_cut_pass_routes import tmp_path
from tests.unit.test_cut_pass import transcript


def test_long_word_is_flagged_without_trimming_or_rewriting():
    from backend.app.cut_timing_guard import timing_anomalies
    raw=transcript([(10,23.4,'garanzia.')])
    result=timing_anomalies(raw)
    assert len(result)==1 and result[0]['index']==0
    assert result[0]['duration']==pytest.approx(13.4)
    assert raw['segments'][0]['words'][0]['end']==23.4


def test_discarded_anomaly_does_not_block_export():
    from backend.app.cut_timing_guard import assert_timing_quality
    raw=transcript([(0,13,'errore'),(14,15,'buono')])
    assert_timing_quality(raw,{'removed_word_indices':[0],'fps':'30',
        'segments':[{'source_in_frame':420,'source_out_frame':450}]})


def test_retained_anomaly_blocks_cut_and_caption_export():
    from backend.app.cut_timing_guard import assert_timing_quality
    raw=transcript([(10,23.4,'garanzia.')])
    with pytest.raises(ValueError,match='Timestamp ASR anomalo'):
        assert_timing_quality(raw,{'removed_word_indices':[],'fps':'30',
            'segments':[{'source_in_frame':300,'source_out_frame':700}]})


def test_rescan_splice_recovers_missing_words_and_maps_manual_indices():
    from backend.app.cut_timing_guard import splice_window,remap_manual_indices
    raw=transcript([(0,1,'prima'),(2,15,'parola'),(16,17,'dopo')])
    repaired,mapping=splice_window(raw,2,16,[{'start':2,'end':3,'text':'parola'},{'start':10,'end':11,'text':'ripetizione'}])
    assert [w['text'] for s in repaired['segments'] for w in s['words']]==['prima','parola','ripetizione','dopo']
    assert remap_manual_indices([2],mapping)==[3]
    assert mapping[1]==1


def test_manual_selection_never_silently_disappears():
    from backend.app.cut_timing_guard import remap_manual_indices
    with pytest.raises(ValueError,match='manuale'):
        remap_manual_indices([3],{0:0})


def test_repeated_manual_word_maps_by_time_not_first_text_occurrence():
    from backend.app.cut_timing_guard import splice_window
    raw=transcript([(10,10.5,'ma'),(11,11.5,'bene')])
    _,mapping=splice_window(raw,9,12,[{'start':9,'end':9.3,'text':'ma'},
        {'start':10,'end':10.5,'text':'ma'},{'start':11,'end':11.5,'text':'bene'}])
    assert mapping[0]==1


def test_caption_export_rejects_unresolved_kept_anomaly():
    from backend.app.autocut_subtitles import subtitle_rows
    from backend.app.cut_pass import build_cut_plan
    raw=transcript([(10,23.4,'garanzia.')])
    plan=build_cut_plan(raw,duration=24,fps=30,signature='s',groups=[])
    with pytest.raises(ValueError,match='Timestamp ASR anomalo'):
        subtitle_rows(raw,plan)


def test_alignment_cannot_replace_good_timing_with_giant_span():
    from backend.app.cut_alignment import refine_cut_timing
    from backend.app.cut_pass import build_cut_plan
    from pathlib import Path
    raw=transcript([(2,2.5,'garanzia.'),(16,16.5,'dopo')])
    plan=build_cut_plan(raw,duration=18,fps=30,signature='s',groups=[])
    plan['groups']=[{'takes':[[0,1]],'selected_take':0}]
    measured=transcript([(1,14.4,'garanzia.'),(15,15.5,'dopo')])
    result,warnings=refine_cut_timing(raw,plan,Path('source'),Path('.'),
        runner=lambda *a,**kw:None,transcriber=lambda *a:measured)
    assert result['segments']==raw['segments']
    assert any('anomalo' in w for w in warnings)


def test_automatic_repair_uses_short_cached_windows_before_editorial(tmp_path,monkeypatch):
    from backend.app.cut_timing_guard import repair_anomalies,assert_timing_quality
    import subprocess
    raw=transcript([(1,14,'garanzia.')])
    source=tmp_path/'source.mp4';source.write_bytes(b'identity')
    monkeypatch.setattr(subprocess,'run',lambda *a,**k:None)
    calls=[];messages=[]
    def recognize(audio,cache):
        calls.append(str(cache))
        return transcript([(.1,.5,'parola')])
    repaired=repair_anomalies(raw,source,tmp_path,recognize,messages.append)
    assert_timing_quality(repaired)
    assert len(calls)==3 and messages
    repair_anomalies(raw,source,tmp_path,recognize)
    assert len(calls)==3


def test_failed_repair_cannot_overwrite_original_transcript(tmp_path,monkeypatch):
    import subprocess
    from backend.app.cut_timing_guard import repair_anomalies
    raw=transcript([(1,14,'garanzia.')])
    source=tmp_path/'source.mp4';source.write_bytes(b'identity')
    monkeypatch.setattr(subprocess,'run',lambda *a,**k:None)
    def fail(*args):raise RuntimeError('quota')
    with pytest.raises(RuntimeError,match='quota'):repair_anomalies(raw,source,tmp_path,fail)
    assert raw['segments'][0]['words'][0]['end']==14


def test_repair_window_does_not_erase_word_crossing_its_end():
    from backend.app.cut_timing_guard import splice_window,remap_manual_indices
    from backend.app.cut_pass import words_of
    raw=transcript([(298,299,'non'),(300.96,301.08,'è'),(301.1,301.6,'soltanto')])
    repaired,mapping=splice_window(raw,297,301,[{'start':300.5,'end':301,'text':'non'}])
    assert [w['text'] for w in words_of(repaired)]==['non','è','soltanto']
    assert remap_manual_indices([1],mapping)==[1]


def test_quiet_audio_is_context_only_and_never_a_discard(tmp_path):
    import array,subprocess
    from backend.app.cut_audio_context import annotate_relative_volume
    raw=transcript([(0,1,'forte'),(1,2,'piano')])
    source=tmp_path/'audio.wav';source.write_bytes(b'exists')
    pcm=array.array('h',[12000]*16000+[1000]*16000).tobytes()
    from types import SimpleNamespace
    result=annotate_relative_volume(raw,source,runner=lambda *a,**k:SimpleNamespace(stdout=pcm))
    assert result['segments'][1]['words'][0]['relative_speech_db'] < -15
    assert [w['text'] for s in result['segments'] for w in s['words']]==['forte','piano']
    assert 'removed_word_indices' not in result
    assert 'relative_speech_db' not in raw['segments'][0]['words'][0]
