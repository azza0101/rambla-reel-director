import pytest
from types import SimpleNamespace as Obj


def timeline(start=100):
    clip=Obj(GetUniqueId=lambda:'clip',GetStart=lambda:start,GetEnd=lambda:start+20,
        GetLeftOffset=lambda:10,GetRightOffset=lambda:50,GetClipEnabled=lambda:True,GetProperty=lambda:{'ZoomX':1})
    return Obj(GetUniqueId=lambda:'timeline',GetTrackCount=lambda kind:1 if kind=='video' else 0,
        GetItemListInTrack=lambda *a:[clip],GetMarkers=lambda:{},GetSetting=lambda:{'timelineFrameRate':30})


def test_snapshot_signature_detects_changed_clip_position():
    from backend.app.autocut_reapply import timeline_snapshot
    assert timeline_snapshot(timeline(100))['signature']!=timeline_snapshot(timeline(101))['signature']


def test_modified_timeline_requires_confirmation_before_backup():
    from backend.app.resolve_native_cut import prepare_active_cut
    with pytest.raises(RuntimeError,match='conferma'):
        prepare_active_cut(Obj(),Obj(),timeline(),{'fps':'30','source_path':'original.mov'})


def test_snapshot_changed_after_confirmation_refuses_before_backup():
    from backend.app.resolve_native_cut import prepare_active_cut
    with pytest.raises(RuntimeError,match='nuovamente'):
        prepare_active_cut(Obj(),Obj(),timeline(),{'fps':'30','source_path':'original.mov'},
                           allow_modified=True,expected_signature='old')


def test_confirmed_modified_timeline_keeps_full_snapshot_and_groups_backup(monkeypatch):
    from backend.app.resolve_native_cut import prepare_active_cut
    from backend.app.autocut_reapply import timeline_snapshot
    t=timeline();t.GetName=lambda:'My timeline'
    backup_media=object();backup=Obj(GetMediaPoolItem=lambda:backup_media,GetEndFrame=lambda:1100,GetStartFrame=lambda:100)
    t.DuplicateTimeline=lambda name:backup
    child=Obj(GetName=lambda:'My timeline');bck=Obj(GetName=lambda:'BCK',GetSubFolderList=lambda:[])
    root=Obj(GetSubFolderList=lambda:[bck]);created=[];moved=[]
    pool=Obj(GetRootFolder=lambda:root,AddSubFolder=lambda parent,name:created.append((parent,name)) or child,
             MoveClips=lambda clips,folder:moved.append((clips,folder)) or True)
    project=Obj(GetTimelineCount=lambda:0,SetCurrentTimeline=lambda t:True)
    result=prepare_active_cut(project,pool,t,{'fps':'30','source_path':'original.mov'},
                              allow_modified=True,expected_signature=timeline_snapshot(t)['signature'])
    assert created==[(bck,'My timeline')]
    assert moved==[([backup_media],child)]
    assert result['archive_media'] is backup_media
    assert result['source_duration_frames']==1000


def test_park_uses_snapshot_media_instead_of_original_file(monkeypatch):
    import backend.app.resolve_native_cut as native
    snapshot=object();calls=[]
    items=[Obj(SetClipEnabled=lambda value:True) for _ in range(2)]
    def append(pool,timeline,source,row,base,**kw):calls.append((source,row));return items,0
    monkeypatch.setattr(native,'append_exact_segment',append)
    t=Obj(SetClipsLinked=lambda *a:True,GetMarkers=lambda:{},AddMarker=lambda *a:True,SetMarkInOut=lambda *a:True)
    native.park_original(None,t,object(),{'fps':'30','duration_frames':300},
        {'archive_media':snapshot,'source_duration_frames':1000,'properties':{}},108000,0)
    assert calls[0][0] is snapshot and calls[0][1]['source_out_frame']==1000
