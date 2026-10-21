import pytest
from types import SimpleNamespace as Obj

def fake(marks):
    media=Obj(GetClipProperty=lambda key:'original.mov')
    clip=Obj(GetLeftOffset=lambda:0,GetRightOffset=lambda:0,GetStart=lambda:108000,GetEnd=lambda:119744,GetMediaPoolItem=lambda:media)
    timeline=Obj(GetTrackCount=lambda kind:1,GetItemListInTrack=lambda *a:[clip],GetMarkInOut=lambda:marks,
        GetStartFrame=lambda:108000,GetSetting=lambda key:30,GetName=lambda:'Timeline',GetUniqueId=lambda:'t1')
    return Obj(GetProjectManager=lambda:Obj(GetCurrentProject=lambda:Obj(GetCurrentTimeline=lambda:timeline,GetName=lambda:'TEST')))


def test_current_source_reads_zero_in_and_inclusive_out_without_mutations():
    from backend.app.autocut_source import capture_source
    result=capture_source(fake({'video':{'in':0,'out':10476},'audio':{'in':0,'out':10476}}))
    assert result['source_range']=={'in_frame':0,'out_frame':10477,'fps':'30'}
    assert result['path']=='original.mov'


def test_current_source_refuses_different_audio_video_marks():
    from backend.app.autocut_source import capture_source
    with pytest.raises(ValueError,match='diversi'):
        capture_source(fake({'video':{'in':0,'out':10476},'audio':{'in':1,'out':10476}}))


def test_analyze_refreshes_current_source_before_starting():
    from backend.app.autocut_ui import AFTER
    assert "await importCurrentTimeline()" in AFTER
    assert "await cutAction('analyze')" in AFTER
    assert 'window.rmblAutoCut.snapshot()' not in AFTER
