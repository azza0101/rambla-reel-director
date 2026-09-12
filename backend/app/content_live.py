"""Minimal persisted, duplicate-only live B-roll slice over a supplied bridge proxy."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

from .resolve_live import allocate_generated_name, is_source_timeline


def frame_range(timeline_start: int, fps: int, start: float, end: float) -> tuple[int, int]:
    if fps <= 0 or start < 0 or end <= start:
        raise ValueError("invalid timeline B-roll range")
    result = (timeline_start + math.floor(start * fps + 0.5), timeline_start + math.floor(end * fps + 0.5))
    if result[1] <= result[0]:
        raise ValueError("B-roll interval is shorter than one frame")
    return result


def source_fingerprint(snapshot: dict[str, Any]) -> str:
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def save_verified_project(
    save: Callable[[], bool],
    read_source: Callable[[], dict[str, Any]],
    expected_source: dict[str, Any],
) -> bool:
    if not save():
        raise RuntimeError("Resolve project save failed")
    if read_source() != expected_source:
        raise RuntimeError("source changed during project save")
    return True


def validate_video_probe(probe: dict[str, Any], *, expected_frames: int, fps: int) -> int:
    videos = [stream for stream in probe.get("streams", []) if stream.get("codec_type") == "video"]
    if len(videos) != 1:
        raise ValueError("expected exactly one video stream for B-roll")
    stream = videos[0]
    if Fraction(stream.get("r_frame_rate", "0/1")) != fps:
        raise ValueError("B-roll frame rate does not match timeline")
    frames = int(stream.get("nb_frames") or 0)
    if frames != expected_frames:
        raise ValueError("B-roll video frame count does not match planned range")
    return frames


def _probe_video(path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,nb_frames,r_frame_rate,pix_fmt", "-of", "json", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _timeline_snapshot(timeline: Any) -> dict[str, Any]:
    def clips(kind: str) -> list[dict[str, Any]]:
        rows = []
        for index in range(1, int(timeline.GetTrackCount(kind)) + 1):
            for clip in timeline.GetItemListInTrack(kind, index) or []:
                row = {
                    "track": index,
                    "id": clip.GetUniqueId(),
                    "name": clip.GetName(),
                    "start": int(clip.GetStart()),
                    "end": int(clip.GetEnd()),
                }
                if kind == "video":
                    properties = clip.GetProperty()
                    row["transform"] = {
                        key: properties.get(key)
                        for key in ("ZoomX", "ZoomY", "Pan", "Tilt", "AnchorPointX", "AnchorPointY")
                    }
                rows.append(row)
        return rows

    return {
        "timeline_id": timeline.GetUniqueId(),
        "name": timeline.GetName(),
        "start": int(timeline.GetStartFrame()),
        "end": int(timeline.GetEndFrame()),
        "fps": float(timeline.GetSetting("timelineFrameRate")),
        "video_tracks": int(timeline.GetTrackCount("video")),
        "audio_tracks": int(timeline.GetTrackCount("audio")),
        "video": clips("video"),
        "audio": clips("audio"),
    }


def _source(project: Any) -> Any:
    matches = [
        project.GetTimelineByIndex(index)
        for index in range(1, int(project.GetTimelineCount()) + 1)
        if is_source_timeline(project.GetTimelineByIndex(index).GetName())
    ]
    if len(matches) != 1:
        raise RuntimeError("expected exactly one REEL MASTER timeline")
    return matches[0]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_broll_plan(resolve: Any, plan_path: Path, asset_path: Path) -> dict[str, Any]:
    if plan_path.exists():
        raise RuntimeError("Edit Plan path already exists")
    asset_path = asset_path.resolve(strict=True)
    project = resolve.GetProjectManager().GetCurrentProject()
    if not project or project.GetName().casefold() != "test-mcp":
        raise RuntimeError("unexpected Resolve project")
    source = _source(project)
    before = _timeline_snapshot(source)
    if len(before["video"]) != 1 or len(before["audio"]) != 1:
        raise RuntimeError("source timeline no longer has one V1 and one A1 clip")
    if before["video"][0]["track"] != 1 or before["audio"][0]["track"] != 1:
        raise RuntimeError("source clip track layout changed")
    start, end = frame_range(before["start"], int(before["fps"]), 54.4, 58.9)
    if end > before["end"]:
        raise RuntimeError("B-roll range exceeds source timeline")
    asset_frames = validate_video_probe(_probe_video(asset_path), expected_frames=end - start, fps=int(before["fps"]))
    names_before = [project.GetTimelineByIndex(i).GetName() for i in range(1, int(project.GetTimelineCount()) + 1)]
    target_name = allocate_generated_name(set(names_before))
    plan = {
        "schema_version": "content-sprint-0.1",
        "status": "DRAFT",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project": project.GetName(),
        "source": before,
        "source_sha256": source_fingerprint(before),
        "target_name": target_name,
        "decision": {
            "action": "BROLL",
            "intent": "Show the actual local node workflow during the spoken workflow passage",
            "asset_path": str(asset_path),
            "asset_sha256": _sha256_file(asset_path),
            "asset_frames": asset_frames,
            "track": 2,
            "start_frame": start,
            "end_frame": end,
            "source_start_frame": 0,
            "source_end_frame": end - start,
            "media_type": 1,
        },
    }
    if _timeline_snapshot(source) != before or [project.GetTimelineByIndex(i).GetName() for i in range(1, int(project.GetTimelineCount()) + 1)] != names_before:
        raise RuntimeError("Resolve changed during B-roll Dry Run")
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return plan


def apply_broll_plan(resolve: Any, plan_path: Path) -> dict[str, Any]:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("status") != "DRAFT" or plan.get("decision", {}).get("action") != "BROLL":
        raise RuntimeError("expected a DRAFT BROLL Edit Plan")
    report_path = plan_path.with_suffix(".apply.json")
    started_path = plan_path.with_suffix(".started.json")
    if report_path.exists() or started_path.exists():
        raise RuntimeError("Apply already started; refusing retry")
    project = resolve.GetProjectManager().GetCurrentProject()
    if not project or project.GetName() != plan["project"]:
        raise RuntimeError("Resolve project changed after Dry Run")
    source = _source(project)
    before = _timeline_snapshot(source)
    if before != plan["source"] or source_fingerprint(before) != plan["source_sha256"]:
        raise RuntimeError("REEL MASTER changed after Dry Run")
    names = {project.GetTimelineByIndex(i).GetName() for i in range(1, int(project.GetTimelineCount()) + 1)}
    if plan["target_name"] in names or allocate_generated_name(names) != plan["target_name"]:
        raise RuntimeError("target timeline name is no longer collision-safe; make a new plan")
    decision = plan["decision"]
    asset_path = Path(decision["asset_path"])
    if _sha256_file(asset_path) != decision["asset_sha256"]:
        raise RuntimeError("B-roll asset changed after Dry Run")
    if not hasattr(source, "DuplicateTimeline"):
        raise RuntimeError("Resolve cannot duplicate the source timeline")
    started_path.write_text(json.dumps({"status": "STARTED", "target_name": plan["target_name"]}) + "\n", encoding="utf-8")
    duplicate = source.DuplicateTimeline(plan["target_name"])
    if not duplicate or duplicate.GetName() != plan["target_name"] or duplicate.GetUniqueId() == source.GetUniqueId():
        raise RuntimeError("timeline duplication ambiguous; no retry")
    if not project.SetCurrentTimeline(duplicate):
        raise RuntimeError("could not select duplicate timeline; no retry")
    if _timeline_snapshot(source) != before:
        raise RuntimeError("source changed after duplication; no retry")
    if int(duplicate.GetTrackCount("video")) != 1 or not duplicate.AddTrack("video"):
        raise RuntimeError("could not create V2 on duplicate; no retry")
    pool = project.GetMediaPool()
    imported = pool.ImportMedia([str(asset_path)]) or []
    if len(imported) != 1:
        raise RuntimeError("B-roll import ambiguous; no retry")
    appended = pool.AppendToTimeline([{
        "mediaPoolItem": imported[0],
        "startFrame": decision["source_start_frame"],
        "endFrame": decision["source_end_frame"],
        "mediaType": decision["media_type"],
        "trackIndex": decision["track"],
        "recordFrame": decision["start_frame"],
    }]) or []
    v2 = duplicate.GetItemListInTrack("video", 2) or []
    source_after = _timeline_snapshot(source)
    target_ok = len(v2) == 1 and v2[0].GetName() == asset_path.name and int(v2[0].GetStart()) == decision["start_frame"] and int(v2[0].GetEnd()) == decision["end_frame"]
    if len(appended) == 1 and target_ok and source_after == before:
        try:
            saved = save_verified_project(resolve.GetProjectManager().SaveProject, lambda: _timeline_snapshot(source), before)
        except RuntimeError as exc:
            saved = False
            save_error = str(exc)
    else:
        saved = False
        save_error = None
    source_after = _timeline_snapshot(source)
    report = {
        "status": "SUCCEEDED" if len(appended) == 1 and target_ok and source_after == before and saved else "AMBIGUOUS",
        "target_name": duplicate.GetName(),
        "target_id": duplicate.GetUniqueId(),
        "target_v2": [{"name": clip.GetName(), "start": int(clip.GetStart()), "end": int(clip.GetEnd())} for clip in v2],
        "source_unchanged": source_after == before,
        "project_saved": saved,
        "save_error": save_error if not saved else None,
        "transport": "bridge-only",
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if report["status"] != "SUCCEEDED":
        raise RuntimeError(f"B-roll Apply ambiguous; no retry: {report}")
    return report
