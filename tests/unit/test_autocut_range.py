import pytest
from tests.unit.test_cut_pass import transcript
from backend.app.cut_pass import build_cut_plan,words_of

def test_selected_range_limits_breathing_after_manual_rebuild():
    raw=transcript([(10,10.5,'prima parola'),(11,11.5,'ultima parola')])
    raw['analysis_range_frames']={'in_frame':300,'out_frame':345,'fps':'30'}
    plan=build_cut_plan(raw,duration=100,fps=30,signature='s',groups=[],breathing=.5)
    assert plan['segments'][0]['source_in_frame']==300
    assert plan['segments'][-1]['source_out_frame']==345
    assert plan['analysis_range_frames']==raw['analysis_range_frames']

def test_shifted_asr_preserves_original_absolute_times():
    from backend.app.autocut_range import offset_transcript
    raw=transcript([(0,1,'ciao mondo')])
    ranged=offset_transcript(raw,{'in_frame':300,'out_frame':360,'fps':'30'})
    assert words_of(ranged)[0]['start']==10
    assert words_of(ranged)[-1]['end']==11
    assert ranged['analysis_range_frames']['in_frame']==300
    assert words_of(raw)[0]['start']==0


def test_original_is_parked_after_cut_disabled_with_full_decoded_duration(monkeypatch):
    from types import SimpleNamespace as Obj
    import backend.app.resolve_native_cut as native
    calls=[];enabled=[];markers=[];marks=[]
    clips=[Obj(SetClipEnabled=lambda value:enabled.append(value) or True,SetProperty=lambda props:True) for _ in range(2)]
    def append(pool,timeline,source,row,base,**kwargs):calls.append(row);return clips,0
    monkeypatch.setattr(native,'append_exact_segment',append)
    timeline=Obj(SetClipsLinked=lambda *a:True,GetMarkers=lambda:{0:{'name':'existing'}},
        AddMarker=lambda *a:markers.append(a) or True,SetMarkInOut=lambda *a:marks.append(a) or True)
    result=native.park_original(None,timeline,object(),{'fps':'30','duration_frames':300},
        {'source_duration_frames':11744,'properties':{}},108000,0)
    assert calls[0]=={'source_in_frame':0,'source_out_frame':11744,'edited_in_frame':360,'edited_out_frame':12104}
    assert enabled==[False,False]
    assert marks==[(0,299)]
    assert markers[0][0]!=0 and markers[1][0]==360
    assert result['original_start_frame']==108360


def test_ntsc_range_is_normalized_to_source_grid():
    from backend.app.autocut_range import validate_range
    assert validate_range({'in_frame':30,'out_frame':300,'fps':'29.97'},100,30000/1001)['fps']=='30000/1001'


def test_audio_extraction_requests_only_the_selected_duration():
    from pathlib import Path
    from backend.app.autocut_range import transcribe_range
    calls=[]
    result=transcribe_range(Path('source.mov'),Path('work'),{'in_frame':300,'out_frame':360,'fps':'30'},
        lambda source,folder:transcript([(0,1,'ciao mondo')]),runner=lambda args,**kw:calls.append(args))
    assert calls[0][calls[0].index('-ss')+1]=='10.0'
    assert calls[0][calls[0].index('-t')+1]=='2.0'
    assert words_of(result)[0]['start']==10
