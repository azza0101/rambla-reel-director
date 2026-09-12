"""Resolve-shaped mutation adapter compatible with the authenticated bridge proxy.

The upstream bridge deliberately exposes objects that look like the native
DaVinci Resolve Scripting API. This adapter therefore depends only on that
Resolve-shaped surface and an injected ``resolve_factory``. It never imports or
connects to the bridge by itself.

Live scope is intentionally narrow and fail-closed:
- B-roll: local media import + exact V2 placement.
- Captions: nested Text+ timeline + exact V3 placement.
- Punch-in: only when the requested range exactly matches one existing V1 clip.
- Other editorial mutations are rejected during preflight.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable


ResolveFactory = Callable[[], Any]
PathExists = Callable[[str], bool]


class BridgeResolveMutationAdapter:
    def __init__(
        self,
        *,
        resolve_factory: ResolveFactory,
        path_exists: PathExists | None = None,
    ) -> None:
        self.resolve_factory = resolve_factory
        self.path_exists = path_exists or (lambda value: Path(value).is_file())
        self._resolve: Any = None
        self._aux_by_target: dict[str, list[str]] = {}

    def _root(self) -> Any:
        if self._resolve is None:
            self._resolve = self.resolve_factory()
        if self._resolve is None:
            raise RuntimeError("Resolve bridge factory returned no Resolve object")
        return self._resolve

    def _project(self) -> Any:
        project = self._root().GetProjectManager().GetCurrentProject()
        if not project:
            raise RuntimeError("Resolve has no open project")
        return project

    @staticmethod
    def _normalize_name(value: str) -> str:
        return value.replace(" ", "_").casefold()

    def _timelines(self, project: Any | None = None) -> list[Any]:
        project = project or self._project()
        return [
            project.GetTimelineByIndex(index)
            for index in range(1, int(project.GetTimelineCount()) + 1)
        ]

    def _timeline(self, name: str, *, normalize: bool = False) -> Any:
        project = self._project()
        if normalize:
            wanted = self._normalize_name(name)
            matches = [
                timeline
                for timeline in self._timelines(project)
                if self._normalize_name(str(timeline.GetName())) == wanted
            ]
        else:
            matches = [timeline for timeline in self._timelines(project) if str(timeline.GetName()) == name]
        if len(matches) != 1:
            raise RuntimeError(f"expected exactly one timeline {name!r}, found {len(matches)}")
        return matches[0]

    @staticmethod
    def _absolute_range(timeline: Any, operation: dict[str, Any]) -> tuple[int, int]:
        start = int(operation.get("start_frame", -1))
        end = int(operation.get("end_frame", -1))
        if start < 0 or end <= start:
            raise ValueError("operation has invalid frame range")
        timeline_start = int(timeline.GetStartFrame())
        return timeline_start + start, timeline_start + end

    def _exact_items(self, timeline: Any, track_index: int, operation: dict[str, Any]) -> list[Any]:
        start, end = self._absolute_range(timeline, operation)
        return [
            item
            for item in (timeline.GetItemListInTrack("video", track_index) or [])
            if int(item.GetStart()) == start and int(item.GetEnd()) == end
        ]

    @staticmethod
    def _ensure_video_tracks(timeline: Any, count: int) -> None:
        while int(timeline.GetTrackCount("video")) < count:
            if timeline.AddTrack("video") is not True:
                raise RuntimeError(f"failed to create video track V{int(timeline.GetTrackCount('video')) + 1}")

    @staticmethod
    def _title_text(timeline: Any) -> str | None:
        for track in range(1, int(timeline.GetTrackCount("video")) + 1):
            for item in timeline.GetItemListInTrack("video", track) or []:
                if int(item.GetFusionCompCount() or 0) <= 0:
                    continue
                comp = item.GetFusionCompByIndex(1)
                tool = comp.FindTool("Template") if comp else None
                if tool:
                    value = tool.GetInput("StyledText")
                    return None if value is None else str(value)
        return None

    @staticmethod
    def _set_title_text(timeline: Any, text: str) -> bool:
        for track in range(1, int(timeline.GetTrackCount("video")) + 1):
            for item in timeline.GetItemListInTrack("video", track) or []:
                if int(item.GetFusionCompCount() or 0) <= 0:
                    continue
                comp = item.GetFusionCompByIndex(1)
                tool = comp.FindTool("Template") if comp else None
                if tool and tool.SetInput("StyledText", text):
                    return True
        return False

    @staticmethod
    def _caption_helper_name(operation: dict[str, Any]) -> str:
        key = str(operation.get("idempotency_key") or "")
        if not key:
            material = json.dumps(operation, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            key = hashlib.sha256(material.encode("utf-8")).hexdigest()
        safe = "".join(char for char in key if char.isalnum())[:12] or "caption"
        return f"RAMBLA_CAP_{safe}"

    def preflight(self, source_timeline: str, operations: list[dict[str, Any]]) -> dict[str, Any]:
        issues: list[str] = []
        try:
            source = self._timeline(source_timeline, normalize=True)
        except Exception as exc:
            return {"ok": False, "source_exists": False, "issues": [str(exc)]}

        for index, operation in enumerate(operations):
            kind = str(operation.get("kind") or "")
            prefix = f"operation[{index}] {kind or '<missing>'}: "
            try:
                self._absolute_range(source, operation)
            except (TypeError, ValueError) as exc:
                issues.append(prefix + str(exc))
                continue

            if kind == "PUNCH_IN":
                matches = self._exact_items(source, 1, operation)
                if len(matches) != 1:
                    issues.append(prefix + "PUNCH_IN requires one exact clip range on V1; partial clip zoom is unsafe")
                scale = float(operation.get("scale", 0.0))
                if scale <= 1.0:
                    issues.append(prefix + "scale must be greater than 1")
            elif kind == "INSERT_BROLL":
                path = str(operation.get("asset_path") or "").strip()
                if not path or not self.path_exists(path):
                    issues.append(prefix + "local B-roll asset is missing")
            elif kind == "CAPTION":
                if not str(operation.get("text") or "").strip():
                    issues.append(prefix + "caption text is empty")
            else:
                issues.append(prefix + "unsupported by verified live Resolve mapping")

        return {
            "ok": not issues,
            "source_exists": True,
            "issues": issues,
            "operation_count": len(operations),
        }

    def list_timeline_names(self) -> set[str]:
        return {str(timeline.GetName()) for timeline in self._timelines()}

    def duplicate_timeline(self, source_timeline: str, target_timeline: str) -> None:
        if target_timeline in self.list_timeline_names():
            raise RuntimeError(f"target timeline already exists: {target_timeline}")
        source = self._timeline(source_timeline, normalize=True)
        duplicate = source.DuplicateTimeline(target_timeline)
        if not duplicate or str(duplicate.GetName()) != target_timeline:
            raise RuntimeError("Resolve timeline duplication failed or returned an ambiguous target")

    def _apply_punch_in(self, timeline: Any, operation: dict[str, Any]) -> dict[str, Any]:
        matches = self._exact_items(timeline, 1, operation)
        if len(matches) != 1:
            raise RuntimeError("PUNCH_IN no longer matches exactly one V1 clip")
        clip = matches[0]
        scale = float(operation["scale"])
        if clip.SetProperty("ZoomX", scale) is not True or clip.SetProperty("ZoomY", scale) is not True:
            raise RuntimeError("Resolve rejected PUNCH_IN transform")
        return {"ok": True, "kind": "PUNCH_IN", "clip": str(clip.GetName())}

    def _apply_broll(self, project: Any, timeline: Any, operation: dict[str, Any]) -> dict[str, Any]:
        media_pool = project.GetMediaPool()
        path = str(operation["asset_path"])
        imported = media_pool.ImportMedia([path]) or []
        if len(imported) != 1:
            raise RuntimeError("Resolve did not import exactly one B-roll asset")
        self._ensure_video_tracks(timeline, 2)
        if project.SetCurrentTimeline(timeline) is not True:
            raise RuntimeError("failed to select generated timeline before B-roll placement")
        start, end = self._absolute_range(timeline, operation)
        duration = end - start
        placed = media_pool.AppendToTimeline(
            [
                {
                    "mediaPoolItem": imported[0],
                    "startFrame": 0,
                    "endFrame": duration,
                    "mediaType": 1,
                    "trackIndex": 2,
                    "recordFrame": start,
                }
            ]
        ) or []
        if len(placed) != 1:
            raise RuntimeError("Resolve did not place exactly one B-roll timeline item")
        item = placed[0]
        if int(item.GetStart()) != start or int(item.GetDuration()) != duration:
            raise RuntimeError("B-roll placement readback does not match requested range")
        return {"ok": True, "kind": "INSERT_BROLL", "start": start, "duration": duration}

    def _apply_caption(self, project: Any, timeline: Any, operation: dict[str, Any]) -> dict[str, Any]:
        media_pool = project.GetMediaPool()
        helper_name = self._caption_helper_name(operation)
        if helper_name in self.list_timeline_names():
            raise RuntimeError(f"caption helper timeline already exists: {helper_name}")
        helper = media_pool.CreateEmptyTimeline(helper_name)
        if not helper:
            raise RuntimeError("failed to create caption helper timeline")
        self._aux_by_target.setdefault(str(timeline.GetName()), []).append(helper_name)
        if project.SetCurrentTimeline(helper) is not True:
            raise RuntimeError("failed to select caption helper timeline")
        title = helper.InsertFusionTitleIntoTimeline("Text+")
        if not title or not self._set_title_text(helper, str(operation["text"])):
            raise RuntimeError("failed to create/edit Text+ caption helper")
        media_item = helper.GetMediaPoolItem()
        if not media_item:
            raise RuntimeError("caption helper has no Media Pool item")

        self._ensure_video_tracks(timeline, 3)
        if project.SetCurrentTimeline(timeline) is not True:
            raise RuntimeError("failed to restore generated timeline before caption placement")
        start, end = self._absolute_range(timeline, operation)
        duration = end - start
        placed = media_pool.AppendToTimeline(
            [
                {
                    "mediaPoolItem": media_item,
                    "startFrame": 0,
                    "endFrame": duration,
                    "trackIndex": 3,
                    "recordFrame": start,
                }
            ]
        ) or []
        if len(placed) != 1:
            raise RuntimeError("Resolve did not place exactly one caption timeline item")
        item = placed[0]
        if int(item.GetStart()) != start or int(item.GetDuration()) != duration:
            raise RuntimeError("caption placement readback does not match requested range")
        return {"ok": True, "kind": "CAPTION", "helper_timeline": helper_name}

    def apply_operation(self, target_timeline: str, operation: dict[str, Any]) -> dict[str, Any]:
        project = self._project()
        timeline = self._timeline(target_timeline)
        kind = str(operation.get("kind") or "")
        if kind == "PUNCH_IN":
            return self._apply_punch_in(timeline, operation)
        if kind == "INSERT_BROLL":
            return self._apply_broll(project, timeline, operation)
        if kind == "CAPTION":
            return self._apply_caption(project, timeline, operation)
        raise RuntimeError(f"unsupported live Resolve operation: {kind}")

    def _verify_punch_in(self, timeline: Any, operation: dict[str, Any]) -> bool:
        matches = self._exact_items(timeline, 1, operation)
        if len(matches) != 1:
            return False
        props = matches[0].GetProperty() or {}
        scale = float(operation["scale"])
        return abs(float(props.get("ZoomX", 0.0)) - scale) < 1e-6 and abs(float(props.get("ZoomY", 0.0)) - scale) < 1e-6

    def _verify_placement(self, timeline: Any, track: int, operation: dict[str, Any]) -> Any | None:
        matches = self._exact_items(timeline, track, operation)
        return matches[0] if len(matches) == 1 else None

    def verify_operations(self, target_timeline: str, operations: list[dict[str, Any]]) -> dict[str, Any]:
        timeline = self._timeline(target_timeline)
        checks: list[dict[str, Any]] = []
        for operation in operations:
            kind = str(operation.get("kind") or "")
            if kind == "PUNCH_IN":
                ok = self._verify_punch_in(timeline, operation)
            elif kind == "INSERT_BROLL":
                ok = self._verify_placement(timeline, 2, operation) is not None
            elif kind == "CAPTION":
                item = self._verify_placement(timeline, 3, operation)
                nested = item.GetMediaPoolItem().GetTimeline() if item and item.GetMediaPoolItem() else None
                ok = bool(nested and self._title_text(nested) == str(operation.get("text") or ""))
            else:
                ok = False
            checks.append({"kind": kind, "ok": bool(ok)})
        return {"ok": all(row["ok"] for row in checks), "checks": checks, "operation_count": len(operations)}

    def discard_timeline(self, target_timeline: str) -> None:
        project = self._project()
        media_pool = project.GetMediaPool()
        names = [target_timeline, *self._aux_by_target.pop(target_timeline, [])]
        timelines: list[Any] = []
        for name in names:
            matches = [timeline for timeline in self._timelines(project) if str(timeline.GetName()) == name]
            timelines.extend(matches)
        if timelines and media_pool.DeleteTimelines(timelines) is not True:
            raise RuntimeError("Resolve failed to delete generated rollback timelines")
        leftovers = set(names) & self.list_timeline_names()
        if leftovers:
            raise RuntimeError(f"Resolve rollback left generated timelines behind: {sorted(leftovers)}")
