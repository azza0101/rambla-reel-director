import pytest
from tests.unit.test_cut_pass_routes import tmp_path


def snapshot():
    return dict(schema='rmbl-resolve-cut-source-1',supported=True,timeline_id='t',mark_in=108060,mark_out=108180,
        fps='30000/1001',width=1080,height=1920,tracks=[
        dict(kind='video',index=1,name='V1',enabled=True,clips=[dict(id='v',path='video.mov',source_fps='30000/1001',
            timeline_in=0,timeline_out=120,source_in=600,source_out=720,enabled=True,properties={})]),
        dict(kind='audio',index=2,name='voice',enabled=True,subtype='mono',clips=[dict(id='a',path='voice.wav',source_fps='30000/1001',
            timeline_in=20,timeline_out=100,source_in=200,source_out=280,enabled=True,properties={})])])


def test_remap_keeps_gaps_tracks_and_source_offsets_at_fractional_fps():
    from backend.app.resolve_cut_source import remap_source_cut
    cut=dict(fps='30000/1001',source_duration_frames=120,duration_frames=70,segments=[
        dict(source_in_frame=10,source_out_frame=50,edited_in_frame=0,edited_out_frame=40),
        dict(source_in_frame=90,source_out_frame=120,edited_in_frame=40,edited_out_frame=70)])
    rows=remap_source_cut(snapshot(),cut)
    video=[r for r in rows if r['kind']=='video'];audio=[r for r in rows if r['kind']=='audio']
    assert [(r['record_in'],r['record_out'],r['source_in']) for r in video]==[(0,40,610),(40,70,690)]
    assert [(r['record_in'],r['record_out'],r['source_in']) for r in audio]==[(10,40,200),(40,50,270)]
    assert all(r['track_index']==2 for r in audio)
    with pytest.raises(ValueError):remap_source_cut({**snapshot(),'supported':False},cut)


def test_snapshot_module_imports_without_server_dependencies():
    import subprocess,sys
    result=subprocess.run([sys.executable,'-S','-c',
        'from backend.app.resolve_cut_source import frame_rate; assert frame_rate("30")==30'],
        capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_fractional_cut_duration_does_not_invent_a_last_frame():
    from backend.app.cut_pass import build_cut_plan
    from fractions import Fraction
    raw={'timing_basis':'cloud_asr_word_timestamps','segments':[{'words':[{'word':'ciao','start':.1,'end':1}]}]}
    rate=Fraction(30000,1001)
    plan=build_cut_plan(raw,duration=120/float(rate),fps=float(rate),signature='s',groups=[])
    assert plan['source_duration_frames']==120


def test_capture_rejects_retimed_or_nested_clips_before_any_write(tmp_path):
    from backend.app.resolve_cut_source import capture_cut_source, verify_snapshot_files
    path=tmp_path/'original.mov';path.write_bytes(b'original')
    class Media:
        def GetClipProperty(self,key):return {'File Path':str(path),'FPS':'29.97'}[key]
        def GetUniqueId(self):return 'media'
    class Item:
        speed=100
        def GetStart(self,*a):return 108000
        def GetEnd(self,*a):return 108180
        def GetMediaPoolItem(self):return Media()
        def GetUniqueId(self):return 'clip'
        def GetSourceStartFrame(self):return 0
        def GetSourceEndFrame(self):return 179
        def GetSpeed(self):return {'Percentage':self.speed}
        def GetFusionCompCount(self):return 0
        def GetClipEnabled(self):return True
        def GetProperty(self):return {}
    item=Item()
    class Timeline:
        def GetUniqueId(self):return 'timeline'
        def GetSetting(self,key):return {'timelineFrameRate':'29.97','timelineResolutionWidth':'1080','timelineResolutionHeight':'1920'}[key]
        def GetTrackCount(self,kind):return 1 if kind=='video' else 0
        def GetTrackName(self,*a):return 'V1'
        def GetIsTrackEnabled(self,*a):return True
        def GetItemListInTrack(self,*a):return [item]
        def GetMarkers(self):return {}
    result=capture_cut_source(Timeline(),108060,108179)
    assert result['supported'] and result['fps']=='30000/1001'
    assert result['tracks'][0]['clips'][0]['source_in']==60
    verify_snapshot_files(result)
    path.write_bytes(b'changed')
    with pytest.raises(ValueError):verify_snapshot_files(result)
    item.speed=120
    assert not capture_cut_source(Timeline(),108060,108179)['supported']
