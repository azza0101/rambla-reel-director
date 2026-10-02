"""Materialize filtered transcript rows as native DaVinci Resolve subtitles."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any


def _srt_time(seconds: float) -> str:
    milliseconds = max(0, round(float(seconds) * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    whole_seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{whole_seconds:02},{milliseconds:03}"


def render_filtered_srt(rows: list[dict[str, Any]]) -> str:
    blocks = []
    for index, row in enumerate(rows, start=1):
        text = str(row.get("text") or "").strip()
        start = float(row["start_seconds"])
        end = float(row["end_seconds"])
        if not text or end <= start:
            raise ValueError("every subtitle needs text and a positive duration")
        blocks.append(f"{index}\n{_srt_time(start)} --> {_srt_time(end)}\n{text}")
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def normalize_subtitle_rows(rows: list[dict[str, Any]], *, fps: int) -> list[dict[str, Any]]:
    if fps <= 0:
        raise ValueError("subtitle fps must be positive")
    return [
        {
            **row,
            "start_frame": round(float(row["start_seconds"]) * fps),
            "end_frame": max(round(float(row["start_seconds"]) * fps) + 1, round(float(row["end_seconds"]) * fps)),
            "start_seconds": round(float(row["start_seconds"]) * fps) / fps,
            "end_seconds": max(round(float(row["start_seconds"]) * fps) + 1, round(float(row["end_seconds"]) * fps)) / fps,
        }
        for row in rows
    ]


def _subtitle_items(timeline: Any) -> list[Any]:
    items: list[Any] = []
    for track in range(1, int(timeline.GetTrackCount("subtitle") or 0) + 1):
        items.extend(timeline.GetItemListInTrack("subtitle", track) or [])
    return items


def _identity(item: Any) -> Any:
    getter = getattr(item, "GetUniqueId", None)
    return getter() if getter else id(item)


def find_subtitle_media(pool: Any, path: Path) -> Any | None:
    root_getter = getattr(pool, "GetRootFolder", None)
    if not root_getter:
        return None
    wanted = os.path.normcase(os.path.abspath(str(path)))
    pending = [root_getter()]
    while pending:
        folder = pending.pop()
        if not folder:
            continue
        raw_clips = folder.GetClipList() or []
        clips = list(raw_clips.values()) if isinstance(raw_clips, dict) else list(raw_clips)
        for clip in clips:
            candidate = os.path.normcase(os.path.abspath(str(clip.GetClipProperty("File Path") or "")))
            if candidate == wanted and str(clip.GetClipProperty("Type")).casefold() == "subtitle":
                return clip
        raw_folders = folder.GetSubFolderList() or []
        pending.extend(list(raw_folders.values()) if isinstance(raw_folders, dict) else list(raw_folders))
    return None


def _as_list(value: Any) -> list[Any]:
    return list(value.values()) if isinstance(value, dict) else list(value or [])


def ensure_media_pool_folder(pool: Any, name: str) -> Any:
    root = pool.GetRootFolder()
    for folder in _as_list(root.GetSubFolderList()):
        if str(folder.GetName()).casefold() == str(name).casefold():
            return folder
    folder = pool.AddSubFolder(root, name)
    if not folder:
        raise RuntimeError(f"Resolve could not create the Media Pool bin '{name}'")
    return folder


def cleanup_stale_subtitle_media(pool: Any, *, keep: Any | None = None) -> int:
    stale: list[Any] = []
    pending = [pool.GetRootFolder()]
    keep_id = _identity(keep) if keep is not None else None
    while pending:
        folder = pending.pop()
        pending.extend(_as_list(folder.GetSubFolderList()))
        for clip in _as_list(folder.GetClipList()):
            if keep_id is not None and _identity(clip) == keep_id:
                continue
            name = str(clip.GetName() or "").casefold()
            path = str(clip.GetClipProperty("File Path") or "").casefold()
            generated = (
                name.startswith("rambla-native-subs-")
                or name.startswith("rambla-filtered-subs-")
                or (name.startswith("rambla_") and "_native_subs_" in name)
                or name.startswith("debug_native_subs")
                or "rambla-native-subs-" in path
                or "rambla-filtered-subs-" in path
                or ("rambla_" in path and "_native_subs_" in path)
            )
            if generated:
                stale.append(clip)
    if stale and pool.DeleteClips(stale) is False:
        raise RuntimeError("Resolve could not clean old RAMBLA subtitle sources")
    return len(stale)


def insert_native_subtitles(
    resolve: Any,
    project: Any,
    timeline: Any,
    rows: list[dict[str, Any]],
    fps: int,
    base_frame: int,
    srt_path: Path | None = None,
) -> list[Any]:
    """Import relative SRT and append it as genuine Resolve Subtitle items."""
    del resolve, fps, base_frame  # SRT is relative; Resolve anchors it to the timeline start.
    if not rows:
        return []
    if int(timeline.GetTrackCount("subtitle") or 0) == 0:
        added = timeline.AddTrack("subtitle")
        if added is False or int(timeline.GetTrackCount("subtitle") or 0) == 0:
            raise RuntimeError("Resolve could not create a native Subtitle track")
    before = {_identity(item) for item in _subtitle_items(timeline)}
    if srt_path is None:
        handle, raw_path = tempfile.mkstemp(prefix="rambla-filtered-subs-", suffix=".srt")
        path = Path(raw_path)
        with os.fdopen(handle, "w", encoding="utf-8-sig", newline="\n") as stream:
            stream.write(render_filtered_srt(rows))
    else:
        path = Path(srt_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_filtered_srt(rows), encoding="utf-8-sig", newline="\n")
    try:
        pool = project.GetMediaPool()
        target_folder = ensure_media_pool_folder(pool, "TEMP")
        original_folder = pool.GetCurrentFolder()
        existing_media = find_subtitle_media(pool, path)
        try:
            if pool.SetCurrentFolder(target_folder) is False:
                raise RuntimeError("Resolve could not open the TEMP Media Pool bin")
            imported = [existing_media] if existing_media else (pool.ImportMedia([str(path)]) or [])
            if existing_media and pool.MoveClips([existing_media], target_folder) is False:
                raise RuntimeError("Resolve could not move the subtitle source into TEMP")
        finally:
            pool.SetCurrentFolder(original_folder)
        if len(imported) != 1 or str(imported[0].GetClipProperty("Type")).casefold() != "subtitle":
            raise RuntimeError("Resolve could not import the filtered SRT as native Subtitle media")
        rename = getattr(imported[0], "SetClipProperty", None)
        if rename:
            rename("Clip Name", f"RAMBLA · {len(rows)} sottotitoli nativi · sorgente interna")
        # Resolve 21.1 always materializes an appended SRT on subtitle track 1.
        # It still returns a truthy result when that track is locked, but silently
        # creates zero timeline items. Active-timeline mode protects every source
        # track before writing, so unlock track 1 only for this append and restore
        # its original state immediately afterwards. Existing items are separately
        # snapshotted and verified by the caller before the generated copy is kept.
        was_locked = False
        get_lock = getattr(timeline, "GetIsTrackLocked", None)
        set_lock = getattr(timeline, "SetTrackLock", None)
        if get_lock is not None and set_lock is not None:
            was_locked = bool(get_lock("subtitle", 1))
            if was_locked and set_lock("subtitle", 1, False) is False:
                raise RuntimeError("Resolve could not temporarily unlock Subtitle track 1")
        try:
            if not pool.AppendToTimeline(imported):
                raise RuntimeError("Resolve could not place the native Subtitle clips on the timeline")
        finally:
            if was_locked and set_lock("subtitle", 1, True) is False:
                raise RuntimeError("Resolve could not restore the Subtitle track lock")
        inserted = [item for item in _subtitle_items(timeline) if _identity(item) not in before]
        if not inserted:
            raise RuntimeError("Resolve imported the SRT but created no native Subtitle clips")
        return inserted
    except Exception:
        path.unlink(missing_ok=True)
        raise


def verify_native_subtitles(
    timeline: Any,
    rows: list[dict[str, Any]],
    fps: int,
    base_frame: int,
) -> None:
    del fps
    actual = sorted(
        (str(item.GetName()).strip(), int(item.GetStart()), int(item.GetEnd()))
        for item in _subtitle_items(timeline)
    )
    expected = sorted(
        (
            str(row["text"]).strip(),
            int(base_frame) + int(row["start_frame"]),
            int(base_frame) + int(row["end_frame"]),
        )
        for row in rows
    )
    matches = len(actual) == len(expected) and all(
        actual_text == expected_text
        and abs(actual_start - expected_start) <= 1
        and abs(actual_end - expected_end) <= 1
        for (actual_text, actual_start, actual_end), (expected_text, expected_start, expected_end)
        in zip(actual, expected)
    )
    if not matches:
        raise RuntimeError(f"Resolve native Subtitle verification failed: expected {expected}, got {actual}")
