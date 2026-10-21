import pytest
from types import SimpleNamespace as Obj
from tests.unit.test_cut_pass_routes import tmp_path


def test_shortcuts_are_read_from_active_resolve_preset():
    from backend.app.resolve_native_input import decode_presets
    import struct
    n=lambda v:struct.pack('>I',v)
    data=lambda b:n(len(b))+b
    text=lambda s:data(s.encode('utf-16-be'))
    actions={'viewActiveWindowSelectionTimeline':0x04000034,'editSelectAll':0x04000041,'editCut':0x04000058,'editPaste':0x04000056}
    body=n(1)+n(len(actions))+b''.join(text(k)+n(1)+n(1)+n(v) for k,v in actions.items())
    raw=n(1)+n(1)+text('Custom')+data(body)
    assert decode_presets(raw)['Custom']==actions


def clip(identity,start,track=1):
    return Obj(GetUniqueId=lambda:identity,GetStart=lambda:start,GetEnd=lambda:start+30,
        GetName=lambda:'source',GetProperty=lambda:{'ZoomX':1.2},GetClipColor=lambda:'Orange',
        GetClipEnabled=lambda:True,GetSourceStartFrame=lambda:10,GetSourceEndFrame=lambda:39,
        GetFusionCompCount=lambda:0,GetLinkedItems=lambda:[],GetTrackTypeAndIndex=lambda:['video',track])


def test_shift_verifier_requires_same_timeline_all_tracks_and_properties():
    from backend.app.resolve_editable_archive import capture_items,verify_shift
    old=clip('old',100);new=clip('new',700)
    t=Obj(GetUniqueId=lambda:'same',GetTrackCount=lambda k:1 if k=='video' else 0,
        GetItemListInTrack=lambda *a:[old],GetMarkers=lambda:{15:{'name':'keep'}})
    before=capture_items(t)
    t.GetItemListInTrack=lambda *a:[new]
    verify_shift(t,before,600)
    new.GetProperty=lambda:{'ZoomX':1.0}
    with pytest.raises(RuntimeError,match='proprietà'):verify_shift(t,before,600)


def test_missing_selection_stops_before_cut_or_paste():
    from backend.app.resolve_editable_archive import transfer_items
    t=Obj(GetUniqueId=lambda:'same',GetSelectedClips=lambda:[])
    actions=[]
    driver=Obj(focus_timeline=lambda:actions.append('focus'),select_all=lambda:actions.append('select'),
        cut=lambda:actions.append('cut'),paste=lambda:actions.append('paste'))
    with pytest.raises(RuntimeError,match='selezione'):transfer_items(t,[{'id':'clip'}],600,driver,lambda:None)
    assert actions==['focus','select']


def test_successful_transfer_uses_native_clipboard_and_exact_playhead():
    from backend.app.resolve_editable_archive import transfer_items
    item=clip('id',100);rows=[{'id':'id'}];actions=[];visible=[item]
    t=Obj(GetUniqueId=lambda:'same',GetSelectedClips=lambda:visible,SetCurrentTimecode=lambda tc:actions.append(tc) or True,
        GetTrackCount=lambda k:1 if k=='video' else 0,GetItemListInTrack=lambda *a:visible)
    def cut():actions.append('cut');visible.clear()
    driver=Obj(focus_timeline=lambda:actions.append('focus'),select_all=lambda:actions.append('select'),cut=cut,paste=lambda:actions.append('paste'))
    transfer_items(t,rows,'01:00:20:00',driver,lambda:None)
    assert actions==['focus','select','cut','01:00:20:00','focus','paste']


def test_native_verifier_ignores_only_parked_items_beyond_archive_boundary():
    from backend.app.resolve_native_cut import verify_native_cut_base
    main=clip('cut',100);main.GetSourceStartFrame=lambda:0
    parked=clip('parked',700)
    t=Obj(GetItemListInTrack=lambda *args:[main,parked])
    cut={'segments':[{'source_in_frame':0,'source_out_frame':30,'edited_in_frame':0,'edited_out_frame':30}]}
    assert verify_native_cut_base(t,cut,100,archive_start=700)=={'video_count':1,'audio_count':1}
    parked.GetStart=lambda:120
    with pytest.raises(RuntimeError,match='Verifica CUT'):verify_native_cut_base(t,cut,100,archive_start=700)


def test_editable_park_never_appends_a_compound_or_another_media_reference(monkeypatch):
    import backend.app.resolve_native_cut as native
    monkeypatch.setattr(native,'append_exact_segment',lambda *a,**kw:pytest.fail('No clip reconstruction'))
    t=Obj(SetMarkInOut=lambda a,b:True)
    backup={'editable_archive':True,'original_start_frame':700,'original_end_frame':800,
        'export_in_frame':100,'export_out_frame':600,'recovery_path':'local.drt'}
    assert native.park_original(None,t,None,{'duration_frames':500},backup,100,0)['original_start_frame']==700


def test_changed_timeline_guard_runs_before_any_native_clipboard_command():
    from backend.app.resolve_editable_archive import transfer_items
    actions=[];driver=Obj(focus_timeline=lambda:actions.append('focus'))
    def guard():raise RuntimeError('timeline cambiata')
    with pytest.raises(RuntimeError,match='cambiata'):transfer_items(None,[],0,driver,guard)
    assert actions==[]


def test_apply_forwards_editable_mode_to_existing_native_engine(monkeypatch):
    from backend.app.autocut_apply import apply_payload
    import backend.app.resolve_native_cut as native
    timeline=Obj(GetUniqueId=lambda:'same');project=Obj(GetName=lambda:'TEST',GetCurrentTimeline=lambda:timeline)
    resolve=Obj(GetProjectManager=lambda:Obj(GetCurrentProject=lambda:project))
    calls=[]
    monkeypatch.setattr(native,'create_native_cut_base',lambda r,p,payload,**kw:calls.append((payload,kw)) or {'timeline':timeline,'timeline_id':'same'})
    cut={'fps':'30','source_duration_frames':30,'duration_frames':30,'segments':[{'source_in_frame':0,'source_out_frame':30,'edited_in_frame':0,'edited_out_frame':30}]}
    result=apply_payload(resolve,{'context':{'project_name':'TEST','timeline_id':'same'},'native_cut':cut,'destination':'active','editable_archive':True,'recovery_root':'local/recovery'})
    assert result['timeline_id']=='same'
    assert calls[0][0]['editable_archive'] is True and calls[0][1]['target'] is timeline


def test_preserved_subtitles_get_new_st1_without_rebuilding_old_captions(monkeypatch):
    from backend.app.autocut_subtitles import apply_subtitles
    import backend.app.resolve_native_subtitles as native
    actions=[];items=[object()]
    monkeypatch.setattr(native,'reserve_subtitle_track_at_start',lambda t:actions.append('reserve'))
    monkeypatch.setattr(native,'insert_native_subtitles',lambda *a,**kw:actions.append('insert') or items)
    monkeypatch.setattr(native,'verify_native_subtitles',lambda *a,**kw:True)
    monkeypatch.setattr(native,'subtitle_track_for_items',lambda *a:1)
    timeline=Obj(GetItemListInTrack=lambda *a:[object()],SetTrackName=lambda *a:True,SetTrackEnable=lambda *a:True)
    assert apply_subtitles(None,None,timeline,{'editable_archive':True,'native_cut':{'fps':'30'},'subtitle_rows':[{}],'subtitle_path':'local.srt'},100)==1
    assert actions==['reserve','insert']
