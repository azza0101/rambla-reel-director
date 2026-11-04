"""One-shot Resolve materialization of the uploaded, already edited video.

Creates an owned timeline from the entire original file, optionally adds the
regular B-roll/captions/title overlays, and rolls back that new timeline on
failure. No AutoCut plan, ffmpeg encode, or mutation of the source timeline.
"""
from __future__ import annotations

from typing import Any, Callable

from .original_video_export import uncut_native_contract


def materialize_original_video(
    resolve: Any,
    project: Any,
    payload: dict[str, Any],
    *,
    materialize_overlay: Callable[[dict[str, Any]], dict[str, Any]],
    report: Callable[[dict[str, Any], str, int, str], None],
    save_project: Callable[[Any], None],
) -> dict[str, Any]:
    from .resolve_native_cut import (
        create_native_cut_base, delete_owned_native_cut, record_native_cut_result,
        recover_native_cut_result, verify_native_cut_base,
    )
    original_video = payload.get("original_video")
    if not isinstance(original_video, dict):
        raise ValueError("Video originale non presente nel pacchetto")
    if payload.get("native_cut") or payload.get("native_cut_reference"):
        raise ValueError("Il video originale e AutoCut sono modalita alternative")
    source = uncut_native_contract(original_video)
    source_payload = {**payload, "native_cut": source, "original_video_import": True}
    recovered = recover_native_cut_result(project, source_payload)
    if recovered:
        return recovered

    pool = project.GetMediaPool()
    previous_timeline = project.GetCurrentTimeline()
    report(payload, "source", 5, "Importo il video caricato senza tagli")
    base = create_native_cut_base(
        resolve, project, source_payload,
        progress=lambda pct, message: report(payload, "source", pct, message),
    )
    try:
        overlay_fields = ("titles", "subtitles", "broll_clips", "generic_broll_clips")
        if any(payload.get(field) for field in overlay_fields):
            overlay = {
                **payload,
                "destination_mode": "active",
                "source_project_name": project.GetName(),
                "source_timeline_id": str(base["timeline_id"]),
                "bridge_mark_in": int(base["base_frame"]),
                "native_cut_fresh": True,
                "native_cut_fps": source["fps"],
            }
            overlay.pop("original_video", None)
            result = materialize_overlay(overlay)
        else:
            result = {
                "status": "created",
                "timeline_id": str(base["timeline_id"]),
                "timeline_name": str(base["timeline_name"]),
                "title_count": 0,
                "subtitle_count": 0,
                "broll_count": 0,
                "generic_broll_count": 0,
            }
        counts = verify_native_cut_base(base["timeline"], source, int(base["base_frame"]))
        result.update(
            original_video=True,
            video_count=counts["video_count"],
            audio_count=counts["audio_count"],
            source_identity=source["source_identity"],
            fps=source["fps"],
            width=source["width"],
            height=source["height"],
            destination_mode="new",
            source_unchanged=True,
            source_timeline_id=str(previous_timeline.GetUniqueId()) if previous_timeline else None,
            source_timeline=str(previous_timeline.GetName()) if previous_timeline else None,
        )
        save_project(resolve.GetProjectManager())
        record_native_cut_result(project, source_payload, result)
        report(payload, "completed", 100, "Video originale e montaggio caricati in Resolve")
        return result
    except Exception:
        # Never leave an incorrectly assembled timeline masquerading as success.
        delete_owned_native_cut(project, pool, base["timeline"], previous_timeline, source_payload)
        raise
