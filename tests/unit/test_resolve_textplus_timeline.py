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
import shutil
import uuid

from backend.app.resolve_textplus_timeline import (
    boundary_operations,
    build_textplus_timeline_plan,
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
)


def test_active_rambla_timeline_is_rebuilt_after_backup_instead_of_duplicating_generated_items():
    assert should_rebuild_active_timeline("active", "Client - SUBS + KEYWORDS + B-ROLL TIMELINE v2")
    assert not should_rebuild_active_timeline("active", "Client master edit")
    assert not should_rebuild_active_timeline("new", "Client - SUBS + KEYWORDS TIMELINE v1")


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


def test_boundary_operations_attach_text_only_to_requested_starts():
    plan = build_textplus_timeline_plan(payload(), target_fps=30)

    assert boundary_operations(plan) == [
        {"frame": 15, "text": "due tre"},
        {"frame": 45, "text": None},
        {"frame": 120, "text": "Otto"},
        {"frame": 135, "text": None},
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


def test_selected_title_name_is_required_and_preserved():
    assert title_name_from_payload({"title_name": "KURA_paper_title_v8"}) == "KURA_paper_title_v8"

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


def test_helper_tolerates_non_utf8_native_resolve_diagnostics(monkeypatch):
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
