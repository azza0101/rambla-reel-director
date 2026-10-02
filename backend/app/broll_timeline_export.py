"""Build portable and Resolve-ready timelines from curated B-roll selections."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


def _frame(seconds: float, fps: int) -> int:
    return int(math.floor(float(seconds) * fps + 0.5))


def _track(value: Any, order: int) -> int:
    raw = str(value or f"V{order + 2}").strip().upper()
    if raw.startswith("V") and raw[1:].isdigit() and int(raw[1:]) >= 2:
        return int(raw[1:])
    return order + 2


def build_broll_timeline_plan(
    visual_plan: dict[str, Any],
    selection: dict[str, Any],
    assets: dict[str, dict[str, Any]],
    *,
    fps: int,
) -> dict[str, Any]:
    """Resolve selected assets into exact phrase ranges without requiring every beat."""
    if not isinstance(fps, int) or isinstance(fps, bool) or fps <= 0:
        raise ValueError("timeline fps must be a positive integer")
    beats = {
        str(row.get("id")): row
        for row in visual_plan.get("visual_beats", [])
        if isinstance(row, dict) and row.get("id")
    }
    clips: list[dict[str, Any]] = []
    unavailable: list[dict[str, str]] = []
    selected_beat_count = 0
    for beat_id, choice in (selection.get("chunks") or {}).items():
        chosen = list(choice.get("selected_assets") or []) if isinstance(choice, dict) else []
        if not chosen:
            continue
        selected_beat_count += 1
        beat = beats.get(str(beat_id))
        if not beat:
            for picked in chosen:
                unavailable.append({"beat_id": str(beat_id), "asset_id": str(picked.get("asset_id")), "reason": "visual beat timing is unavailable"})
            continue
        record_start = _frame(float(beat["start"]), fps)
        record_end = _frame(float(beat["end"]), fps)
        required = record_end - record_start
        if required <= 0:
            continue
        for order, picked in enumerate(chosen):
            asset_id = str(picked.get("asset_id") or "")
            asset = assets.get(asset_id) or {}
            raw_path = str(asset.get("media_path") or "").strip()
            path = Path(raw_path) if raw_path else None
            if path is None or not path.is_file():
                unavailable.append({"beat_id": str(beat_id), "asset_id": asset_id, "reason": "clip file is not available locally"})
                continue
            available = _frame(float(asset.get("duration_seconds") or 0), fps)
            source_start = _frame(float(asset.get("source_offset_seconds") or 0), fps)
            if available - source_start < required:
                unavailable.append({"beat_id": str(beat_id), "asset_id": asset_id, "reason": "clip is shorter than phrase and cannot preserve exact timing"})
                continue
            clips.append({
                "beat_id": str(beat_id), "asset_id": asset_id,
                "title": str(asset.get("title") or asset_id),
                "source_page": str(asset.get("source_page") or ""),
                "provider": str(asset.get("provider") or "unknown"),
                "media_path": str(path.resolve()), "track_index": _track(picked.get("track"), order),
                "record_start_frame": record_start, "record_end_frame": record_end,
                "source_start_frame": source_start, "source_end_frame": source_start + required,
                "duration_frames": required,
            })
    clips.sort(key=lambda row: (row["record_start_frame"], row["track_index"], row["asset_id"]))
    duration = max([_frame(float(row.get("end") or 0), fps) for row in beats.values()] + [1])
    return {
        "schema_version": "rambla-broll-timeline-1", "fps": fps,
        "duration_frames": duration, "selected_beat_count": selected_beat_count,
        "clip_count": len(clips), "clips": clips, "unavailable": unavailable,
    }


def render_fcp7_xml(plan: dict[str, Any], *, sequence_name: str) -> str:
    """Render an FCP7 XML sequence, a format Resolve imports with track timing."""
    fps = int(plan["fps"])
    tracks: dict[int, list[dict[str, Any]]] = {}
    for row in plan.get("clips") or []:
        tracks.setdefault(int(row["track_index"]), []).append(row)
    max_track = max(tracks, default=1)
    track_xml = []
    for track_index in range(1, max_track + 1):
        items = []
        for index, row in enumerate(tracks.get(track_index, []), 1):
            path = Path(row["media_path"])
            uri = escape(path.resolve().as_uri())
            name = escape(path.name)
            items.append(
                f'<clipitem id="clip-{track_index}-{index}"><name>{name}</name>'
                f'<duration>{row["duration_frames"]}</duration><rate><timebase>{fps}</timebase><ntsc>FALSE</ntsc></rate>'
                f'<start>{row["record_start_frame"]}</start><end>{row["record_end_frame"]}</end>'
                f'<in>{row["source_start_frame"]}</in><out>{row["source_end_frame"]}</out>'
                f'<file id="file-{track_index}-{index}"><name>{name}</name><pathurl>{uri}</pathurl>'
                f'<rate><timebase>{fps}</timebase><ntsc>FALSE</ntsc></rate><duration>{row["source_end_frame"]}</duration></file></clipitem>'
            )
        track_xml.append("<track>" + "".join(items) + "</track>")
    name = escape(str(sequence_name))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="5">'
        f'<sequence id="sequence-1"><name>{name}</name><duration>{int(plan["duration_frames"])}</duration>'
        f'<rate><timebase>{fps}</timebase><ntsc>FALSE</ntsc></rate><media><video>'
        + "".join(track_xml) + '</video></media></sequence></xmeml>\n'
    )
