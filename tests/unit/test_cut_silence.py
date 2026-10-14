from backend.app.cut_pass import build_cut_plan,clean_transcript
from backend.app.cut_silence import trim_silence_ranges
from tests.unit.test_cut_pass import transcript


def test_strong_removes_shorter_measured_pauses_without_changing_text():
    raw=transcript([(0,1,'condividere.'),(1,2,'E questo'),(2,3,'poi')])
    args=dict(duration=3.1,fps=30,signature='s',groups=[],silence_intervals=[[.7,1.2],[2.1,2.4]])
    normal=build_cut_plan(raw,**args)
    soft=build_cut_plan(raw,**args,tight_pauses=True,pause_mode='soft')
    strong=build_cut_plan(raw,**args,tight_pauses=True,pause_mode='strong')
    assert strong['duration_frames']<soft['duration_frames']<normal['duration_frames']
    assert clean_transcript(raw,strong)['text']==clean_transcript(raw,soft)['text']==clean_transcript(raw,normal)['text']
    assert len([w for s in clean_transcript(raw,strong)['segments'] for w in s['words']])==4
    reverted=build_cut_plan(raw,**args,tight_pauses=False,pause_mode='strong')
    assert reverted['segments']==normal['segments']


def test_silence_cut_leaves_margins_on_both_sides():
    assert trim_silence_ranges([[0,100,1]],[[.5,.9]],100,'strong')==[[0,57,1],[84,100,1]]


def test_silence_detection_cannot_clip_a_brief_final_word():
    words=[{'text':'via','start':77.76,'end':78.02}]
    pieces=trim_silence_ranges([[2300,2390,1]],[[77.842812,79.124354]],30,'strong',words)
    assert pieces[0][1]>=2341  # end of via at 78.02, with safety margin


def test_medium_sits_between_soft_and_strong():
    raw=transcript([(0,1,'frase'),(1.5,2.5,'successiva')])
    durations=[build_cut_plan(raw,duration=3,fps=30,signature='s',groups=[],tight_pauses=True,pause_mode=mode,silence_intervals=[[.8,1.5]])['duration_frames'] for mode in ['soft','medium','strong']]
    assert durations[0]>=durations[1]>=durations[2]
