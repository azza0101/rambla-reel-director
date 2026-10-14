from pathlib import Path
from backend.app.cut_alignment import refine_cut_timing
from backend.app.cut_pass import build_cut_plan
from tests.unit.test_cut_pass import transcript


def test_refinement_extends_clipped_last_word_and_updates_following_discard():
    raw=transcript([(2,3,'Cura Viaggi'),(3,3.5,'e oggi')])
    plan=build_cut_plan(raw,duration=5,fps=30,signature='s',groups=[])
    plan['groups']=[{'takes':[[0,1],[0,1]],'selected_take':0}]
    # Window starts at 1; short-window transcription puts Viaggi through 3.3.
    fresh=transcript([(1,2.3,'Cura Viaggi'),(2.3,2.8,'e oggi')])
    result,warnings=refine_cut_timing(raw,plan,Path('source'),Path('.'),
        runner=lambda *a,**kw:None,transcriber=lambda *a:fresh)
    assert not warnings
    assert result['segments'][0]['words'][-1]['end']==3.3
    assert result['segments'][1]['words'][0]['start']==3.3
    assert raw['segments'][0]['words'][-1]['end']==3


def test_uncertain_short_transcription_preserves_original_words_and_times():
    raw=transcript([(2,3,'Cura Viaggi')]);plan=build_cut_plan(raw,duration=5,fps=30,signature='s',groups=[])
    plan['groups']=[{'takes':[[0,1],[0,1]],'selected_take':0}]
    result,warnings=refine_cut_timing(raw,plan,Path('source'),Path('.'),runner=lambda *a,**kw:None,
        transcriber=lambda *a:transcript([(1,2,'qualcosa diversa')]))
    assert warnings
    assert result['segments']==raw['segments']


def test_optional_refinement_quota_does_not_discard_measured_transcript():
    raw=transcript([(2,3,'Cura Viaggi')]);plan=build_cut_plan(raw,duration=5,fps=30,signature='s',groups=[])
    plan['groups']=[{'takes':[[0,1],[0,1]],'selected_take':0}]
    calls=[]
    def limited(*args):
        calls.append(args)
        raise RuntimeError('Groq ASR failed (429): Rate limit reached')
    result,warnings=refine_cut_timing(raw,plan,Path('source'),Path('.'),runner=lambda *a,**kw:None,transcriber=limited)
    assert result['segments']==raw['segments']
    assert result['timing_basis']=='cloud_asr_word_timestamps'
    assert len(calls)==1
    assert 'timestamp già misurati' in warnings[0]
