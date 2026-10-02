"""Create a text-only Resolve timeline from highlighted transcript words."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from typing import Any, Callable

from backend.app.video_preview import probe_preview

from backend.app.resolve_native_subtitles import (
    cleanup_stale_subtitle_media,
    ensure_media_pool_folder,
    find_subtitle_media,
    insert_native_subtitles,
    normalize_subtitle_rows,
    verify_native_subtitles,
)


def wrap_textplus_text(text: str, *, max_chars: int = 11) -> str:
    """Wrap highlighted Text+ copy at word boundaries for vertical-safe titles."""
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    words = str(text or "").split()
    if not words:
        return ""
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = current + " " + word
        if len(candidate) <= max_chars:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return "\n".join(lines)


def build_textplus_timeline_plan(payload: dict[str, Any], *, target_fps: float) -> dict[str, Any]:
    if target_fps <= 0:
        raise ValueError("target fps must be positive")
    segments: list[dict[str, Any]] = []
    for item in payload.get("items") or []:
        text = wrap_textplus_text(str(item.get("text") or "").strip())
        start = round(float(item["start_seconds"]) * target_fps)
        end = round(float(item["end_seconds"]) * target_fps)
        if not text or end <= start:
            raise ValueError("every Text+ item needs text and a positive duration")
        if len(text.split()) > 3:
            raise ValueError("Text+ groups may contain at most three words")
        segments.append({"text": text, "start_frame": start, "end_frame": end})
    if not segments:
        raise ValueError("select at least one highlighted word")
    segments.sort(key=lambda row: (row["start_frame"], row["end_frame"]))
    for previous, current in zip(segments, segments[1:]):
        if current["start_frame"] < previous["end_frame"]:
            raise ValueError("Text+ ranges overlap")
    boundaries = sorted({frame for row in segments for frame in (row["start_frame"], row["end_frame"])})
    return {"fps": float(target_fps), "boundaries": boundaries, "segments": segments}


def title_name_from_payload(payload: dict[str, Any]) -> str:
    value = str(payload.get("title_name") or "").strip()
    if not value:
        raise ValueError("select a Resolve title template before creating the timeline")
    return value


def mode_from_payload(payload: dict[str, Any]) -> str:
    mode = str(payload.get("mode") or "titles").strip().casefold()
    if mode not in {"titles", "combined", "editing"}:
        raise ValueError("Resolve timeline mode must be 'titles', 'combined' or 'editing'")
    return mode


def should_rebuild_active_timeline(destination_mode: str, timeline_name: str) -> bool:
    """Rebuild a RAMBLA output cleanly instead of duplicating its generated items."""
    if destination_mode != "active":
        return False
    normalized = " ".join(str(timeline_name or "").upper().split())
    return "SUBS + KEYWORDS" in normalized


def next_backup_name(project: Any, timeline_name: str, *, timestamp: str | None = None) -> str:
    stamp = timestamp or datetime.now().strftime("%Y-%m-%d · %H-%M-%S")
    prefix = f"{timeline_name} · BCK · {stamp} · "
    existing = {
        str(project.GetTimelineByIndex(index).GetName())
        for index in range(1, int(project.GetTimelineCount() or 0) + 1)
        if project.GetTimelineByIndex(index)
    }
    number = 1
    while f"{prefix}{number:03d}" in existing:
        number += 1
    return f"{prefix}{number:03d}"


def create_active_backup(original: Any, backup_name: str) -> tuple[Any, Any]:
    backup = original.DuplicateTimeline(backup_name)
    if not backup:
        raise RuntimeError("Resolve could not create the required safety backup")
    return original, backup


def snapshot_timeline_markers(timeline: Any) -> dict[Any, Any]:
    return copy.deepcopy(dict(timeline.GetMarkers() or {}))


def verify_timeline_markers(timeline: Any, expected: dict[Any, Any]) -> None:
    if dict(timeline.GetMarkers() or {}) != expected:
        raise RuntimeError("RAMBLA safety check: timeline markers moved or changed")


def restore_timeline_markers(timeline: Any, expected: dict[Any, Any]) -> bool:
    """Restore markers only when Resolve actually changed them.

    Rewriting an already-correct marker set is unnecessary and can itself make
    Resolve 21 re-materialize markers at a different visual position. Keep the
    timeline completely untouched in the normal case; only fall back to the API
    rewrite when the live marker dictionary differs from the pre-apply snapshot.
    """
    current = copy.deepcopy(dict(timeline.GetMarkers() or {}))
    if current == expected:
        return False
    for frame in list(current.keys()):
        if timeline.DeleteMarkerAtFrame(frame) is False:
            raise RuntimeError(f"Resolve could not clear moved marker at frame {frame}")
    for frame, row in expected.items():
        if timeline.AddMarker(
            frame,
            str(row.get("color") or "Blue"),
            str(row.get("name") or ""),
            str(row.get("note") or ""),
            float(row.get("duration") or 1),
            str(row.get("customData") or ""),
        ) is False:
            raise RuntimeError(f"Resolve could not restore marker at frame {frame}")
    verify_timeline_markers(timeline, expected)
    return True


def active_track_layout(
    original_video_tracks: int, clips: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], int]:
    remapped = [
        {**row, "track_index": original_video_tracks + max(1, int(row.get("track_index") or 2) - 1)}
        for row in clips
    ]
    title_track = max([original_video_tracks] + [int(row["track_index"]) for row in remapped]) + 1
    return remapped, title_track


def rescale_broll_frames(clips: list[dict[str, Any]], *, source_fps: float, target_fps: float) -> list[dict[str, Any]]:
    """Convert RAMBLA timeline-frame coordinates to Resolve's actual frame rate."""
    if source_fps <= 0 or target_fps <= 0:
        raise ValueError("source and target fps must be positive")
    if abs(source_fps - target_fps) < 0.001:
        return [dict(row) for row in clips]
    ratio = target_fps / source_fps
    fields = ("record_start_frame", "record_end_frame", "source_start_frame", "source_end_frame", "duration_frames")
    return [{**row, **{key: int(round(float(row.get(key) or 0) * ratio)) for key in fields if key in row}} for row in clips]


def remove_prior_rambla_items(timeline: Any, *, title_name: str) -> dict[str, int]:
    """Remove generated RAMBLA layers from a disposable duplicate, preserving the source."""
    video_remove = []
    for track in range(1, int(timeline.GetTrackCount("video") or 0) + 1):
        for item in timeline.GetItemListInTrack("video", track) or []:
            generated_title = bool(item.GetFusionCompCount()) and str(item.GetName() or "") == title_name and str(item.GetClipColor() or "") == "Yellow"
            media = item.GetMediaPoolItem() if hasattr(item, "GetMediaPoolItem") else None
            metadata = media.GetMetadata() if media and hasattr(media, "GetMetadata") else {}
            keywords = str((metadata or {}).get("Keywords") or "") if isinstance(metadata, dict) else ""
            generated_broll = "RAMBLA" in keywords.upper() and str(item.GetClipColor() or "") in {"Purple", "Beige"}
            if generated_title or generated_broll:
                video_remove.append(item)
    # Existing subtitles are replaced only when this duplicate already contains
    # RAMBLA video layers. On a first import, preserve subtitles authored by the user.
    subtitle_remove = ([item for track in range(1, int(timeline.GetTrackCount("subtitle") or 0) + 1)
                        for item in (timeline.GetItemListInTrack("subtitle", track) or [])]
                       if video_remove else [])
    if video_remove and timeline.DeleteClips(video_remove, False) is False:
        raise RuntimeError("Resolve could not replace earlier RAMBLA video layers")
    if subtitle_remove and timeline.DeleteClips(subtitle_remove, False) is False:
        raise RuntimeError("Resolve could not replace earlier RAMBLA subtitles")
    return {"video": len(video_remove), "subtitle": len(subtitle_remove)}


def mute_prior_rambla_titles(timeline: Any, *, title_name: str) -> int:
    """Disable prior generated keyword clips without touching any media layer."""
    muted = 0
    for track in range(1, int(timeline.GetTrackCount("video") or 0) + 1):
        for item in timeline.GetItemListInTrack("video", track) or []:
            generated = bool(item.GetFusionCompCount()) and str(item.GetName() or "") == title_name and str(item.GetClipColor() or "") == "Yellow"
            if not generated:
                continue
            setter = getattr(item, "SetClipEnabled", None)
            if setter is None or setter(False) is False:
                raise RuntimeError("Resolve could not mute a previous RMBL Text+ clip")
            muted += 1
    return muted


def _rambla_subtitle_item(item: Any) -> bool:
    media = item.GetMediaPoolItem() if hasattr(item, "GetMediaPoolItem") else None
    if not media:
        return False
    name = str(media.GetName() or "").casefold() if hasattr(media, "GetName") else ""
    path = str(media.GetClipProperty("File Path") or "").casefold() if hasattr(media, "GetClipProperty") else ""
    return "rambla" in name or "rambla" in path


def mute_prior_rambla_subtitles(timeline: Any) -> int:
    """Disable only subtitle clips that can be identified as RAMBLA-generated."""
    muted = 0
    get_track_name = getattr(timeline, "GetTrackName", None)
    for track in range(1, int(timeline.GetTrackCount("subtitle") or 0) + 1):
        track_name = str(get_track_name("subtitle", track) or "") if get_track_name else ""
        named_rambla = track_name.casefold().startswith("rmbl subs ")
        for item in timeline.GetItemListInTrack("subtitle", track) or []:
            if not named_rambla and not _rambla_subtitle_item(item):
                continue
            setter = getattr(item, "SetClipEnabled", None)
            if setter is None or setter(False) is False:
                raise RuntimeError("Resolve could not mute a previous RMBL Subtitle clip")
            muted += 1
    return muted


def next_rambla_track_name(timeline: Any, kind: str, prefix: str) -> str:
    getter = getattr(timeline, "GetTrackName", None)
    pattern = re.compile(rf"^{re.escape(prefix)} v(\d+)$", re.I)
    versions = []
    if getter:
        for track in range(1, int(timeline.GetTrackCount(kind) or 0) + 1):
            match = pattern.match(str(getter(kind, track) or ""))
            if match:
                versions.append(int(match.group(1)))
    return f"{prefix} v{max(versions, default=0) + 1}"


def name_rambla_track(timeline: Any, kind: str, track: int, prefix: str) -> str:
    name = next_rambla_track_name(timeline, kind, prefix)
    setter = getattr(timeline, "SetTrackName", None)
    if setter is not None and setter(kind, int(track), name) is False:
        raise RuntimeError(f"Resolve could not name the new {kind} track")
    return name


def canonical_timeline_name(payload: dict[str, Any]) -> str:
    project_name = re.sub(r'[\\/:*?"<>|]+', " ", str(payload.get("project_name") or "RAMBLA")).strip()
    project_name = re.sub(r"\s+", " ", project_name)[:80] or "RAMBLA"
    mode = mode_from_payload(payload)
    suffix = "SUBS + KEYWORDS + B-ROLL TIMELINE v1" if mode == "editing" else "SUBS + KEYWORDS TIMELINE v1" if mode == "combined" else "KEYWORDS TIMELINE v1"
    return f"{project_name} - {suffix}"


def next_timeline_name(project: Any, payload: dict[str, Any]) -> str:
    first = canonical_timeline_name(payload)
    stem = first.rsplit(" v", 1)[0]
    pattern = re.compile(rf"^{re.escape(stem)} v(\d+)$")
    versions = []
    for index in range(1, int(project.GetTimelineCount() or 0) + 1):
        timeline = project.GetTimelineByIndex(index)
        match = pattern.match(str(timeline.GetName() or "")) if timeline else None
        if match:
            versions.append(int(match.group(1)))
    return f"{stem} v{max(versions, default=0) + 1}"


def legacy_generated_timelines(
    project: Any, *, keep: Any, canonical_name: str, mode: str = "combined"
) -> list[Any]:
    del canonical_name
    keep_id = str(keep.GetUniqueId()) if hasattr(keep, "GetUniqueId") else None
    stale = []
    for index in range(1, int(project.GetTimelineCount() or 0) + 1):
        timeline = project.GetTimelineByIndex(index)
        if not timeline:
            continue
        same = (
            str(timeline.GetUniqueId()) == keep_id
            if keep_id is not None and hasattr(timeline, "GetUniqueId")
            else timeline is keep
        )
        if same:
            continue
        name = str(timeline.GetName() or "")
        legacy_prefix = "RAMBLA_COMBINED_" if mode == "combined" else "RAMBLA_TEXTPLUS_"
        if name.startswith(legacy_prefix):
            stale.append(timeline)
    return stale


def find_timeline_media_item(media_pool: Any, timeline: Any) -> Any | None:
    wanted = str(timeline.GetUniqueId())
    pending = [media_pool.GetRootFolder()]
    while pending:
        folder = pending.pop()
        raw_folders = folder.GetSubFolderList() or []
        pending.extend(list(raw_folders.values()) if isinstance(raw_folders, dict) else list(raw_folders))
        raw_clips = folder.GetClipList() or []
        clips = list(raw_clips.values()) if isinstance(raw_clips, dict) else list(raw_clips)
        for clip in clips:
            getter = getattr(clip, "GetTimeline", None)
            if not getter:
                continue
            try:
                candidate = getter()
                if candidate and str(candidate.GetUniqueId()) == wanted:
                    return clip
            except Exception:
                continue
    return None


def export_drt(resolve: Any, timeline: Any, output_path: Path) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, raw_path = tempfile.mkstemp(prefix="rambla-timeline-", suffix=".drt")
    os.close(handle)
    local_target = Path(raw_path)
    local_target.unlink(missing_ok=True)
    try:
        result = timeline.Export(str(local_target), resolve.EXPORT_DRT, resolve.EXPORT_NONE)
        if result is False or not local_target.is_file() or local_target.stat().st_size <= 0:
            raise RuntimeError("Resolve could not export the generated DRT timeline")
        shutil.copy2(local_target, target)
    finally:
        local_target.unlink(missing_ok=True)
    return target


def export_dra(
    project_manager: Any,
    project: Any,
    output_path: Path,
    *,
    media_paths: list[str] | None = None,
) -> Path:
    """Archive the current Resolve project and return a downloadable zip package."""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    final = target.parent / (target.name + ".zip")
    final.unlink(missing_ok=True)
    # Resolve can reject mapped/network drives even when Python can write to
    # them. Archive beside the Resolve process first, then copy the package to
    # the project export directory (the same pattern used by DRT export).
    local_target = Path(tempfile.gettempdir()) / f"rambla-{uuid.uuid4().hex}.dra"
    local_zip = local_target.with_suffix(".zip")
    try:
        result = project_manager.ArchiveProject(
            str(project.GetName()), str(local_target), False, False, False
        )
        if result is False or not local_target.exists() or not local_target.is_dir():
            # Some Resolve builds refuse ArchiveProject while that project is
            # loaded. ExportProject is supported for the loaded project; a DRA
            # is a directory whose root contains project.drp.
            local_target.mkdir(parents=True, exist_ok=True)
            project_file = local_target / "project.drp"
            if project_manager.ExportProject(str(project.GetName()), str(project_file), True) is False or not project_file.is_file():
                raise RuntimeError("Resolve could not archive the generated TEMP timeline")
            media_dir = local_target / "MediaFiles"
            for raw in media_paths or []:
                source = Path(raw)
                if source.is_file():
                    media_dir.mkdir(exist_ok=True)
                    prefix = hashlib.sha256(str(source.resolve()).encode("utf-8")).hexdigest()[:10]
                    destination = media_dir / f"{prefix}-{source.name}"
                    if not destination.exists():
                        shutil.copy2(source, destination)
        local_zip = Path(shutil.make_archive(str(local_zip.with_suffix("")), "zip", root_dir=local_target))
        shutil.copy2(local_zip, final)
        return final
    finally:
        shutil.rmtree(local_target, ignore_errors=True)
        local_zip.unlink(missing_ok=True)


def generated_fusion_items(timeline: Any, existing_ids: set[str]) -> list[Any]:
    """Include split descendants: Resolve gives them fresh IDs on overwrite."""
    return [item for track in range(1, int(timeline.GetTrackCount('video') or 0) + 1)
            for item in (timeline.GetItemListInTrack('video', track) or [])
            if str(item.GetUniqueId()) not in existing_ids and item.GetFusionCompCount()]


def boundary_operations(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Return boundary insertions, priming Resolve before a non-zero first title.

    Resolve 21 can ignore the first non-zero playhead position on a newly
    reserved Fusion-title track and create that first title at the timeline
    origin instead. A blank boundary at frame 0 makes that behavior explicit:
    the real first boundary then splits the priming title at the requested
    frame, and select_exact_segments() removes the blank lead-in fragment.
    """
    text_by_start = {int(row["start_frame"]): row["text"] for row in plan["segments"]}
    boundaries = [int(frame) for frame in plan["boundaries"]]
    if boundaries and boundaries[0] > 0:
        boundaries.insert(0, 0)
    return [
        {"frame": frame, "text": text_by_start.get(frame)}
        for frame in boundaries
    ]


def select_exact_segments(
    materialized: list[dict[str, Any]], requested: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_range = {(int(row["start_frame"]), int(row["end_frame"])): row for row in materialized}
    keep = []
    used: set[int] = set()
    for expected in requested:
        key = (int(expected["start_frame"]), int(expected["end_frame"]))
        actual = by_range.get(key)
        if actual is None:
            available = sorted(by_range)
            raise RuntimeError(
                f"Resolve did not create the exact Text+ range {key[0]}-{key[1]}; available ranges: {available}"
            )
        merged = {**actual, "text": expected["text"]}
        keep.append(merged)
        used.add(id(actual))
    remove = [row for row in materialized if id(row) not in used]
    return keep, remove


def _frame_to_timecode(frame: int, fps: int) -> str:
    hours, remainder = divmod(int(frame), fps * 3600)
    minutes, remainder = divmod(remainder, fps * 60)
    seconds, frames = divmod(remainder, fps)
    return f"{hours:02}:{minutes:02}:{seconds:02}:{frames:02}"


def move_to_boundary(timeline: Any, *, boundary: int, base_frame: int, fps: int) -> None:
    timecode = _frame_to_timecode(base_frame + int(boundary), fps)
    if timeline.SetCurrentTimecode(timecode) is False:
        raise RuntimeError(f"Resolve could not move to Text+ boundary {boundary}")


def _timeline_items(timeline: Any) -> list[Any]:
    rows = []
    for kind in ("video", "audio", "subtitle"):
        for track in range(1, int(timeline.GetTrackCount(kind) or 0) + 1):
            rows.extend(timeline.GetItemListInTrack(kind, track) or [])
    return rows


def clear_generated_timeline(timeline: Any) -> None:
    """Empty only the disposable duplicate, including clips on locked tracks."""
    for kind in ("video", "audio", "subtitle"):
        for track in range(1, int(timeline.GetTrackCount(kind) or 0) + 1):
            try:
                if timeline.GetIsTrackLocked(kind, track) is True:
                    timeline.SetTrackLock(kind, track, False)
            except Exception:
                try:
                    timeline.SetTrackLock(kind, track, False)
                except Exception:
                    pass
    for _attempt in range(3):
        existing = _timeline_items(timeline)
        if not existing:
            return
        timeline.DeleteClips(existing, False)
        time.sleep(0.12)
    remaining = _timeline_items(timeline)
    details = ", ".join(
        f"{kind}:{sum(len(timeline.GetItemListInTrack(kind, track) or []) for track in range(1, int(timeline.GetTrackCount(kind) or 0) + 1))}"
        for kind in ("video", "audio", "subtitle")
    )
    raise RuntimeError(f"Resolve could not clear the generated timeline ({len(remaining)} items remain; {details})")


def _timeline_signature(timeline: Any) -> tuple[Any, ...]:
    return tuple(
        (item.GetName(), int(item.GetStart()), int(item.GetEnd()))
        for item in _timeline_items(timeline)
    )


def snapshot_existing_timeline_items(timeline: Any) -> dict[str, tuple[Any, ...]]:
    """Record every pre-existing item's track and range before RAMBLA writes."""
    snapshot = {}
    for kind in ("video", "audio", "subtitle"):
        for track in range(1, int(timeline.GetTrackCount(kind) or 0) + 1):
            for item in timeline.GetItemListInTrack(kind, track) or []:
                identity = str(item.GetUniqueId())
                snapshot[identity] = (kind, track, int(item.GetStart()), int(item.GetEnd()), str(item.GetName()))
    return snapshot


def verify_existing_timeline_items(timeline: Any, expected: dict[str, tuple[Any, ...]]) -> None:
    actual = snapshot_existing_timeline_items(timeline)
    changed = [identity for identity, value in expected.items() if actual.get(identity) != value]
    if changed:
        raise RuntimeError("RAMBLA safety check: existing timeline clips moved or changed; generated copy discarded")


def protect_existing_tracks(
    timeline: Any, *, reserve_subtitle_track: bool, title_track_index: int | None = None,
    reserve_title_track: bool = True,
) -> tuple[list[tuple[str, int, bool]], int]:
    """Lock source tracks and reserve empty upper tracks for RAMBLA additions."""
    states = []
    original_video_tracks = int(timeline.GetTrackCount("video") or 0)
    for kind in ("video", "audio", "subtitle"):
        for track in range(1, int(timeline.GetTrackCount(kind) or 0) + 1):
            try: locked = bool(timeline.GetIsTrackLocked(kind, track))
            except Exception: locked = False
            states.append((kind, track, locked))
            if timeline.SetTrackLock(kind, track, True) is False:
                raise RuntimeError(f"Resolve could not protect existing {kind} track {track}")
    target_title_track = int(title_track_index or (original_video_tracks + 1)) if reserve_title_track else original_video_tracks
    if reserve_title_track:
        while int(timeline.GetTrackCount("video") or 0) < target_title_track:
            if timeline.AddTrack("video") is False:
                raise RuntimeError("Resolve could not create the dedicated RAMBLA video tracks")
        # Keep every newly reserved B-roll track protected while Fusion titles are
        # inserted. The only writable video track is the last/highest title track.
        for track in range(original_video_tracks + 1, target_title_track):
            if timeline.SetTrackLock("video", track, True) is False:
                raise RuntimeError(f"Resolve could not reserve B-roll track {track}")
    if reserve_subtitle_track and timeline.AddTrack("subtitle") is False:
        raise RuntimeError("Resolve could not create the dedicated RAMBLA subtitle track")
    return states, original_video_tracks


def unlock_broll_tracks(timeline: Any, clips: list[dict[str, Any]]) -> None:
    for track in sorted({int(row["track_index"]) for row in clips}):
        if timeline.SetTrackLock("video", track, False) is False:
            raise RuntimeError(f"Resolve could not unlock B-roll track {track}")


def restore_active_timeline(
    project: Any, media_pool: Any, original: Any, backup: Any, original_name: str
) -> Any:
    """Replace a partially modified active timeline from its safety backup."""
    restored = backup.DuplicateTimeline(f"__RAMBLA_RESTORE_{int(time.time() * 1000)}")
    if not restored:
        raise RuntimeError("RAMBLA could not duplicate the safety backup for automatic restore")
    project.SetCurrentTimeline(backup)
    if media_pool.DeleteTimelines([original]) is False:
        media_pool.DeleteTimelines([restored])
        raise RuntimeError("RAMBLA could not remove the incomplete active timeline")
    if restored.SetName(original_name) is False:
        raise RuntimeError("RAMBLA restored the timeline but could not restore its original name")
    project.SetCurrentTimeline(restored)
    return restored


def restore_track_locks(timeline: Any, states: list[tuple[str, int, bool]]) -> None:
    for kind, track, locked in states:
        timeline.SetTrackLock(kind, track, locked)


def _text_tool(item: Any) -> Any:
    composition = item.GetFusionCompByIndex(1)
    if not composition:
        raise RuntimeError("Resolve created a title without a Fusion composition")
    tools = composition.GetToolList(False, "TextPlus") or {}
    values = list(tools.values()) if isinstance(tools, dict) else list(tools)
    exposed = [tool for tool in values if str(getattr(tool, "Name", "")).casefold() == "template"]
    if len(exposed) == 1:
        return exposed[0]
    if len(values) != 1:
        raise RuntimeError("Resolve Text+ composition is ambiguous")
    return values[0]


def set_textplus_content(item: Any, text: str) -> None:
    tool = _text_tool(item)
    for _ in range(5):
        tool.StyledText[0] = text
        if str(tool.GetInput("StyledText", 0)) == text:
            return
        time.sleep(0.1)
    raise RuntimeError(f"Resolve did not persist Text+ text: {text}")


def insert_fusion_title_with_retry(
    timeline: Any, title_name: str, *, attempts: int = 20,
    on_retry: Callable[[], Any] | None = None,
) -> Any:
    """Wait briefly while Resolve initializes Fusion on an activated duplicate."""
    for attempt in range(attempts):
        inserted = timeline.InsertFusionTitleIntoTimeline(title_name)
        if inserted:
            return inserted
        if attempt + 1 < attempts:
            if on_retry is not None:
                on_retry()
            time.sleep(0.5)
    return None


def save_resolve_project(project_manager: Any) -> None:
    if project_manager.SaveProject() is False:
        raise RuntimeError("Resolve could not save the generated timeline in the project")


def _safe_media_name(value: str, *, fallback: str) -> str:
    clean = re.sub(r'[\\/:*?"<>|]+', " ", str(value or ""))
    clean = re.sub(r"\s+", "_", clean).strip(" ._")
    return clean[:110] or fallback


def versioned_media_folder_name(project_name: str, timeline_name: str) -> str:
    match = re.search(r"\bv(\d+)$", str(timeline_name or ""), re.I)
    version = match.group(1) if match else "1"
    return f"{_safe_media_name(project_name, fallback='RAMBLA')}_media_v{version}"


def prepare_broll_media_files(
    clips: list[dict[str, Any]], staging_root: Path, folder_name: str
) -> list[dict[str, Any]]:
    destination = Path(staging_root) / folder_name
    destination.mkdir(parents=True, exist_ok=True)
    prepared = []
    used: set[str] = set()
    for row in clips:
        source = Path(str(row.get("media_path") or ""))
        if not source.is_file():
            continue
        provider = _safe_media_name(str(row.get("provider") or "source"), fallback="source")
        stem = _safe_media_name(str(row.get("title") or source.stem), fallback="clip")
        filename = f"{stem}_{provider}{source.suffix.casefold() or '.mp4'}"
        key = filename.casefold()
        if key in used or (destination / filename).exists():
            token = hashlib.sha256(str(row.get("asset_id") or source).encode("utf-8")).hexdigest()[:8]
            filename = f"{stem}_{provider}_{token}{source.suffix.casefold() or '.mp4'}"
        used.add(filename.casefold())
        target = destination / filename
        if not target.exists():
            try:
                os.link(source, target)
            except OSError:
                shutil.copy2(source, target)
        prepared.append({**row, "media_path": str(target.resolve()), "original_media_path": str(source.resolve())})
    return prepared


def _apply_broll_metadata(item: Any, row: dict[str, Any]) -> bool:
    metadata = {
        "Description": str(row.get("title") or row.get("asset_id") or "RAMBLA B-roll"),
        "Comments": "\n".join((
            "Original source: " + str(row.get("source_page") or "unknown"),
            "RAMBLA project: " + str(row.get("rambla_project") or "unknown"),
            "Timeline: " + str(row.get("rambla_timeline") or "unknown"),
        )),
        "Keywords": ", ".join(filter(None, (
            "RAMBLA", str(row.get("provider") or ""), str(row.get("beat_id") or "")
        ))),
    }
    setter = getattr(item, "SetMetadata", None)
    if not setter:
        return False
    try:
        return setter(metadata) is not False
    except TypeError:
        results = [setter(key, value) for key, value in metadata.items()]
        return all(result is not False for result in results)


def conform_broll_media(clips: list[dict[str, Any]], fps: float, progress=None) -> list[dict[str, Any]]:
    """Create frame-exact excerpts with editorial handles around the visible range.

    Resolve rounds source-frame trims before converting clip FPS. Some requested
    durations therefore cannot be represented with a mixed-rate source directly.
    """
    result = []
    for index, row in enumerate(clips):
        if progress: progress(index, len(clips))
        duration = int(row['record_end_frame']) - int(row['record_start_frame'])
        start = int(row['source_start_frame'])
        selected_end = start + duration
        source = Path(row['media_path'])
        available = max(selected_end, int(round(float(probe_preview(str(source)).get('duration') or 0) * fps)))
        cut_start = max(0, start - duration)
        cut_end = min(available, selected_end + duration)
        desired_total = duration * 3
        missing = max(0, desired_total - (cut_end - cut_start))
        if missing:
            extra_right = min(missing, max(0, available - cut_end))
            cut_end += extra_right
            missing -= extra_right
        if missing:
            cut_start = max(0, cut_start - missing)
        total = max(duration, cut_end - cut_start)
        handle_before = start - cut_start
        handle_after = max(0, cut_end - selected_end)
        target = source.with_name(f'{source.stem}_handles_{cut_start}_{total}_{fps:g}fps.mp4')
        if not target.is_file():
            temporary = target.with_name(target.stem + '.working.mp4')
            try:
                subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(cut_start / fps),
                    '-i', str(source), '-map', '0:v:0', '-an', '-vf', f'fps={fps:g}',
                    '-frames:v', str(total), '-c:v', 'libx264', '-preset', 'fast',
                    '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(temporary)],
                    check=True, capture_output=True, timeout=180,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        result.append({**row, 'media_path': str(target), 'source_start_frame': handle_before,
                       'source_end_frame': handle_before + duration,
                       'handle_before_frames': handle_before,
                       'handle_after_frames': handle_after})
    return result


def append_broll_clips(media_pool: Any, timeline: Any, clips: list[dict[str, Any]], *, base_frame: int, fps: float | None = None, progress=None) -> int:
    """Append local B-roll to V2+; the caller owns a disposable TEMP duplicate."""
    if not clips:
        return 0
    highest = max(int(row["track_index"]) for row in clips)
    while int(timeline.GetTrackCount("video") or 0) < highest:
        if timeline.AddTrack("video") is False:
            raise RuntimeError("Resolve could not create the requested B-roll video track")
    inserted = 0
    for index, row in enumerate(clips):
        if progress: progress(index, len(clips))
        imported = media_pool.ImportMedia([str(row["media_path"])]) or []
        if len(imported) != 1:
            raise RuntimeError(f"Resolve could not import selected clip: {row['media_path']}")
        _apply_broll_metadata(imported[0], row)
        ratio = 1.0
        if fps is not None:
            source_fps = float(imported[0].GetClipProperty("FPS"))
            if source_fps <= 0 or fps <= 0:
                raise ValueError("Invalid source or timeline frame rate")
            ratio = source_fps / fps
        duration = int(row["record_end_frame"]) - int(row["record_start_frame"])
        source_start = float(row["source_start_frame"]) * ratio
        result = media_pool.AppendToTimeline([{
            "mediaPoolItem": imported[0],
            "startFrame": source_start,
            "endFrame": source_start + duration * ratio,
            "mediaType": 1,
            "trackIndex": int(row["track_index"]),
            "recordFrame": int(base_frame) + int(row["record_start_frame"]),
        }]) or []
        if len(result) != 1:
            raise RuntimeError(f"Resolve could not place selected clip: {row['asset_id']}")
        if fps is not None:
            expected = (int(base_frame) + int(row["record_start_frame"]),
                        int(base_frame) + int(row["record_end_frame"]))
            actual = (int(result[0].GetStart()), int(result[0].GetEnd()))
            if actual != expected:
                raise RuntimeError(f"B-roll timing mismatch for {row['asset_id']}: {actual} != {expected}")
        color = "Beige" if row.get("role") == "generic" else "Purple"
        setter = getattr(result[0], "SetClipColor", None)
        if setter:
            setter(color)
        inserted += 1
    return inserted


def activate_timeline(resolve: Any, project: Any, timeline: Any) -> bool:
    resolve.OpenPage("edit")
    for _ in range(5):
        project.SetCurrentTimeline(timeline)
        current = project.GetCurrentTimeline()
        if current and str(current.GetUniqueId()) == str(timeline.GetUniqueId()):
            return True
        time.sleep(0.2)
    return False


def report_handoff_progress(payload: dict[str, Any], phase: str, percent: int, message: str) -> None:
    raw=str(payload.get("handoff_progress_path") or "").strip()
    if not raw: return
    from .atomic_io import write_json
    try:
        write_json(Path(raw), {"phase":phase,"percent":percent,"message":message})
    except OSError as exc:
        # A telemetry-file sharing lock must never abort a timeline build.
        print(f'Progress checkpoint unavailable: {exc}', file=sys.stderr, flush=True)


def materialize_in_resolve(payload: dict[str, Any]) -> dict[str, Any]:
    import DaVinciResolveScript as dvr_script  # type: ignore[import-not-found]

    resolve = dvr_script.scriptapp("Resolve")
    if not resolve:
        raise RuntimeError("DaVinci Resolve is not open or external scripting is unavailable")
    project_manager = resolve.GetProjectManager()
    project = project_manager.GetCurrentProject()
    if not project:
        raise RuntimeError("Open a DaVinci Resolve project first")
    linked_id = str(payload.get("source_timeline_id") or "").strip()
    linked_project = str(payload.get("source_project_name") or "").strip()
    if linked_project and str(project.GetName()) != linked_project:
        raise RuntimeError(f"Apri il progetto Resolve collegato: {linked_project}")
    original = None
    if linked_id:
        for index in range(1, int(project.GetTimelineCount() or 0) + 1):
            candidate = project.GetTimelineByIndex(index)
            if candidate and str(candidate.GetUniqueId()) == linked_id:
                original = candidate
                break
        if original is None:
            raise RuntimeError("La timeline Resolve collegata non esiste più")
    else:
        original = project.GetCurrentTimeline()
    if not original:
        raise RuntimeError("Open the destination timeline in Resolve first")
    report_handoff_progress(payload,"validate",5,"Collegamento Resolve verificato")
    fps_value = float(original.GetSetting("timelineFrameRate") or 0)
    original_name = str(original.GetName())
    fps = int(round(fps_value))
    if fps <= 0 or abs(fps_value - fps) > 0.001:
        raise RuntimeError(f"The first release supports integer timeline frame rates; Resolve reports {fps_value:g} fps")
    mode = mode_from_payload(payload)
    apply_scope = str(payload.get("apply_scope") or "all").strip().casefold()
    if apply_scope not in {"all", "titles", "subtitles"}:
        raise ValueError("apply_scope must be 'all', 'titles' or 'subtitles'")
    include_titles = apply_scope in {"all", "titles"}
    include_subtitles = apply_scope in {"all", "subtitles"}
    include_broll = apply_scope == "all"
    title_payload = {**payload, "items": payload.get("titles") or payload.get("items") or []}
    plan = build_textplus_timeline_plan(title_payload, target_fps=fps) if include_titles else {"segments": [], "boundaries": []}
    title_name = title_name_from_payload(payload) if include_titles else str(payload.get("title_name") or "")
    original_signature = _timeline_signature(original)
    original_markers = snapshot_timeline_markers(original)
    media_pool = project.GetMediaPool()
    name = original_name if str(payload.get("destination_mode") or "new") == "active" else next_timeline_name(project, payload)
    media_folder_name = versioned_media_folder_name(str(payload.get("project_name") or "RAMBLA"), name)
    destination_mode = str(payload.get("destination_mode") or "new")
    if destination_mode not in {"new", "active"}:
        raise ValueError("destination_mode must be 'new' or 'active'")
    if apply_scope != "all" and destination_mode != "active":
        raise ValueError("Selective Resolve updates require the active timeline")
    generic_rows = []
    prepared_broll_clips = []
    if include_broll:
        tail_frame = int(round(float(payload.get("duration_seconds") or 0) * fps)) + int(round(float(payload.get("generic_tail_gap_seconds") or 2) * fps))
        if destination_mode == 'active':
            origin = int(payload.get('bridge_mark_in') if payload.get('bridge_mark_in') is not None else original.GetStartFrame())
            tail_frame = max(tail_frame, int(original.GetEndFrame()) - origin + int(round(float(payload.get('generic_tail_gap_seconds') or 2) * fps)))
        for index, row in enumerate(payload.get("generic_broll_clips") or []):
            duration_frames = max(1, int(round(min(4.0, float(row.get("duration") or 4.0)) * fps)))
            generic_rows.append({**row, "asset_id": str(row.get("provider_id") or f"generic-{index}"), "beat_id": "generic-tail",
                                 "track_index": 2, "record_start_frame": tail_frame, "record_end_frame": tail_frame + duration_frames,
                                 "source_start_frame": 0, "source_end_frame": duration_frames, "role": "generic"})
            tail_frame += duration_frames
        source_payload_fps = float(payload.get("fps") or fps)
        coverage_rows = rescale_broll_frames(
            [{**row, "role": "coverage"} for row in payload.get("broll_clips") or []],
            source_fps=source_payload_fps, target_fps=fps,
        )
        all_broll_rows = coverage_rows + generic_rows
        prepared_broll_clips = prepare_broll_media_files(
            [{**row, "rambla_project": str(payload.get("project_name") or "RAMBLA"), "rambla_timeline": name}
             for row in all_broll_rows if row.get("media_path") and Path(str(row.get("media_path"))).is_file()],
            Path(str(payload.get("media_staging_root") or Path.cwd() / "resolve-media")),
            media_folder_name,
        )
        prepared_broll_clips = conform_broll_media(prepared_broll_clips, fps,
            progress=lambda index,total: report_handoff_progress(payload,'conform',5+int(12*index/max(1,total)),f'Preparo estratti video: {index}/{total}'))
    build_name = f"__RAMBLA_BUILD_{int(time.time() * 1000)}"
    generated = None
    backup = None
    backup_media = None
    protected_items = None
    protected_track_states = []
    active_mutated = False
    backup_folder = None
    target_folder = None
    media_folder = None
    title_track_index = None
    subtitle_target_track = None
    muted_title_count = 0
    muted_subtitle_count = 0
    markers_restored = False
    original_folder = media_pool.GetCurrentFolder()
    try:
        backup_folder = ensure_media_pool_folder(media_pool, "BCK")
        if include_broll:
            target_folder = ensure_media_pool_folder(media_pool, "B-ROLL MEDIA")
            raw_children = target_folder.GetSubFolderList() or []
            children = list(raw_children.values()) if isinstance(raw_children, dict) else list(raw_children)
            media_folder = next((folder for folder in children if str(folder.GetName()).casefold() == media_folder_name.casefold()), None)
            if media_folder is None:
                media_folder = media_pool.AddSubFolder(target_folder, media_folder_name)
            if not media_folder:
                raise RuntimeError(f"Resolve could not create the Media Pool bin '{media_folder_name}'")
        if destination_mode == "active":
            generated, backup = create_active_backup(
                original, next_backup_name(project, original_name)
            )
            backup_media = find_timeline_media_item(media_pool, backup)
            if backup_media is None:
                raise RuntimeError("Resolve could not find the safety backup in the Media Pool")
        else:
            generated = original.DuplicateTimeline(build_name)
            if not generated:
                raise RuntimeError("Resolve could not create the Text+ timeline")
        if not activate_timeline(resolve, project, generated):
            raise RuntimeError("Resolve could not activate the Text+ timeline")
        report_handoff_progress(payload,"destination",18,"Timeline di destinazione pronta")
        if destination_mode == "new":
            clear_generated_timeline(generated)
        else:
            active_mutated = True
            if apply_scope == "all":
                remove_prior_rambla_items(generated, title_name=title_name)
            elif apply_scope == "titles":
                muted_title_count = mute_prior_rambla_titles(generated, title_name=title_name)
            elif apply_scope == "subtitles":
                muted_subtitle_count = mute_prior_rambla_subtitles(generated)
            protected_items = snapshot_existing_timeline_items(generated)
            if include_broll:
                prepared_broll_clips, title_track_index = active_track_layout(
                    int(generated.GetTrackCount("video") or 0), prepared_broll_clips
                )
            elif include_titles:
                title_track_index = int(generated.GetTrackCount("video") or 0) + 1
            if apply_scope == "subtitles":
                subtitle_target_track = int(generated.GetTrackCount("subtitle") or 0) + 1
            protected_track_states, source_video_tracks = protect_existing_tracks(
                generated,
                reserve_subtitle_track=bool(payload.get("subtitles")) and mode in {"combined", "editing"} and include_subtitles,
                title_track_index=title_track_index,
                reserve_title_track=include_titles,
            )
            if include_titles and title_track_index is not None:
                name_rambla_track(generated, "video", title_track_index, "RMBL TEXT")
            if subtitle_target_track is not None:
                name_rambla_track(generated, "subtitle", subtitle_target_track, "RMBL SUBS")
        base_frame = int(payload.get("bridge_mark_in") if payload.get("bridge_mark_in") is not None else generated.GetStartFrame())
        keep = []
        if include_titles:
            existing_title_ids = {str(item.GetUniqueId()) for item in _timeline_items(generated)}
            for operation in boundary_operations(plan):
                boundary = operation["frame"]
                move_to_boundary(generated, boundary=boundary, base_frame=base_frame, fps=fps)
                inserted = insert_fusion_title_with_retry(
                    generated, title_name,
                    on_retry=lambda: activate_timeline(resolve, project, generated),
                )
                if not inserted:
                    raise RuntimeError(
                        f"Resolve Fusion Title '{title_name}' is unavailable. Install it and restart Resolve"
                    )
                color_setter = getattr(inserted, "SetClipColor", None)
                if color_setter:
                    color_setter("Yellow")
                if operation["text"] is not None:
                    set_textplus_content(inserted, operation["text"])
            report_handoff_progress(payload,"titles",66,"Parole evidenziate inserite")
            time.sleep(0.15)
            materialized = []
            for item in generated_fusion_items(generated, existing_title_ids):
                if item.GetFusionCompCount():
                    materialized.append({"id":str(item.GetUniqueId()),"item":item,"start_frame":int(item.GetStart())-base_frame,"end_frame":int(item.GetEnd())-base_frame})
            keep, remove = select_exact_segments(materialized, plan["segments"])
            if remove and generated.DeleteClips([row["item"] for row in remove], False) is False:
                raise RuntimeError('Resolve could not remove Fusion title split fragments')
            title_items = generated_fusion_items(generated, existing_title_ids)
            final_ranges = sorted((int(item.GetStart())-base_frame,int(item.GetEnd())-base_frame) for item in title_items)
            expected_ranges = sorted((row["start_frame"],row["end_frame"]) for row in plan["segments"])
            if final_ranges != expected_ranges:
                raise RuntimeError("Resolve Text+ verification found unexpected clip ranges")
            if any(str(item.GetName()) != title_name for item in title_items):
                raise RuntimeError("Resolve created a different title than the selected template")
            final_text = [str(_text_tool(row["item"]).GetInput("StyledText", 0)) for row in keep]
            if final_text != [str(row["text"]) for row in keep]:
                raise RuntimeError("Resolve title text verification failed")
        else:
            report_handoff_progress(payload,"titles",66,"Testi RMBL lasciati invariati")

        inserted_subtitles = []
        if include_subtitles:
            subtitles = normalize_subtitle_rows(list(payload.get("subtitles") or []) if mode in {"combined","editing"} else [], fps=fps)
            selective_srt = None if apply_scope == "subtitles" else (Path(payload["subtitle_srt_path"]) if payload.get("subtitle_srt_path") else None)
            inserted_subtitles = insert_native_subtitles(resolve,project,generated,subtitles,fps=fps,base_frame=base_frame,srt_path=selective_srt,target_track=subtitle_target_track)
            verify_native_subtitles(generated,subtitles,fps=fps,base_frame=base_frame,track_index=subtitle_target_track)
            report_handoff_progress(payload,"subtitles",78,"Sottotitoli inseriti")
        else:
            report_handoff_progress(payload,"subtitles",78,"Sottotitoli lasciati invariati")

        broll_count = 0
        if include_broll:
            if destination_mode == "active":
                unlock_broll_tracks(generated, prepared_broll_clips)
            media_pool.SetCurrentFolder(media_folder)
            broll_count = append_broll_clips(media_pool, generated, prepared_broll_clips, base_frame=base_frame, fps=fps,
                progress=lambda index,total: report_handoff_progress(payload,'broll',78+int(10*index/max(1,total)),f'Inserisco clip: {index}/{total}'))
            report_handoff_progress(payload,"broll",88,"B-roll posizionati")
        else:
            report_handoff_progress(payload,"broll",88,"Media e B-roll lasciati invariati")
        if protected_items is not None:
            verify_existing_timeline_items(generated, protected_items)
            markers_restored = restore_timeline_markers(generated, original_markers)
            verify_timeline_markers(generated, original_markers)
            restore_track_locks(generated, protected_track_states)
        if destination_mode == "new" and _timeline_signature(original) != original_signature:
            raise RuntimeError("The source timeline changed while creating Text+ clips")
        project.SetCurrentTimeline(generated)
        stale_timelines = legacy_generated_timelines(
            project, keep=generated, canonical_name=name, mode=mode
        )
        if destination_mode == "new" and (generated.SetName(name) is False or str(generated.GetName()) != name):
            raise RuntimeError("Resolve could not assign the final timeline name")
        if backup_media is not None and media_pool.MoveClips([backup_media], backup_folder) is False:
            raise RuntimeError("Resolve could not archive the safety backup in BCK")
        # Prior timelines belong to the editor. A new export never deletes them.
        stale_timelines = []
        current_subtitle_media = find_subtitle_media(media_pool, Path(payload["subtitle_srt_path"])) if include_subtitles and payload.get("subtitle_srt_path") else None
        removed_subtitle_sources = 0
        report_handoff_progress(payload,"save",96,"Salvataggio progetto Resolve")
        save_resolve_project(project_manager)
        result = {
            "status": "created", "timeline_name": name, "item_count": len(keep),
            "timeline_id": str(generated.GetUniqueId()),
            "source_timeline_id": str(original.GetUniqueId()),
            "title_count": len(keep), "subtitle_count": len(inserted_subtitles),
            "fps": fps, "title_name": title_name,
            "source_timeline": original_name, "source_unchanged": destination_mode != "active",
            "media_bin": target_folder.GetName() if target_folder is not None else None,
            "media_folder": media_folder_name if include_broll else None,
            "removed_timelines": len(stale_timelines),
            "removed_subtitle_sources": removed_subtitle_sources,
            "broll_count": broll_count,
            "generic_broll_count": len(generic_rows),
            "broll_skipped": len(payload.get("broll_unavailable") or []),
            "destination_mode": destination_mode,
            "apply_scope": apply_scope,
            "muted_title_count": muted_title_count,
            "muted_subtitle_count": muted_subtitle_count,
            "markers_restored": markers_restored,
            "backup_timeline_name": str(backup.GetName()) if backup else None,
        }
    except Exception:
        media_pool.SetCurrentFolder(original_folder)
        if destination_mode == "active" and active_mutated and backup:
            restored = restore_active_timeline(project, media_pool, original, backup, original_name)
            if backup_media is not None and backup_folder is not None:
                media_pool.MoveClips([backup_media], backup_folder)
            project.SetCurrentTimeline(restored)
            project_manager.SaveProject()
        else:
            project.SetCurrentTimeline(original)
        if destination_mode == "new" and generated:
            media_pool.DeleteTimelines([generated])
            project_manager.SaveProject()
        raise
    media_pool.SetCurrentFolder(original_folder)
    drt_output = str(payload.get("drt_output_path") or "").strip()
    if drt_output:
        result["drt_path"] = str(export_drt(resolve, generated, Path(drt_output)))
    dra_output = str(payload.get("dra_output_path") or "").strip()
    if dra_output:
        result["dra_path"] = str(export_dra(
            project_manager,
            project,
            Path(dra_output),
            media_paths=[str(row.get("media_path") or "") for row in prepared_broll_clips],
        ))
    return result


def run_resolve_helper(payload: dict[str, Any], *, timeout: float = 600.0) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    api_root = Path(os.environ.get(
        "RESOLVE_SCRIPT_API",
        r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting",
    ))
    library = Path(os.environ.get(
        "RESOLVE_SCRIPT_LIB",
        r"C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll",
    ))
    if not (api_root / "Modules" / "DaVinciResolveScript.py").is_file() or not library.is_file():
        raise RuntimeError("DaVinci Resolve scripting files are not installed")
    env = {**os.environ, "RESOLVE_SCRIPT_API": str(api_root), "RESOLVE_SCRIPT_LIB": str(library)}
    env["PYTHONUTF8"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (str(root), str(api_root / "Modules"), env.get("PYTHONPATH", ""))))
    handle, raw_path = tempfile.mkstemp(prefix="rambla-textplus-", suffix=".json")
    payload_path = Path(raw_path)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False)
        interpreter = str(getattr(sys, "_base_executable", None) or sys.executable)
        try:
            completed = subprocess.run(
                [interpreter, "-m", "backend.app.resolve_textplus_timeline", "--payload", str(payload_path)],
                cwd=root, env=env, capture_output=True, text=True, encoding="utf-8", timeout=timeout,
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f'Operazione Resolve interrotta dopo {timeout:g} secondi. Una copia TEMP può essere incompleta; la timeline originale è conservata. Consulta la diagnostica prima di riprovare.') from exc
        if completed.returncode:
            detail = (completed.stderr or completed.stdout or "Resolve Text+ helper failed").strip().splitlines()[-1]
            error = RuntimeError(detail)
            error.helper_traceback = (completed.stderr or completed.stdout or '')[-16000:]
            raise error
        return json.loads(completed.stdout)
    finally:
        payload_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", required=True)
    args = parser.parse_args()
    try:
        result = materialize_in_resolve(json.loads(Path(args.payload).read_text(encoding="utf-8")))
    except Exception as exc:
        import traceback
        traceback.print_exc(file=sys.stderr)
        raise SystemExit(1) from exc
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
