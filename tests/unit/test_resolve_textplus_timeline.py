from pathlib import Path
from types import SimpleNamespace

import pytest


def test_fusion_title_insert_retries_while_resolve_initializes_the_duplicate(monkeypatch):
    from backend.app.resolve_textplus_timeline import insert_fusion_title_with_retry

    class Timeline:
        def __init__(self): self.calls = 0
        def InsertFusionTitleIntoTimeline(self, _name):
            self.calls += 1
            return None if self.calls < 3 else "title-item"

    delays = []
    monkeypatch.setattr("backend.app.resolve_textplus_timeline.time.sleep", delays.append)
    timeline = Timeline()
    assert insert_fusion_title_with_retry(timeline, "KURA") == "title-item"
    assert timeline.calls == 3
    assert delays == [0.5, 0.5]


def test_activate_timeline_waits_until_resolve_reports_the_requested_timeline(monkeypatch):
    from backend.app.resolve_textplus_timeline import activate_timeline

    target = SimpleNamespace(GetUniqueId=lambda: "target")
    old = SimpleNamespace(GetUniqueId=lambda: "old")

    class Project:
        def __init__(self): self.calls = 0
        def SetCurrentTimeline(self, timeline): self.calls += 1; return True
        def GetCurrentTimeline(self): return old if self.calls == 1 else target

    class Resolve:
        def OpenPage(self, page): return page == "edit"

    delays = []
    monkeypatch.setattr("backend.app.resolve_textplus_timeline.time.sleep", delays.append)
    project = Project()

    assert activate_timeline(Resolve(), project, target)
    assert project.calls == 2
    assert delays == [0.2]
import shutil
import uuid

from backend.app.resolve_textplus_timeline import (
    boundary_operations,
    build_textplus_timeline_plan,
    wrap_textplus_text,
    select_exact_segments,
    set_textplus_content,
    save_resolve_project,
    export_drt,
    export_dra,
    mode_from_payload,
    run_resolve_helper,
    title_name_from_payload,
    canonical_timeline_name,
    legacy_generated_timelines,
    move_to_boundary,
    find_timeline_media_item,
    next_timeline_name,
    should_rebuild_active_timeline,
    rescale_broll_frames,
    remove_prior_rambla_items,
    next_backup_name,
    snapshot_timeline_markers,
    verify_timeline_markers,
    restore_timeline_markers,
    active_track_layout,
    create_active_backup,
    conform_broll_media,
    mute_prior_rambla_titles,
    remove_prior_rambla_titles,
    mute_prior_rambla_subtitles,
    remove_prior_rambla_broll,
    remap_broll_for_selective_refresh,
    next_rambla_track_name,
    raise_if_cancelled,
    ResolveApplyCancelled,
    append_nested_title_layer,
    append_separate_fusion_titles,
    backup_drt_path,
    remove_archived_backup_timeline,
)


def test_textplus_wraps_at_word_boundaries_to_vertical_safe_lines():
    assert wrap_textplus_text("National Geographic") == "National\nGeographic"
    assert wrap_textplus_text("turismo sostenibile") == "turismo\nsostenibile"
    assert wrap_textplus_text("viaggio in treno") == "viaggio in\ntreno"
    assert wrap_textplus_text("dieci char") == "dieci char"


def test_textplus_wrap_keeps_single_long_words_intact():
    assert wrap_textplus_text("sostenibilissimo") == "sostenibilissimo"


def test_textplus_plan_stores_wrapped_copy_used_for_resolve_verification():
    plan = build_textplus_timeline_plan(
        {"items": [{"text": "turismo sostenibile", "start_seconds": 0, "end_seconds": 1}]},
        target_fps=30,
    )
    assert plan["segments"][0]["text"] == "turismo\nsostenibile"


def test_selective_title_refresh_mutes_prior_rmbl_titles_across_style_changes():
    class Item:
        def __init__(self, name, color, fusion):
            self.name,self.color,self.fusion=name,color,fusion
            self.enabled=True
        def GetFusionCompCount(self): return self.fusion
        def GetName(self): return self.name
        def GetClipColor(self): return self.color
        def SetClipEnabled(self,value): self.enabled=bool(value); return True
    rmbl=Item("Legacy_Paper_Style","Yellow",1)
    user=Item("My title","Yellow",1)
    class Timeline:
        def GetTrackCount(self,kind): return 2 if kind=="video" else 0
        def GetTrackName(self,kind,track): return "RMBL TEXT v2" if track==1 else "CLIENT TITLES"
        def GetItemListInTrack(self,kind,track): return [rmbl] if track==1 else [user]
    assert mute_prior_rambla_titles(Timeline(),title_name="KURA_paper_title_v9")==1
    assert rmbl.enabled is False and user.enabled is True


def test_nested_rmbl_title_layer_is_recognized_on_its_named_track():
    class Item:
        def GetFusionCompCount(self): return 0
        def GetName(self): return "RMBL TEXT LAYER 20261009-173000"
        def GetClipColor(self): return "Yellow"

    from backend.app.resolve_textplus_timeline import _is_rambla_generated_title

    assert _is_rambla_generated_title(
        Item(), title_name="KURA_paper_title_v9", track_name="RMBL TEXT v3"
    ) is True


def test_append_nested_title_layer_targets_the_dedicated_upper_track(monkeypatch):
    title_timeline = SimpleNamespace(GetUniqueId=lambda: "titles")
    media = object()

    class MediaPool:
        def AppendToTimeline(self, rows):
            self.rows = rows
            return [SimpleNamespace(SetClipColor=lambda color: color == "Yellow")]

    pool = MediaPool()
    monkeypatch.setattr(
        "backend.app.resolve_textplus_timeline.find_timeline_media_item",
        lambda _pool, _timeline: media,
    )
    item = append_nested_title_layer(
        pool, object(), title_timeline,
        base_frame=108000, duration_frames=900, track_index=13,
    )

    assert item is not None
    assert pool.rows == [{
        "mediaPoolItem": media,
        "startFrame": 0,
        "endFrame": 900,
        "mediaType": 1,
        "trackIndex": 13,
        "recordFrame": 108000,
    }]


def test_separate_fusion_titles_are_individual_clips_on_the_upper_track():
    media = SimpleNamespace(GetClipProperty=lambda key: "Video" if key == "Type" else "")
    existing = SimpleNamespace(GetMediaPoolItem=lambda: media)

    class Source:
        def __init__(self, start, end): self.start, self.end = start, end
        def GetStart(self): return self.start
        def GetEnd(self): return self.end
        def ExportFusionComp(self, path, index):
            assert index == 1
            Path(path).write_text("composition", encoding="utf-8")
            return True

    class FusionItem:
        def __init__(self, raw): self.raw, self.name, self.color = raw, "", ""
        def ImportFusionComp(self, path): return Path(path).is_file()
        def SetName(self, name): self.name = name; return True
        def SetClipColor(self, color): self.color = color; return True
        def GetStart(self): return self.raw.GetStart()
        def GetEnd(self): return self.raw.GetEnd()
        def GetFusionCompCount(self): return 1

    class Timeline:
        def __init__(self): self.created = []
        def GetTrackCount(self, kind): return 1
        def GetItemListInTrack(self, kind, track): return [existing]
        def CreateFusionClip(self, items):
            raise AssertionError("Titles must not be wrapped in a nested Fusion Clip")

    class Pool:
        def __init__(self): self.rows = []
        def AppendToTimeline(self, rows):
            self.rows.extend(rows)
            row = rows[0]
            return [FusionItem(SimpleNamespace(
                GetStart=lambda: row["recordFrame"],
                GetEnd=lambda: row["recordFrame"] + row["endFrame"],
            ))]

    timeline, pool = Timeline(), Pool()
    clips = append_separate_fusion_titles(
        pool, timeline, [Source(108010, 108020), Source(108040, 108055)],
        source_base_frame=108000, destination_base_frame=200000,
        track_index=8, title_name="KURA_paper_title_v9",
        composition_root=Path.cwd() / ".unit-title-comps",
    )

    assert [(row["recordFrame"], row["endFrame"], row["trackIndex"]) for row in pool.rows] == [
        (200010, 10, 8), (200040, 15, 8),
    ]
    assert len(clips) == 2
    assert [(clip.name, clip.color) for clip in clips] == [
        ("KURA_paper_title_v9", "Yellow"),
        ("KURA_paper_title_v9", "Yellow"),
    ]


def test_backup_is_archived_as_drt_and_temporary_timeline_is_removed():
    backup_root = Path.cwd() / ".unit-backups"
    path = backup_drt_path(
        {"media_staging_root": str(backup_root / "resolve-media")},
        'EGITTO · BCK · 2026-10-09 · 18-00-00 · 001',
    )
    assert path.parent == backup_root / "BCK"
    assert path.suffix == ".drt"

    backup = object()
    pool = SimpleNamespace(DeleteTimelines=lambda rows: rows == [backup])
    remove_archived_backup_timeline(pool, backup)


def test_selective_title_refresh_removes_only_previous_rmbl_titles():
    class Item:
        def __init__(self, name, color, fusion): self.name, self.color, self.fusion = name, color, fusion
        def GetName(self): return self.name
        def GetClipColor(self): return self.color
        def GetFusionCompCount(self): return self.fusion

    old_title = Item("KURA_paper_title_v9", "Yellow", 1)
    client_clip = Item("Client overlay", "", 0)

    class Timeline:
        def __init__(self): self.deleted = []
        def GetTrackCount(self, kind): return 1
        def GetTrackName(self, kind, track): return "RMBL TEXT v2"
        def GetItemListInTrack(self, kind, track): return [old_title, client_clip]
        def DeleteClips(self, rows, ripple): self.deleted = list(rows); return ripple is False

    timeline = Timeline()
    assert remove_prior_rambla_titles(timeline, title_name="KURA_paper_title_v9") == 1
    assert timeline.deleted == [old_title]


def test_selective_subtitle_refresh_mutes_only_rmbl_sources():
    class Media:
        def __init__(self,name): self.name=name
        def GetName(self): return self.name
        def GetClipProperty(self,key): return ""
    class Item:
        def __init__(self,media): self.media=media; self.enabled=True
        def GetMediaPoolItem(self): return self.media
        def SetClipEnabled(self,value): self.enabled=bool(value); return True
    rmbl=Item(Media("RAMBLA · 20 sottotitoli nativi · sorgente interna"))
    user=Item(Media("Client subtitles"))
    class Timeline:
        def GetTrackCount(self,kind): return 1 if kind=="subtitle" else 0
        def GetTrackName(self,kind,track): return "Subtitle 1"
        def GetItemListInTrack(self,kind,track): return [rmbl,user]
    assert mute_prior_rambla_subtitles(Timeline())==1
    assert rmbl.enabled is False and user.enabled is True


def test_media_refresh_removes_only_rmbl_broll_and_reuses_its_tracks():
    class Media:
        def __init__(self, keywords): self.keywords=keywords
        def GetMetadata(self): return {"Keywords": self.keywords}
    class Item:
        def __init__(self, keywords, color):
            self.media=Media(keywords); self.color=color
        def GetMediaPoolItem(self): return self.media
        def GetClipColor(self): return self.color
    rmbl=Item("RAMBLA, pexels, beat_1","Purple")
    user=Item("client footage","Purple")
    class Timeline:
        def __init__(self): self.tracks=[[user],[rmbl],[]]; self.deleted=[]
        def GetTrackCount(self,kind): return len(self.tracks) if kind=="video" else 0
        def GetItemListInTrack(self,kind,track): return self.tracks[track-1]
        def DeleteClips(self,items,_ripple):
            self.deleted.extend(items)
            for row in self.tracks:
                row[:] = [item for item in row if item not in items]
            return True
        def AddTrack(self,kind): self.tracks.append([]); return True
    timeline=Timeline()
    removed,tracks=remove_prior_rambla_broll(timeline)
    assert removed == 1 and tracks == [2]
    assert timeline.deleted == [rmbl] and user in timeline.tracks[0]

    rows=remap_broll_for_selective_refresh(timeline,[
        {"asset_id":"a","track_index":2},
        {"asset_id":"b","track_index":2},
    ],tracks)
    assert [row["track_index"] for row in rows] == [2,2]


def test_media_refresh_adds_only_missing_media_tracks_when_no_reusable_track_exists():
    class Timeline:
        def __init__(self): self.count=3
        def GetTrackCount(self,kind): return self.count
        def AddTrack(self,kind): self.count+=1; return True
    timeline=Timeline()
    rows=remap_broll_for_selective_refresh(timeline,[
        {"asset_id":"a","track_index":2},
        {"asset_id":"b","track_index":3},
    ],[])
    assert [row["track_index"] for row in rows] == [4,5]
    assert timeline.count == 5


def test_rambla_track_versions_increment_without_touching_other_track_names():
    class Timeline:
        def GetTrackCount(self,kind): return 3
        def GetTrackName(self,kind,track): return ["V1","RMBL TEXT v1","RMBL TEXT v3"][track-1]
    assert next_rambla_track_name(Timeline(),"video","RMBL TEXT")=="RMBL TEXT v4"


def test_active_rambla_timeline_is_rebuilt_after_backup_instead_of_duplicating_generated_items():
    assert should_rebuild_active_timeline("active", "Client - SUBS + KEYWORDS + B-ROLL TIMELINE v2")
    assert not should_rebuild_active_timeline("active", "Client master edit")
    assert not should_rebuild_active_timeline("new", "Client - SUBS + KEYWORDS TIMELINE v1")


def test_active_destination_creates_one_backup_and_keeps_the_real_timeline_as_target():
    class Timeline:
        def __init__(self): self.duplicates = []
        def DuplicateTimeline(self, name):
            self.duplicates.append(name)
            return SimpleNamespace(GetName=lambda: name)

    original = Timeline()
    target, backup = create_active_backup(original, "EGITTO · BCK · 2026-10-02 · 14-35-20 · 001")

    assert target is original
    assert backup.GetName().endswith("001")
    assert original.duplicates == ["EGITTO · BCK · 2026-10-02 · 14-35-20 · 001"]


def test_backup_name_is_timestamped_and_numbered_for_the_same_second():
    rows = [SimpleNamespace(GetName=lambda: "EGITTO · BCK · 2026-10-02 · 14-35-20 · 001")]
    project = SimpleNamespace(
        GetTimelineCount=lambda: len(rows),
        GetTimelineByIndex=lambda index: rows[index - 1],
    )

    assert next_backup_name(project, "EGITTO", timestamp="2026-10-02 · 14-35-20") == (
        "EGITTO · BCK · 2026-10-02 · 14-35-20 · 002"
    )


def test_timeline_markers_must_remain_byte_for_byte_equivalent():
    timeline = SimpleNamespace(GetMarkers=lambda: {108030.0: {"color":"Blue","name":"note","note":"x","duration":1.0}})
    expected = snapshot_timeline_markers(timeline)
    verify_timeline_markers(timeline, expected)
    timeline.GetMarkers = lambda: {108031.0: {"color":"Blue","name":"note","note":"x","duration":1.0}}
    with pytest.raises(RuntimeError, match="marker"):
        verify_timeline_markers(timeline, expected)


def test_timeline_markers_are_restored_to_their_original_frames_and_metadata():
    markers = {10.0: {"color":"Blue","name":"A","note":"note","duration":2.0,"customData":"id"}}
    class Timeline:
        def __init__(self):
            self.markers={99.0:{"color":"Red","name":"moved","note":"","duration":1,"customData":""}}
            self.deleted=[]; self.added=[]
        def GetMarkers(self): return dict(self.markers)
        def DeleteMarkerAtFrame(self, frame):
            self.deleted.append(frame); self.markers.pop(frame, None); return True
        def AddMarker(self, frame, color, name, note, duration, custom):
            self.added.append(frame)
            self.markers[frame]={"color":color,"name":name,"note":note,"duration":duration,"customData":custom}; return True
    timeline=Timeline()
    assert restore_timeline_markers(timeline, markers) is True
    assert timeline.markers == markers
    assert timeline.deleted == [99.0] and timeline.added == [10.0]


def test_marker_preservation_does_not_rewrite_markers_when_they_are_already_exact():
    markers = {10.0: {"color":"Blue","name":"A","note":"note","duration":2.0,"customData":"id"}}
    class Timeline:
        def __init__(self): self.deleted=[]; self.added=[]
        def GetMarkers(self): return markers
        def DeleteMarkerAtFrame(self, frame): self.deleted.append(frame); return True
        def AddMarker(self, *args): self.added.append(args); return True
    timeline=Timeline()

    assert restore_timeline_markers(timeline, markers) is False
    assert timeline.deleted == []
    assert timeline.added == []


def test_highlight_track_is_always_above_every_broll_track():
    rows, title_track = active_track_layout(5, [
        {"track_index": 2, "asset_id": "a"},
        {"track_index": 4, "asset_id": "b"},
    ])

    assert [row["track_index"] for row in rows] == [6, 8]
    assert title_track == 9
    assert title_track > max(row["track_index"] for row in rows)


def test_conformed_broll_keeps_equal_duration_handles_when_source_allows(monkeypatch):
    root = Path.cwd() / (".test-broll-handles-" + uuid.uuid4().hex)
    root.mkdir()
    source = root / "source.mp4"
    source.write_bytes(b"source")
    commands = []
    try:
        monkeypatch.setattr("backend.app.resolve_textplus_timeline.probe_preview", lambda _: {"duration":30.0})
        def run(command, **kwargs):
            commands.append(command)
            Path(command[-1]).write_bytes(b"conformed")
            return SimpleNamespace(returncode=0)
        monkeypatch.setattr("backend.app.resolve_textplus_timeline.subprocess.run", run)

        rows = conform_broll_media([{
            "media_path":str(source), "record_start_frame":0, "record_end_frame":90,
            "source_start_frame":300, "source_end_frame":390,
        }], 30)

        assert rows[0]["source_start_frame"] == 90
        assert rows[0]["source_end_frame"] == 180
        assert rows[0]["handle_before_frames"] == 90
        assert rows[0]["handle_after_frames"] == 90
        assert commands[0][commands[0].index("-frames:v") + 1] == "270"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_conformed_broll_keeps_the_selected_preview_as_the_visible_anchor(monkeypatch):
    root = Path.cwd() / (".test-broll-preview-anchor-" + uuid.uuid4().hex)
    root.mkdir()
    source = root / "source.mp4"
    source.write_bytes(b"source")
    try:
        monkeypatch.setattr("backend.app.resolve_textplus_timeline.probe_preview", lambda _: {"duration":30.0})
        def run(command, **kwargs):
            Path(command[-1]).write_bytes(b"conformed")
            return SimpleNamespace(returncode=0)
        monkeypatch.setattr("backend.app.resolve_textplus_timeline.subprocess.run", run)

        row = conform_broll_media([{
            "media_path":str(source), "record_start_frame":0, "record_end_frame":60,
            "source_start_frame":360, "source_end_frame":420,
        }], 30)[0]

        assert row["selected_source_start_frame_absolute"] == 360
        assert row["selected_source_end_frame_absolute"] == 420
        assert row["conformed_cut_start_frame_absolute"] + row["source_start_frame"] == 360
        assert row["source_end_frame"] - row["source_start_frame"] == 60
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_conformed_broll_moves_unavailable_left_handle_budget_to_the_right(monkeypatch):
    root = Path.cwd() / (".test-broll-edge-handles-" + uuid.uuid4().hex)
    root.mkdir(); source = root / "source.mp4"; source.write_bytes(b"source")
    try:
        monkeypatch.setattr("backend.app.resolve_textplus_timeline.probe_preview", lambda _: {"duration":30.0})
        def run(command, **kwargs): Path(command[-1]).write_bytes(b"conformed"); return SimpleNamespace(returncode=0)
        monkeypatch.setattr("backend.app.resolve_textplus_timeline.subprocess.run", run)
        row = conform_broll_media([{"media_path":str(source),"record_start_frame":0,"record_end_frame":90,
            "source_start_frame":0,"source_end_frame":90}],30)[0]
        assert row["handle_before_frames"] == 0
        assert row["handle_after_frames"] == 180
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_clear_generated_timeline_unlocks_duplicate_tracks_before_deleting():
    from backend.app.resolve_textplus_timeline import clear_generated_timeline

    class Timeline:
        def __init__(self):
            self.items = {("video", 1): [object()], ("audio", 1): [object()]}
            self.locked = {("video", 1): True, ("audio", 1): True}
        def GetTrackCount(self, kind): return 1 if kind in {"video", "audio"} else 0
        def GetItemListInTrack(self, kind, track): return self.items.get((kind, track), [])
        def GetIsTrackLocked(self, kind, track): return self.locked[(kind, track)]
        def SetTrackLock(self, kind, track, value): self.locked[(kind, track)] = value; return True
        def DeleteClips(self, items, ripple):
            assert ripple is False
            if any(self.locked.values()): return False
            for key in self.items: self.items[key] = []
            return True

    timeline = Timeline()
    clear_generated_timeline(timeline)

    assert not any(timeline.locked.values())
    assert not any(timeline.items.values())


def test_broll_clips_are_appended_to_exact_records_on_separate_video_tracks():
    from backend.app.resolve_textplus_timeline import append_broll_clips

    class Item:
        def __init__(self, path): self.path = path
    class Timeline:
        def __init__(self): self.tracks = 1
        def GetTrackCount(self, kind): return self.tracks if kind == "video" else 0
        def AddTrack(self, kind): self.tracks += 1; return kind == "video"
    class Pool:
        def __init__(self): self.appended = []
        def ImportMedia(self, paths): return [Item(paths[0])]
        def AppendToTimeline(self, rows): self.appended.extend(rows); return [object()]
    pool, timeline = Pool(), Timeline()
    clips = [
        {"media_path": "C:/one.mp4", "track_index": 2, "record_start_frame": 25, "record_end_frame": 75, "source_start_frame": 0, "source_end_frame": 50},
        {"media_path": "C:/two.mp4", "track_index": 3, "record_start_frame": 25, "record_end_frame": 75, "source_start_frame": 10, "source_end_frame": 60},
    ]

    count = append_broll_clips(pool, timeline, clips, base_frame=108000)

    assert count == 2 and timeline.tracks == 3
    assert [(row["trackIndex"], row["recordFrame"], row["startFrame"], row["endFrame"]) for row in pool.appended] == [
        (2, 108025, 0, 50), (3, 108025, 10, 60),
    ]


def test_broll_frames_are_rescaled_from_package_fps_to_resolve_fps():
    rows = rescale_broll_frames([{"record_start_frame":345,"record_end_frame":444,
        "source_start_frame":0,"source_end_frame":99,"duration_frames":99}], source_fps=25, target_fps=30)
    assert rows == [{"record_start_frame":414,"record_end_frame":533,
        "source_start_frame":0,"source_end_frame":119,"duration_frames":119}]


def test_selected_image_is_materialized_as_a_frame_exact_still_video(tmp_path, monkeypatch):
    from backend.app.resolve_textplus_timeline import conform_broll_media
    import backend.app.resolve_textplus_timeline as module

    source = tmp_path / "egypt.jpg"
    source.write_bytes(b"image")
    commands = []
    def run(command, **_kwargs):
        commands.append(command)
        Path(command[-1]).write_bytes(b"video")
    monkeypatch.setattr(module.subprocess, "run", run)

    result = conform_broll_media([{
        "kind": "image", "media_path": str(source), "record_start_frame": 10,
        "record_end_frame": 60, "source_start_frame": 0, "source_end_frame": 50,
    }], 25)

    assert commands and commands[0][commands[0].index("-loop") + 1] == "1"
    assert commands[0][commands[0].index("-frames:v") + 1] == "50"
    assert Path(result[0]["media_path"]).suffix == ".mp4"
    assert (result[0]["source_start_frame"], result[0]["source_end_frame"]) == (0, 50)


def test_prior_rambla_layers_are_removed_from_duplicate_only():
    class Media:
        def __init__(self, rambla=False): self.rambla=rambla
        def GetMetadata(self): return {"Keywords":"RAMBLA, pexels"} if self.rambla else {}
    class Item:
        def __init__(self,name,color,fusion=0,rambla=False): self.name,self.color,self.fusion,self.media=name,color,fusion,Media(rambla)
        def GetName(self): return self.name
        def GetClipColor(self): return self.color
        def GetFusionCompCount(self): return self.fusion
        def GetMediaPoolItem(self): return self.media
    old_title=Item("KURA","Yellow",1); user_title=Item("Other","Yellow",1)
    old_broll=Item("clip","Purple",0,True); user_broll=Item("clip","Purple",0,False); sub=Item("sub","",0)
    class Timeline:
        def __init__(self): self.rows={"video":[old_title,user_title,old_broll,user_broll],"subtitle":[sub]}; self.deleted=[]
        def GetTrackCount(self,kind): return 1 if kind in self.rows else 0
        def GetItemListInTrack(self,kind,track): return list(self.rows[kind])
        def DeleteClips(self,items,ripple): self.deleted.extend(items); return True
    timeline=Timeline(); result=remove_prior_rambla_items(timeline,title_name="KURA")
    assert result=={"video":2,"subtitle":1}
    assert timeline.deleted==[old_title,old_broll,sub]


def test_active_timeline_tracks_are_locked_and_existing_clip_movement_fails_closed():
    from backend.app.resolve_textplus_timeline import (
        protect_existing_tracks, restore_track_locks,
        snapshot_existing_timeline_items, verify_existing_timeline_items,
    )

    class Existing:
        def __init__(self, identity): self.identity, self.start, self.end = identity, 100, 150
        def GetUniqueId(self): return self.identity
        def GetStart(self): return self.start
        def GetEnd(self): return self.end
        def GetName(self): return "Original B-roll"
    class Timeline:
        def __init__(self):
            self.items = {("video", 1): [Existing("existing-video")], ("audio", 1): [Existing("existing-audio")]}
            self.counts = {"video": 1, "audio": 1, "subtitle": 0}
            self.locks = {("video", 1): False, ("audio", 1): True}
        def GetTrackCount(self, kind): return self.counts[kind]
        def GetItemListInTrack(self, kind, track): return self.items.get((kind, track), [])
        def GetIsTrackLocked(self, kind, track): return self.locks.get((kind, track), False)
        def SetTrackLock(self, kind, track, value): self.locks[(kind, track)] = value; return True
        def AddTrack(self, kind): self.counts[kind] += 1; return True

    timeline = Timeline()
    before = snapshot_existing_timeline_items(timeline)
    states, original_video_tracks = protect_existing_tracks(timeline, reserve_subtitle_track=True)
    assert original_video_tracks == 1
    assert timeline.counts == {"video": 2, "audio": 1, "subtitle": 1}
    assert timeline.locks[("video", 1)] and timeline.locks[("audio", 1)]
    restore_track_locks(timeline, states)
    assert timeline.locks[("video", 1)] is False and timeline.locks[("audio", 1)] is True
    verify_existing_timeline_items(timeline, before)
    timeline.items[("video", 1)][0].start += 10
    with pytest.raises(RuntimeError, match="existing timeline clips moved"):
        verify_existing_timeline_items(timeline, before)


def test_broll_media_uses_versioned_project_folder_readable_names_and_source_metadata():
    from backend.app.resolve_textplus_timeline import prepare_broll_media_files, versioned_media_folder_name, append_broll_clips

    root = Path.cwd() / (".test-resolve-media-" + uuid.uuid4().hex)
    root.mkdir()
    try:
        source = root / "full.mp4"
        source.write_bytes(b"video")
        folder = versioned_media_folder_name("KURA / Test", "KURA Test - SUBS + KEYWORDS + B-ROLL TIMELINE v4")
        assert folder == "KURA_Test_media_v4"
        clips = prepare_broll_media_files([{
            "asset_id": "beat_3--envato:abc", "beat_id": "beat_3", "media_path": str(source),
            "title": "Bathroom mirror / morning", "provider": "envato",
            "source_page": "https://elements.envato.com/item-ABC123", "track_index": 2,
            "record_start_frame": 10, "record_end_frame": 30, "source_start_frame": 0, "source_end_frame": 20,
        }], root / "staged", folder)
        staged = Path(clips[0]["media_path"])
        assert staged.parent.name == folder
        assert staged.name == "Bathroom_mirror_morning_envato.mp4"

        class Item:
            def __init__(self): self.metadata = None
            def SetMetadata(self, value): self.metadata = value; return True
        class Timeline:
            def GetTrackCount(self, _): return 2
        class Pool:
            def __init__(self): self.item = Item()
            def ImportMedia(self, _): return [self.item]
            def AppendToTimeline(self, _): return [object()]
        pool = Pool()
        assert append_broll_clips(pool, Timeline(), clips, base_frame=100) == 1
        assert pool.item.metadata["Description"] == "Bathroom mirror / morning"
        assert "https://elements.envato.com/item-ABC123" in pool.item.metadata["Comments"]
        assert "beat_3" in pool.item.metadata["Keywords"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def payload():
    return {
        "project_id": "reel-1",
        "items": [
            {"text": "due tre", "start_seconds": 0.5, "end_seconds": 1.5},
            {"text": "Otto", "start_seconds": 4.0, "end_seconds": 4.5},
        ],
    }


def test_plan_uses_target_timeline_fps_and_every_start_end_boundary():
    plan = build_textplus_timeline_plan(payload(), target_fps=30)

    assert plan["boundaries"] == [15, 45, 120, 135]
    assert plan["segments"] == [
        {"text": "due tre", "start_frame": 15, "end_frame": 45},
        {"text": "Otto", "start_frame": 120, "end_frame": 135},
    ]


def test_boundary_operations_prime_resolve_before_nonzero_first_title():
    plan = build_textplus_timeline_plan(payload(), target_fps=30)

    assert boundary_operations(plan) == [
        {"frame": 0, "text": None},
        {"frame": 15, "text": "due tre"},
        {"frame": 45, "text": None},
        {"frame": 120, "text": "Otto"},
        {"frame": 135, "text": None},
    ]


def test_boundary_operations_do_not_duplicate_zero_when_first_title_starts_at_origin():
    plan = build_textplus_timeline_plan(
        {"items": [{"text": "zero", "start_seconds": 0, "end_seconds": 1}]},
        target_fps=30,
    )

    assert boundary_operations(plan) == [
        {"frame": 0, "text": "zero"},
        {"frame": 30, "text": None},
    ]


def test_plan_refuses_overlapping_textplus_clips():
    value = payload()
    value["items"][1].update(start_seconds=1.0, end_seconds=2.0)

    with pytest.raises(ValueError, match="overlap"):
        build_textplus_timeline_plan(value, target_fps=30)


def test_materialized_segments_keep_only_exact_requested_ranges():
    existing = [
        {"id": "a", "start_frame": 15, "end_frame": 45},
        {"id": "gap", "start_frame": 45, "end_frame": 120},
        {"id": "b", "start_frame": 120, "end_frame": 135},
        {"id": "tail", "start_frame": 135, "end_frame": 255},
    ]
    keep, remove = select_exact_segments(existing, build_textplus_timeline_plan(payload(), target_fps=30)["segments"])

    assert [(row["id"], row["text"]) for row in keep] == [("a", "due tre"), ("b", "Otto")]
    assert [row["id"] for row in remove] == ["gap", "tail"]


def test_materialized_segments_remove_resolve_priming_lead_in():
    materialized = [
        {"id": "prime", "start_frame": 0, "end_frame": 15},
        {"id": "wanted", "start_frame": 15, "end_frame": 45},
    ]
    requested = [{"text": "due tre", "start_frame": 15, "end_frame": 45}]

    keep, remove = select_exact_segments(materialized, requested)

    assert [(row["id"], row["text"]) for row in keep] == [("wanted", "due tre")]
    assert [row["id"] for row in remove] == ["prime"]


def test_materialized_segments_reject_wrong_physical_duration():
    existing = [{"id": "a", "start_frame": 15, "end_frame": 50}]

    with pytest.raises(RuntimeError, match=r"exact Text\+ range"):
        select_exact_segments(existing, build_textplus_timeline_plan({"items": [payload()["items"][0]]}, target_fps=30)["segments"])


def test_setting_text_does_not_rename_timeline_item_and_reset_fusion_value():
    class Input:
        def __init__(self):
            self.values = {0: "Custom Title"}

        def __setitem__(self, frame, value):
            self.values[frame] = value

    class Tool:
        def __init__(self):
            self.StyledText = Input()

        def GetInput(self, name, frame):
            assert name == "StyledText"
            return self.StyledText.values[frame]

    class Composition:
        def __init__(self, tool):
            self.tool = tool

        def GetToolList(self, *_):
            return {1: self.tool}

    class Item:
        def __init__(self):
            self.tool = Tool()
            self.renamed = False

        def GetFusionCompByIndex(self, index):
            assert index == 1
            return Composition(self.tool)

        def SetName(self, _):
            self.renamed = True
            self.tool.StyledText.values[0] = "Custom Title"

    item = Item()

    set_textplus_content(item, "antonomasia")

    assert item.tool.GetInput("StyledText", 0) == "antonomasia"
    assert item.renamed is False


def test_setting_text_prefers_exposed_template_control_in_custom_title():
    class Input:
        def __init__(self, value):
            self.values = {0: value}

        def __setitem__(self, frame, value):
            self.values[frame] = value

    class Tool:
        def __init__(self, name, value):
            self.Name = name
            self.StyledText = Input(value)

        def GetInput(self, name, frame):
            assert name == "StyledText"
            return self.StyledText.values[frame]

    template = Tool("Template", "sostenibile")
    animated = Tool("Text1_1", "0")

    class Composition:
        def GetToolList(self, *_):
            return {1: template, 2: animated}

    class Item:
        def GetFusionCompByIndex(self, index):
            assert index == 1
            return Composition()

    set_textplus_content(Item(), "antonomasia")

    assert template.GetInput("StyledText", 0) == "antonomasia"
    assert animated.GetInput("StyledText", 0) == "0"


def test_text_control_waits_for_fusion_to_initialize_before_next_insertion(monkeypatch):
    from backend.app.resolve_textplus_timeline import _text_tool
    from types import SimpleNamespace
    template = SimpleNamespace(Name='Template')
    class Composition:
        calls = 0
        def GetToolList(self, *_):
            self.calls += 1
            return {} if self.calls < 3 else {1: template}
    comp = Composition()
    item = SimpleNamespace(GetFusionCompByIndex=lambda _: comp)
    delays = []
    monkeypatch.setattr('backend.app.resolve_textplus_timeline.time.sleep', delays.append)
    assert _text_tool(item) is template
    assert len(delays) == 2


def test_selected_title_name_is_required_and_preserved():
    assert title_name_from_payload({"title_name": "KURA_paper_title_v9"}) == "KURA_paper_title_v9"

    with pytest.raises(ValueError, match="title template"):
        title_name_from_payload({})


def test_multiple_text_controls_without_exposed_template_are_rejected():
    class Tool:
        def __init__(self, name):
            self.Name = name

    class Composition:
        def GetToolList(self, *_):
            return {1: Tool("First"), 2: Tool("Second")}

    class Item:
        def GetFusionCompByIndex(self, _):
            return Composition()

    with pytest.raises(RuntimeError, match="ambiguous"):
        set_textplus_content(Item(), "word")


def test_generated_timeline_is_saved_in_the_resolve_project():
    class ProjectManager:
        def __init__(self, result):
            self.result = result
            self.calls = 0

        def SaveProject(self):
            self.calls += 1
            return self.result

    manager = ProjectManager(True)
    save_resolve_project(manager)
    assert manager.calls == 1

    with pytest.raises(RuntimeError, match="save the generated timeline"):
        save_resolve_project(ProjectManager(False))


def test_helper_accepts_only_titles_or_combined_modes():
    assert mode_from_payload({}) == "titles"
    assert mode_from_payload({"mode": "combined"}) == "combined"
    with pytest.raises(ValueError, match="mode"):
        mode_from_payload({"mode": "other"})


def test_drt_export_uses_official_resolve_constants_and_preserves_requested_path():
    target = Path("selected words and subs.drt")

    class Resolve:
        EXPORT_DRT = "drt"
        EXPORT_NONE = "none"

    class Timeline:
        def __init__(self, result=True): self.result = result; self.args = None
        def Export(self, *args):
            self.args = args
            if self.result:
                Path(args[0]).write_bytes(b"DRT")
            return self.result

    timeline = Timeline()
    assert export_drt(Resolve(), timeline, target) == target
    assert timeline.args[1:] == ("drt", "none")
    assert timeline.args[0].endswith(".drt")
    assert Path(timeline.args[0]) != target
    target.unlink()

    with pytest.raises(RuntimeError, match="DRT"):
        export_drt(Resolve(), Timeline(False), target)


def test_dra_export_archives_locally_then_copies_a_downloadable_package(monkeypatch):
    target = Path("resolve-export-test.dra")

    class Project:
        def GetName(self): return "Current Resolve Project"

    class Manager:
        def __init__(self): self.path = None
        def ArchiveProject(self, name, path, *flags):
            self.path = Path(path)
            assert name == "Current Resolve Project"
            assert self.path != target
            self.path.mkdir(parents=True)
            (self.path / "project.drp").write_bytes(b"archive")
            return True

    manager = Manager()
    exported = export_dra(manager, Project(), target)

    assert exported == Path("resolve-export-test.dra.zip")
    assert exported.is_file() and exported.stat().st_size > 0
    exported.unlink()


def test_dra_export_falls_back_to_loaded_project_export_when_archive_is_refused():
    target = Path("resolve-export-fallback.dra")

    class Project:
        def GetName(self): return "Loaded Project"

    class Manager:
        def ArchiveProject(self, *_): return False
        def ExportProject(self, name, path, with_stills):
            assert (name, with_stills) == ("Loaded Project", True)
            Path(path).write_bytes(b"DRP")
            return True

    exported = export_dra(Manager(), Project(), target)

    assert exported.is_file() and exported.stat().st_size > 0
    exported.unlink()


def test_helper_tolerates_non_utf8_native_resolve_diagnostics(monkeypatch, tmp_path):
    # The subprocess is mocked; provide isolated placeholder paths rather than
    # requiring a full DaVinci Resolve installation on GitHub CI runners.
    api_root = tmp_path / "ResolveScripting"
    module = api_root / "Modules" / "DaVinciResolveScript.py"
    module.parent.mkdir(parents=True)
    module.write_text("# mocked API path", encoding="utf-8")
    native_lib = tmp_path / "fusionscript.dll"
    native_lib.write_bytes(b"mock")
    monkeypatch.setenv("RESOLVE_SCRIPT_API", str(api_root))
    monkeypatch.setenv("RESOLVE_SCRIPT_LIB", str(native_lib))
    captured = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(returncode=0, stdout='{"status":"created"}', stderr="")

    monkeypatch.setattr("backend.app.resolve_textplus_timeline.subprocess.run", fake_run)

    assert run_resolve_helper({"items": [{"text": "è", "start_seconds": 0, "end_seconds": 1}]}) == {"status": "created"}
    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"
    assert captured["env"]["PYTHONUTF8"] == "1"


def test_canonical_timeline_name_uses_readable_project_name_and_version():
    assert canonical_timeline_name({"project_name": "New Reel", "mode": "combined"}) == "New Reel - SUBS + KEYWORDS TIMELINE v1"
    assert canonical_timeline_name({"project_name": "  KURA / Thailand:*  ", "mode": "combined"}) == "KURA Thailand - SUBS + KEYWORDS TIMELINE v1"


def test_legacy_generated_timelines_removes_only_technical_legacy_names():
    class TimelineRef:
        def __init__(self, name): self.name = name
        def GetName(self): return self.name

    rows = [
        TimelineRef("KURA source"),
        TimelineRef("RAMBLA_COMBINED_old"),
        TimelineRef("New Reel - SUBS + KEYWORDS TIMELINE v1"),
        TimelineRef("New Reel · SUBS + KEYWORDS TIMELINE v1"),
        TimelineRef("Client edit"),
    ]

    class Project:
        def GetTimelineCount(self): return len(rows)
        def GetTimelineByIndex(self, index): return rows[index - 1]

    stale = legacy_generated_timelines(Project(), keep=rows[0], canonical_name="New Reel - SUBS + KEYWORDS TIMELINE v1")
    assert [row.GetName() for row in stale] == ["RAMBLA_COMBINED_old"]


def test_every_boundary_moves_to_an_exact_timeline_timecode():
    class Timeline:
        def __init__(self): self.calls = []
        def SetCurrentTimecode(self, value): self.calls.append(value); return True

    timeline = Timeline()
    move_to_boundary(timeline, boundary=0, base_frame=108000, fps=30)
    assert timeline.calls == ["01:00:00:00"]

    timeline.SetCurrentTimecode = lambda _: False
    with pytest.raises(RuntimeError, match="boundary 30"):
        move_to_boundary(timeline, boundary=30, base_frame=108000, fps=30)


def test_find_timeline_media_item_searches_nested_bins_by_unique_id():
    class TimelineRef:
        def __init__(self, uid): self.uid = uid
        def GetUniqueId(self): return self.uid

    target = TimelineRef("wanted")

    class Clip:
        def __init__(self, timeline=None): self.timeline = timeline
        def GetTimeline(self): return self.timeline

    wanted_clip = Clip(TimelineRef("wanted"))

    class Folder:
        def __init__(self, clips=None, children=None): self.clips, self.children = clips or [], children or []
        def GetClipList(self): return self.clips
        def GetSubFolderList(self): return self.children

    root = Folder([Clip()], [Folder([wanted_clip])])
    class Pool:
        def GetRootFolder(self): return root

    assert find_timeline_media_item(Pool(), target) is wanted_clip


def test_next_timeline_name_increments_existing_named_versions():
    class TimelineRef:
        def __init__(self, name): self.name = name
        def GetName(self): return self.name

    rows = [
        TimelineRef("New Reel - SUBS + KEYWORDS TIMELINE v1"),
        TimelineRef("New Reel - SUBS + KEYWORDS TIMELINE v3"),
        TimelineRef("Other - SUBS + KEYWORDS TIMELINE v20"),
    ]
    class Project:
        def GetTimelineCount(self): return len(rows)
        def GetTimelineByIndex(self, index): return rows[index - 1]

    assert next_timeline_name(Project(), {"project_name": "New Reel", "mode": "combined"}) == "New Reel - SUBS + KEYWORDS TIMELINE v4"


def test_named_versions_are_not_legacy_cleanup_targets():
    class TimelineRef:
        def __init__(self, name): self.name = name
        def GetName(self): return self.name

    keep = TimelineRef("build")
    rows = [keep, TimelineRef("New Reel - SUBS + KEYWORDS TIMELINE v1"), TimelineRef("RAMBLA_COMBINED_old")]
    class Project:
        def GetTimelineCount(self): return len(rows)
        def GetTimelineByIndex(self, index): return rows[index - 1]

    stale = legacy_generated_timelines(Project(), keep=keep, canonical_name="unused", mode="combined")
    assert [row.GetName() for row in stale] == ["RAMBLA_COMBINED_old"]
def test_progress_file_lock_cannot_abort_timeline_build(monkeypatch):
    from backend.app import atomic_io
    from backend.app.resolve_textplus_timeline import report_handoff_progress
    def locked(*args):raise PermissionError('file in use')
    monkeypatch.setattr(atomic_io,'write_json',locked)
    report_handoff_progress({'handoff_progress_path':'test-progress.json'},'broll',82,'Clip 5/13')


def test_resolve_helper_cancellation_checkpoint_raises_when_cancel_file_exists(tmp_path):
    cancel = tmp_path / "cancel.request"
    cancel.write_text("cancel\n", encoding="utf-8")
    with pytest.raises(ResolveApplyCancelled, match="annullata"):
        raise_if_cancelled({"handoff_cancel_path": str(cancel)})

    cancel.unlink()
    raise_if_cancelled({"handoff_cancel_path": str(cancel)})


def test_broll_scaling_fills_the_frame_instead_of_overlaying_a_horizontal_strip():
    from backend.app.resolve_textplus_timeline import configure_broll_scaling
    from types import SimpleNamespace
    calls=[]
    item=SimpleNamespace(SetProperty=lambda values:calls.append(values) or True)
    configure_broll_scaling(item)
    assert calls==[{'Scaling':3}]


def test_staged_broll_reuses_identical_file_and_existing_conformed_excerpt(monkeypatch, tmp_path):
    """Retried application must not repeat minutes of FFmpeg work."""
    from backend.app.resolve_textplus_timeline import prepare_broll_media_files, conform_broll_media
    source = tmp_path / "downloaded" / "video.mp4"
    source.parent.mkdir()
    source.write_bytes(b"original video data")
    row = {
        "asset_id": "youtube:abc", "title": "A KURA clip", "provider": "youtube",
        "media_path": str(source), "record_start_frame": 10, "record_end_frame": 40,
        "source_start_frame": 60, "source_end_frame": 90,
    }
    calls = []
    monkeypatch.setattr("backend.app.resolve_textplus_timeline.probe_preview",
                        lambda _: {"duration": 8.0})
    def encode(command, **kwargs):
        calls.append(command)
        Path(command[-1]).write_bytes(b"encoded video")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr("backend.app.resolve_textplus_timeline.subprocess.run", encode)
    staging = tmp_path / "staging"
    first = prepare_broll_media_files([row], staging, "kura_media_v1")
    output1 = conform_broll_media(first, 30)
    assert len(calls) == 1
    second = prepare_broll_media_files([row], staging, "kura_media_v1")
    output2 = conform_broll_media(second, 30)
    assert second[0]["media_path"] == first[0]["media_path"]
    assert output2[0]["media_path"] == output1[0]["media_path"]
    assert len(calls) == 1


def test_staged_broll_does_not_reuse_different_source_with_same_readable_name(tmp_path):
    from backend.app.resolve_textplus_timeline import prepare_broll_media_files
    sources = []
    for name, data in [("a.mp4", b"clip one"), ("b.mp4", b"clip two")]:
        src = tmp_path / name
        src.write_bytes(data)
        sources.append({"media_path": str(src), "asset_id": name,
                        "title": "Same title", "provider": "pexels"})
    rows = prepare_broll_media_files(sources, tmp_path / "stage", "kura_media_v1")
    assert rows[0]["media_path"] != rows[1]["media_path"]
    assert Path(rows[0]["media_path"]).read_bytes() == b"clip one"
    assert Path(rows[1]["media_path"]).read_bytes() == b"clip two"
    rerun = prepare_broll_media_files(sources, tmp_path / "stage", "kura_media_v1")
    assert [x["media_path"] for x in rows] == [x["media_path"] for x in rerun]


def test_text_tool_tolerates_slow_fusion_initialization(monkeypatch):
    from backend.app.resolve_textplus_timeline import _text_tool
    template = SimpleNamespace(Name="Template")
    class Composition:
        def __init__(self):
            self.calls = 0
        def GetToolList(self, *_):
            self.calls += 1
            return {} if self.calls <= 25 else {1: template}
    composition = Composition()
    item = SimpleNamespace(GetFusionCompByIndex=lambda _: composition)
    monkeypatch.setattr("backend.app.resolve_textplus_timeline.time.sleep", lambda _: None)
    assert _text_tool(item) is template
    assert composition.calls == 26


def test_text_tool_reports_longer_timeout_not_original_five_seconds(monkeypatch):
    from backend.app.resolve_textplus_timeline import _text_tool
    item = SimpleNamespace(GetFusionCompByIndex=lambda _: None)
    monkeypatch.setattr("backend.app.resolve_textplus_timeline.time.sleep", lambda _: None)
    with pytest.raises(RuntimeError, match="20 secondi"):
        _text_tool(item)


def test_missing_fusion_title_is_repaired_before_video_conform(tmp_path):
    from zipfile import ZipFile
    from backend.app.resolve_textplus_timeline import ensure_resolve_title_ready
    from backend.app.resolve_title_templates import inspect_drfx, template_install_status
    title = "KURA_paper_title_v9"
    package = tmp_path / (title + ".drfx")
    with ZipFile(package, "w") as z:
        z.writestr("Edit/Titles/KURA/" + title + ".setting", "Tools = {}")
        z.writestr("Edit/Titles/KURA/paper.png", b"paper")
    destination = tmp_path / "ResolveTemplates"
    payload = {"title_package_path": str(package)}
    with pytest.raises(RuntimeError, match="riparato automaticamente"):
        ensure_resolve_title_ready(title, payload, install_root=destination)
    assert template_install_status(inspect_drfx(package), destination) == "installed"
    assert (destination / "Edit" / "Titles" / "KURA" / (title + ".setting")).is_file()
    # Once Resolve has been restarted, the same preflight succeeds unchanged.
    ensure_resolve_title_ready(title, payload, install_root=destination)


def test_missing_fusion_package_fails_before_media_work(tmp_path):
    from backend.app.resolve_textplus_timeline import ensure_resolve_title_ready
    with pytest.raises(RuntimeError, match="non presente"):
        ensure_resolve_title_ready("KURA_paper_title_v9",
                                  {"title_package_path": str(tmp_path / "missing.drfx")},
                                  install_root=tmp_path / "ResolveTemplates")


def test_fusion_install_never_substitutes_wrong_named_preset(tmp_path):
    from zipfile import ZipFile
    from backend.app.resolve_textplus_timeline import ensure_resolve_title_ready
    package = tmp_path / "other.drfx"
    with ZipFile(package, "w") as z:
        z.writestr("Edit/Titles/KURA/other.setting", "Tools = {}")
    with pytest.raises(RuntimeError, match="non corrisponde"):
        ensure_resolve_title_ready("KURA_paper_title_v9",
                                  {"title_package_path": str(package)},
                                  install_root=tmp_path / "ResolveTemplates")


def _stub_resolve_empty_title_preflight(monkeypatch, *, has_video=False):
    import sys
    from backend.app import resolve_textplus_timeline as mod

    class Timeline:
        def GetUniqueId(self):
            return "source-timeline-id"
        def GetSetting(self, key):
            assert key == "timelineFrameRate"
            return "30"
        def GetName(self):
            return "Timeline 1"
        def GetTrackCount(self, kind):
            return int(has_video) if kind == "video" else 0
        def GetItemListInTrack(self, kind, index):
            if kind == "video" and index == 1 and has_video:
                media = SimpleNamespace(GetClipProperty=lambda key: "Video")
                return [SimpleNamespace(GetMediaPoolItem=lambda: media)]
            return []

    timeline = Timeline()
    project = SimpleNamespace(GetName=lambda: "test kura v2",
                              GetTimelineCount=lambda: 1,
                              GetTimelineByIndex=lambda i: timeline)
    manager = SimpleNamespace(GetCurrentProject=lambda: project)
    resolve = SimpleNamespace(GetProjectManager=lambda: manager)
    monkeypatch.setitem(sys.modules, "DaVinciResolveScript",
                        SimpleNamespace(scriptapp=lambda name: resolve))
    return mod


def test_empty_active_timeline_is_rejected_before_ffmpeg_or_fusion(monkeypatch):
    mod = _stub_resolve_empty_title_preflight(monkeypatch)
    def should_not_run(*args, **kwargs):
        raise AssertionError("Expensive media processing should not start")
    monkeypatch.setattr(mod, "ensure_resolve_title_ready", should_not_run)
    monkeypatch.setattr(mod, "conform_broll_media", should_not_run)
    payload = {
        "source_project_name": "test kura v2",
        "source_timeline_id": "source-timeline-id",
        "destination_mode": "active",
        "mode": "editing",
        "components": {"highlights": True, "broll": True},
        "titles": [{"text": "Viaggiare insieme", "start_seconds": 0, "end_seconds": 1}],
        "title_name": "KURA_paper_title_v9",
    }
    with pytest.raises(RuntimeError, match="non contiene alcun video sorgente"):
        mod.materialize_in_resolve(payload)


def test_active_timeline_with_source_video_passes_early_preflight(monkeypatch):
    mod = _stub_resolve_empty_title_preflight(monkeypatch, has_video=True)
    def found_video(*args, **kwargs):
        raise RuntimeError("READY_TO_CHECK_FUSION_TEMPLATE")
    monkeypatch.setattr(mod, "ensure_resolve_title_ready", found_video)
    payload = {
        "source_project_name": "test kura v2",
        "source_timeline_id": "source-timeline-id",
        "destination_mode": "active",
        "mode": "editing",
        "components": {"highlights": True, "broll": True},
        "titles": [{"text": "Viaggiare insieme", "start_seconds": 0, "end_seconds": 1}],
        "title_name": "KURA_paper_title_v9",
    }
    with pytest.raises(RuntimeError, match="READY_TO_CHECK_FUSION_TEMPLATE"):
        mod.materialize_in_resolve(payload)
