"""One-shot caption overlay Apply to a verified generated Resolve timeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .captions import validate_caption_target, validate_overlay_probe
from .content_live import _probe_video, _sha256_file, _source, _timeline_snapshot, save_verified_project, source_fingerprint


def _target(project: Any, name: str) -> Any:
    matches = [
        project.GetTimelineByIndex(index)
        for index in range(1, int(project.GetTimelineCount()) + 1)
        if project.GetTimelineByIndex(index).GetName() == name
    ]
    if len(matches) != 1:
        raise RuntimeError("expected exactly one generated caption target")
    return matches[0]


def prepare_caption_plan(
    resolve: Any,
    plan_path: Path,
    overlay_path: Path,
    srt_path: Path,
) -> dict[str, Any]:
    if plan_path.exists():
        raise RuntimeError("caption Edit Plan already exists")
    overlay_path = overlay_path.resolve(strict=True)
    srt_path = srt_path.resolve(strict=True)
    project = resolve.GetProjectManager().GetCurrentProject()
    if not project or project.GetName().casefold() != "test-mcp":
        raise RuntimeError("unexpected Resolve project")
    source = _source(project)
    target = _target(project, "REEL_AI_v06")
    source_before = _timeline_snapshot(source)
    target_before = _timeline_snapshot(target)
    validate_caption_target(source_before, target_before, name="REEL_AI_v06", broll_start=91360, broll_end=91473)
    if target_before["video_tracks"] != 2 or target_before["audio_tracks"] != 1:
        raise RuntimeError("caption target track layout changed")
    validate_overlay_probe(_probe_video(overlay_path), expected_frames=113, fps=25)
    plan = {
        "schema_version": "content-sprint-0.1",
        "status": "DRAFT",
        "project": project.GetName(),
        "source": source_before,
        "source_sha256": source_fingerprint(source_before),
        "target": target_before,
        "target_sha256": source_fingerprint(target_before),
        "decision": {
            "action": "CAPTION_OVERLAY",
            "text": "WORKFLOW NODI",
            "transcript_srt": str(srt_path),
            "transcript_srt_sha256": _sha256_file(srt_path),
            "asset_path": str(overlay_path),
            "asset_sha256": _sha256_file(overlay_path),
            "track": 3,
            "start_frame": 91360,
            "end_frame": 91473,
            "source_start_frame": 0,
            "source_end_frame": 113,
        },
    }
    if _timeline_snapshot(source) != source_before or _timeline_snapshot(target) != target_before:
        raise RuntimeError("Resolve changed during caption Dry Run")
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return plan


def apply_caption_plan(resolve: Any, plan_path: Path) -> dict[str, Any]:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("status") != "DRAFT" or plan.get("decision", {}).get("action") != "CAPTION_OVERLAY":
        raise RuntimeError("expected DRAFT caption Edit Plan")
    started_path = plan_path.with_suffix(".started.json")
    report_path = plan_path.with_suffix(".apply.json")
    if started_path.exists() or report_path.exists():
        raise RuntimeError("caption Apply already started; refusing retry")
    project = resolve.GetProjectManager().GetCurrentProject()
    if not project or project.GetName() != plan["project"]:
        raise RuntimeError("Resolve project changed after caption plan")
    source = _source(project)
    target = _target(project, "REEL_AI_v06")
    source_before = _timeline_snapshot(source)
    target_before = _timeline_snapshot(target)
    if source_before != plan["source"] or source_fingerprint(source_before) != plan["source_sha256"]:
        raise RuntimeError("REEL MASTER changed after caption plan")
    if target_before != plan["target"] or source_fingerprint(target_before) != plan["target_sha256"]:
        raise RuntimeError("caption target changed after plan")
    validate_caption_target(source_before, target_before, name="REEL_AI_v06", broll_start=91360, broll_end=91473)
    decision = plan["decision"]
    overlay_path = Path(decision["asset_path"])
    if _sha256_file(overlay_path) != decision["asset_sha256"] or _sha256_file(Path(decision["transcript_srt"])) != decision["transcript_srt_sha256"]:
        raise RuntimeError("caption asset or SRT changed after Dry Run")
    validate_overlay_probe(_probe_video(overlay_path), expected_frames=113, fps=25)
    started_path.write_text(json.dumps({"target": "REEL_AI_v06", "started": True}) + "\n", encoding="utf-8")
    if not project.SetCurrentTimeline(target) or not target.AddTrack("video"):
        raise RuntimeError("could not select generated timeline or add V3; no retry")
    if _timeline_snapshot(source) != source_before:
        raise RuntimeError("source changed before caption insertion; no retry")
    pool = project.GetMediaPool()
    items = pool.ImportMedia([str(overlay_path)]) or []
    if len(items) != 1:
        raise RuntimeError("caption import ambiguous; no retry")
    returned = pool.AppendToTimeline([{
        "mediaPoolItem": items[0],
        "startFrame": decision["source_start_frame"],
        "endFrame": decision["source_end_frame"],
        "mediaType": 1,
        "trackIndex": decision["track"],
        "recordFrame": decision["start_frame"],
    }]) or []
    after = _timeline_snapshot(target)
    source_after = _timeline_snapshot(source)
    v2 = [clip for clip in after["video"] if clip["track"] == 2]
    v3 = [clip for clip in after["video"] if clip["track"] == 3]
    exact = len(v3) == 1 and v3[0]["name"] == overlay_path.name and v3[0]["start"] == 91360 and v3[0]["end"] == 91473
    broll_preserved = len(v2) == 1 and v2[0]["name"] == "workflow-113f.mp4" and v2[0]["start"] == 91360 and v2[0]["end"] == 91473
    if len(returned) == 1 and exact and broll_preserved and source_after == source_before:
        try:
            saved = save_verified_project(resolve.GetProjectManager().SaveProject, lambda: _timeline_snapshot(source), source_before)
        except RuntimeError as exc:
            saved = False
            save_error = str(exc)
    else:
        saved = False
        save_error = None
    source_after = _timeline_snapshot(source)
    report = {
        "status": "SUCCEEDED" if len(returned) == 1 and exact and broll_preserved and source_after == source_before and saved else "AMBIGUOUS",
        "target_name": target.GetName(),
        "target_id": target.GetUniqueId(),
        "target_v2": v2,
        "target_v3": v3,
        "source_unchanged": source_after == source_before,
        "project_saved": saved,
        "save_error": save_error if not saved else None,
        "transport": "bridge-only",
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if report["status"] != "SUCCEEDED":
        raise RuntimeError(f"caption Apply ambiguous; no retry: {report}")
    return report
