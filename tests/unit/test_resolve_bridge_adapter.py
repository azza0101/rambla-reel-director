from __future__ import annotations

import pytest

from backend.app.resolve_bridge_adapter import BridgeResolveMutationAdapter


class FakeFusionTool:
    def __init__(self) -> None:
        self.inputs = {"StyledText": ""}

    def SetInput(self, name: str, value: str) -> bool:
        self.inputs[name] = value
        return True

    def GetInput(self, name: str):
        return self.inputs.get(name)


class FakeFusionComp:
    def __init__(self) -> None:
        self.template = FakeFusionTool()

    def FindTool(self, name: str):
        return self.template if name == "Template" else None


class FakeMediaPoolItem:
    def __init__(self, path: str = "", *, timeline=None) -> None:
        self.path = path
        self.timeline = timeline

    def GetTimeline(self):
        return self.timeline

    def GetClipProperty(self, name: str | None = None):
        props = {"File Path": self.path, "FPS": "24"}
        return props.get(name) if name else props


class FakeTimelineItem:
    def __init__(self, name: str, start: int, end: int, *, mpi=None, fusion=False) -> None:
        self.name = name
        self.start = start
        self.end = end
        self.mpi = mpi
        self.fusion = FakeFusionComp() if fusion else None
        self.properties = {
            "ZoomX": 1.0,
            "ZoomY": 1.0,
            "Pan": 0.0,
            "Tilt": 0.0,
            "AnchorPointX": 0.0,
            "AnchorPointY": 0.0,
        }

    def GetName(self) -> str:
        return self.name

    def GetStart(self) -> int:
        return self.start

    def GetEnd(self) -> int:
        return self.end

    def GetDuration(self) -> int:
        return self.end - self.start

    def GetProperty(self, name: str | None = None):
        return self.properties.get(name) if name else dict(self.properties)

    def SetProperty(self, name: str, value) -> bool:
        self.properties[name] = value
        return True

    def GetMediaPoolItem(self):
        return self.mpi

    def GetFusionCompCount(self) -> int:
        return 1 if self.fusion is not None else 0

    def GetFusionCompByIndex(self, index: int):
        return self.fusion if index == 1 else None


class FakeTimeline:
    def __init__(self, project, name: str, *, start_frame: int = 86400, source_clip: bool = False) -> None:
        self.project = project
        self.name = name
        self.start_frame = start_frame
        self.tracks: dict[int, list[FakeTimelineItem]] = {1: []}
        if source_clip:
            self.tracks[1].append(FakeTimelineItem("A001", start_frame, start_frame + 96))

    def GetName(self) -> str:
        return self.name

    def GetStartFrame(self) -> int:
        return self.start_frame

    def GetTrackCount(self, track_type: str) -> int:
        assert track_type == "video"
        return max(self.tracks) if self.tracks else 0

    def AddTrack(self, track_type: str) -> bool:
        assert track_type == "video"
        self.tracks[self.GetTrackCount("video") + 1] = []
        return True

    def GetItemListInTrack(self, track_type: str, index: int):
        assert track_type == "video"
        return list(self.tracks.get(index, []))

    def DuplicateTimeline(self, new_name: str):
        clone = FakeTimeline(self.project, new_name, start_frame=self.start_frame)
        clone.tracks = {
            index: [
                FakeTimelineItem(item.name, item.start, item.end, mpi=item.mpi, fusion=item.fusion is not None)
                for item in items
            ]
            for index, items in self.tracks.items()
        }
        for index, items in self.tracks.items():
            for source, copied in zip(items, clone.tracks[index]):
                copied.properties = dict(source.properties)
                if source.fusion and copied.fusion:
                    copied.fusion.template.inputs = dict(source.fusion.template.inputs)
        self.project.timelines.append(clone)
        return clone

    def InsertFusionTitleIntoTimeline(self, title_name: str):
        assert title_name == "Text+"
        item = FakeTimelineItem("Text+", self.start_frame, self.start_frame + 100, fusion=True)
        self.tracks.setdefault(1, []).append(item)
        return item

    def GetMediaPoolItem(self):
        return FakeMediaPoolItem(timeline=self)


class FakeMediaPool:
    def __init__(self, project) -> None:
        self.project = project
        self.imported: list[str] = []

    def ImportMedia(self, paths: list[str]):
        self.imported.extend(paths)
        return [FakeMediaPoolItem(path) for path in paths]

    def AppendToTimeline(self, rows: list[dict]):
        timeline = self.project.current
        output = []
        for row in rows:
            track = int(row.get("trackIndex", 1))
            while timeline.GetTrackCount("video") < track:
                timeline.AddTrack("video")
            start = int(row["recordFrame"])
            duration = int(row["endFrame"] - row["startFrame"])
            item = FakeTimelineItem(
                "placed",
                start,
                start + duration,
                mpi=row["mediaPoolItem"],
            )
            timeline.tracks[track].append(item)
            output.append(item)
        return output

    def CreateEmptyTimeline(self, name: str):
        if any(timeline.GetName() == name for timeline in self.project.timelines):
            return None
        timeline = FakeTimeline(self.project, name, start_frame=0)
        self.project.timelines.append(timeline)
        return timeline

    def DeleteTimelines(self, timelines: list[FakeTimeline]) -> bool:
        remove = set(timelines)
        self.project.timelines = [timeline for timeline in self.project.timelines if timeline not in remove]
        if self.project.current in remove:
            self.project.current = self.project.timelines[0] if self.project.timelines else None
        return True


class FakeProject:
    def __init__(self) -> None:
        self.timelines: list[FakeTimeline] = []
        self.media_pool = FakeMediaPool(self)
        source = FakeTimeline(self, "REEL_MASTER", source_clip=True)
        self.timelines.append(source)
        self.current = source

    def GetName(self) -> str:
        return "Project"

    def GetTimelineCount(self) -> int:
        return len(self.timelines)

    def GetTimelineByIndex(self, index: int):
        return self.timelines[index - 1]

    def GetCurrentTimeline(self):
        return self.current

    def SetCurrentTimeline(self, timeline) -> bool:
        self.current = timeline
        return True

    def GetMediaPool(self):
        return self.media_pool


class FakeProjectManager:
    def __init__(self, project: FakeProject) -> None:
        self.project = project

    def GetCurrentProject(self):
        return self.project


class FakeResolve:
    def __init__(self) -> None:
        self.project = FakeProject()
        self.manager = FakeProjectManager(self.project)

    def GetProjectManager(self):
        return self.manager


def _adapter(resolve: FakeResolve) -> BridgeResolveMutationAdapter:
    return BridgeResolveMutationAdapter(resolve_factory=lambda: resolve, path_exists=lambda _: True)


def test_preflight_rejects_partial_range_punch_in_instead_of_zooming_whole_clip() -> None:
    resolve = FakeResolve()
    adapter = _adapter(resolve)

    result = adapter.preflight(
        "REEL_MASTER",
        [{"kind": "PUNCH_IN", "start_frame": 24, "end_frame": 48, "scale": 1.08}],
    )

    assert result["ok"] is False
    assert result["source_exists"] is True
    assert any("exact clip range" in issue for issue in result["issues"])
    source = resolve.project.timelines[0].tracks[1][0]
    assert source.GetProperty("ZoomX") == 1.0


def test_exact_range_punch_in_can_be_applied_and_verified_on_duplicate() -> None:
    resolve = FakeResolve()
    adapter = _adapter(resolve)
    operation = {"kind": "PUNCH_IN", "start_frame": 0, "end_frame": 96, "scale": 1.08}

    assert adapter.preflight("REEL_MASTER", [operation])["ok"] is True
    adapter.duplicate_timeline("REEL_MASTER", "REEL_AI_v01")
    assert adapter.apply_operation("REEL_AI_v01", operation)["ok"] is True
    verified = adapter.verify_operations("REEL_AI_v01", [operation])

    target = next(tl for tl in resolve.project.timelines if tl.GetName() == "REEL_AI_v01")
    clip = target.tracks[1][0]
    assert clip.GetProperty("ZoomX") == pytest.approx(1.08)
    assert clip.GetProperty("ZoomY") == pytest.approx(1.08)
    assert verified["ok"] is True


def test_broll_import_is_placed_on_v2_at_exact_record_frame_and_duration() -> None:
    resolve = FakeResolve()
    adapter = _adapter(resolve)
    operation = {
        "kind": "INSERT_BROLL",
        "start_frame": 24,
        "end_frame": 72,
        "asset_path": "C:/cache/evidence.mp4",
        "asset_id": "youtube:abc",
    }

    assert adapter.preflight("REEL_MASTER", [operation])["ok"] is True
    adapter.duplicate_timeline("REEL_MASTER", "REEL_AI_v01")
    assert adapter.apply_operation("REEL_AI_v01", operation)["ok"] is True

    target = next(tl for tl in resolve.project.timelines if tl.GetName() == "REEL_AI_v01")
    item = target.tracks[2][0]
    assert resolve.project.media_pool.imported == ["C:/cache/evidence.mp4"]
    assert item.GetStart() == 86424
    assert item.GetDuration() == 48
    assert adapter.verify_operations("REEL_AI_v01", [operation])["ok"] is True


def test_caption_uses_nested_text_plus_on_v3_with_exact_range_and_text() -> None:
    resolve = FakeResolve()
    adapter = _adapter(resolve)
    operation = {
        "kind": "CAPTION",
        "start_frame": 0,
        "end_frame": 48,
        "caption_index": 0,
        "text": "Ciao mondo",
        "idempotency_key": "cap-key-001",
    }

    assert adapter.preflight("REEL_MASTER", [operation])["ok"] is True
    adapter.duplicate_timeline("REEL_MASTER", "REEL_AI_v01")
    assert adapter.apply_operation("REEL_AI_v01", operation)["ok"] is True

    target = next(tl for tl in resolve.project.timelines if tl.GetName() == "REEL_AI_v01")
    placed = target.tracks[3][0]
    inner = placed.GetMediaPoolItem().GetTimeline()
    title = inner.tracks[1][0].GetFusionCompByIndex(1).FindTool("Template")
    assert placed.GetStart() == 86400
    assert placed.GetDuration() == 48
    assert title.GetInput("StyledText") == "Ciao mondo"
    assert adapter.verify_operations("REEL_AI_v01", [operation])["ok"] is True


def test_discard_target_also_removes_owned_caption_helper_timelines() -> None:
    resolve = FakeResolve()
    adapter = _adapter(resolve)
    operation = {
        "kind": "CAPTION",
        "start_frame": 0,
        "end_frame": 48,
        "caption_index": 0,
        "text": "Ciao mondo",
        "idempotency_key": "cap-key-001",
    }
    adapter.duplicate_timeline("REEL_MASTER", "REEL_AI_v01")
    adapter.apply_operation("REEL_AI_v01", operation)
    assert len(adapter.list_timeline_names()) == 3

    adapter.discard_timeline("REEL_AI_v01")

    assert adapter.list_timeline_names() == {"REEL_MASTER"}


def test_preflight_rejects_editorial_operations_without_verified_live_mapping() -> None:
    resolve = FakeResolve()
    adapter = _adapter(resolve)

    result = adapter.preflight(
        "REEL_MASTER",
        [{"kind": "CAPTION_EMPHASIS", "start_frame": 0, "end_frame": 24, "text": "ciao"}],
    )

    assert result["ok"] is False
    assert any("unsupported" in issue.lower() for issue in result["issues"])
