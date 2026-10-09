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


def _subtitle_items(timeline: Any, track_index: int | None = None) -> list[Any]:
    items: list[Any] = []
    tracks = [int(track_index)] if track_index is not None else range(1, int(timeline.GetTrackCount("subtitle") or 0) + 1)
    for track in tracks:
        items.extend(timeline.GetItemListInTrack("subtitle", track) or [])
    return items


def _identity(item: Any) -> Any:
    getter = getattr(item, "GetUniqueId", None)
    return getter() if getter else id(item)


def subtitle_track_for_items(timeline: Any, items: list[Any]) -> int | None:
    wanted = {_identity(item) for item in items}
    if not wanted:
        return None
    matched = []
    for track in range(1, int(timeline.GetTrackCount("subtitle") or 0) + 1):
        track_ids = {_identity(item) for item in (timeline.GetItemListInTrack("subtitle", track) or [])}
        if wanted & track_ids:
            matched.append(track)
    return matched[0] if len(matched) == 1 else None


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


def reserve_subtitle_track_at_start(timeline: Any) -> int:
    """Reserve an empty ST1 before the caller snapshots/protects source tracks.

    Native SRT append can ignore clipInfo.trackIndex. Insert a track at index 1
    instead of unlocking an occupied ST1: existing subtitle clips retain their
    IDs, timing and track content, with only their track numbers increasing.
    The caller must already have created its BCK backup.
    """
    count = int(timeline.GetTrackCount("subtitle") or 0)
    before = {
        _identity(item): (track, int(item.GetStart()), int(item.GetEnd()), str(item.GetName()))
        for track in range(1, count + 1)
        for item in (timeline.GetItemListInTrack("subtitle", track) or [])
    }
    locks = [bool(timeline.GetIsTrackLocked("subtitle", track)) for track in range(1, count + 1)]
    added = timeline.AddTrack("subtitle", {"index": 1}) if count else timeline.AddTrack("subtitle")
    if added is False or int(timeline.GetTrackCount("subtitle") or 0) != count + 1:
        raise RuntimeError("Resolve could not reserve a new empty native Subtitle track at ST1")
    if timeline.GetItemListInTrack("subtitle", 1):
        raise RuntimeError("Resolve ignored the new ST1 position; existing subtitles were not overwritten")
    after = {
        _identity(item): (track, int(item.GetStart()), int(item.GetEnd()), str(item.GetName()))
        for track in range(2, count + 2)
        for item in (timeline.GetItemListInTrack("subtitle", track) or [])
    }
    expected = {identity: (track + 1, start, end, text)
                for identity, (track, start, end, text) in before.items()}
    if after != expected:
        raise RuntimeError("Resolve changed existing subtitles while reserving ST1")
    for track, locked in enumerate(locks, start=2):
        if timeline.SetTrackLock("subtitle", track, locked) is False:
            raise RuntimeError("Resolve could not preserve an existing Subtitle track lock")
    if timeline.SetTrackLock("subtitle", 1, False) is False:
        raise RuntimeError("Resolve could not unlock the empty new ST1")
    enable = getattr(timeline, "SetTrackEnable", None)
    if callable(enable) and enable("subtitle", 1, True) is False:
        raise RuntimeError("Resolve could not enable the new Subtitle track")
    return 1


def insert_native_subtitles(
    resolve: Any,
    project: Any,
    timeline: Any,
    rows: list[dict[str, Any]],
    fps: int,
    base_frame: int,
    srt_path: Path | None = None,
    target_track: int | None = None,
) -> list[Any]:
    """Import relative SRT and append it as genuine Resolve Subtitle items."""
    del resolve
    if not rows:
        return []
    if fps <= 0:
        raise ValueError("subtitle fps must be positive")
    start_getter = getattr(timeline, "GetStartFrame", None)
    timeline_start = int(start_getter()) if callable(start_getter) else int(base_frame)
    offset = (int(base_frame) - timeline_start) / fps
    if offset < 0:
        raise ValueError("Subtitle IN is before the start of the timeline")
    # SRT import is anchored to timeline start, not the playhead/current IN.
    srt_rows = [{**row, "start_seconds": float(row["start_seconds"]) + offset,
                 "end_seconds": float(row["end_seconds"]) + offset} for row in rows]
    wanted_track = int(target_track or 1)
    if wanted_track < 1:
        raise ValueError("target subtitle track must be >= 1")
    initial_track_count = int(timeline.GetTrackCount("subtitle") or 0)
    while int(timeline.GetTrackCount("subtitle") or 0) < wanted_track:
        added = timeline.AddTrack("subtitle")
        if added is False:
            raise RuntimeError("Resolve could not create the requested native Subtitle track")
    if target_track == 1 and _subtitle_items(timeline, 1):
        raise RuntimeError("Selective native subtitle import requires a reserved empty ST1")
    before = {_identity(item) for item in _subtitle_items(timeline)}
    if srt_path is None:
        handle, raw_path = tempfile.mkstemp(prefix="rambla-filtered-subs-", suffix=".srt")
        path = Path(raw_path)
        with os.fdopen(handle, "w", encoding="utf-8-sig", newline="\n") as stream:
            stream.write(render_filtered_srt(srt_rows))
    else:
        path = Path(srt_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_filtered_srt(srt_rows), encoding="utf-8-sig", newline="\n")
    try:
        pool = project.GetMediaPool()
        get_current_timecode = getattr(timeline, "GetCurrentTimecode", None)
        get_start_timecode = getattr(timeline, "GetStartTimecode", None)
        set_current_timecode = getattr(timeline, "SetCurrentTimecode", None)
        previous_timecode = get_current_timecode() if callable(get_current_timecode) else None
        start_timecode = get_start_timecode() if callable(get_start_timecode) else None
        # Resolve 21.1 binds an imported SRT's timeline origin while the media
        # is created, before AppendToTimeline. Keep the playhead at the timeline
        # start for both operations, then restore the user's position.
        if callable(set_current_timecode) and start_timecode:
            if set_current_timecode(str(start_timecode)) is False:
                raise RuntimeError("Resolve could not anchor native subtitles to the timeline start")
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
        # Legacy full export uses Resolve's native SRT append behavior on ST1.
        # Selective subtitle refreshes explicitly request a higher target track
        # through clipInfo and then verify where Resolve actually materialized it.
        get_lock = getattr(timeline, "GetIsTrackLocked", None)
        set_lock = getattr(timeline, "SetTrackLock", None)
        get_enabled = getattr(timeline, "GetIsTrackEnabled", None)
        set_enabled = getattr(timeline, "SetTrackEnable", None)
        subtitle_lock_states: dict[int, bool] = {}
        subtitle_enabled_states: dict[int, bool] = {}
        if get_lock is not None and set_lock is not None:
            for track in range(1, int(timeline.GetTrackCount("subtitle") or 0) + 1):
                subtitle_lock_states[track] = bool(get_lock("subtitle", track))
                if subtitle_lock_states[track] and set_lock("subtitle", track, False) is False:
                    raise RuntimeError(f"Resolve could not temporarily unlock Subtitle track {track}")
        if get_enabled is not None and set_enabled is not None:
            for track in range(1, int(timeline.GetTrackCount("subtitle") or 0) + 1):
                subtitle_enabled_states[track] = bool(get_enabled("subtitle", track))
                should_enable = track == wanted_track
                if subtitle_enabled_states[track] != should_enable:
                    if set_enabled("subtitle", track, should_enable) is False:
                        raise RuntimeError(f"Resolve could not isolate Subtitle track {wanted_track}")
        try:
            appended = (
                pool.AppendToTimeline(imported)
                if target_track is None or wanted_track == 1
                else pool.AppendToTimeline([{"mediaPoolItem": imported[0], "trackIndex": wanted_track}])
            )
            if not appended:
                raise RuntimeError("Resolve could not place the native Subtitle clips on the timeline")
        finally:
            if set_enabled is not None:
                for track, was_enabled in subtitle_enabled_states.items():
                    if bool(get_enabled("subtitle", track)) != was_enabled:
                        if set_enabled("subtitle", track, was_enabled) is False:
                            raise RuntimeError(f"Resolve could not restore Subtitle track {track} visibility")
            if set_lock is not None:
                for track, was_locked in subtitle_lock_states.items():
                    if was_locked and set_lock("subtitle", track, True) is False:
                        raise RuntimeError(f"Resolve could not restore Subtitle track {track} lock")
        inserted_on_target = [item for item in _subtitle_items(timeline, wanted_track) if _identity(item) not in before]
        inserted_anywhere = [item for item in _subtitle_items(timeline) if _identity(item) not in before]
        if not inserted_anywhere:
            raise RuntimeError("Resolve imported the SRT but created no native Subtitle clips")

        inserted = inserted_on_target or inserted_anywhere

        # Resolve 21.1 can ignore clipInfo.trackIndex for native subtitle media
        # and still create the captions correctly on ST1. Keep those valid new
        # items instead of deleting them and failing the whole Apply. If we had
        # created a brand-new upper target track that remained empty, remove it
        # so the user's timeline is not left with a useless blank subtitle track.
        if not inserted_on_target and target_track is not None and wanted_track > initial_track_count:
            target_items = list(timeline.GetItemListInTrack("subtitle", wanted_track) or [])
            delete_track = getattr(timeline, "DeleteTrack", None)
            if not target_items and delete_track is not None:
                delete_track("subtitle", wanted_track)
        return inserted
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        if "set_current_timecode" in locals() and callable(set_current_timecode) and previous_timecode:
            if set_current_timecode(str(previous_timecode)) is False:
                raise RuntimeError("Resolve could not restore the timeline playhead after Subtitle import")


def verify_native_subtitles(
    timeline: Any,
    rows: list[dict[str, Any]],
    fps: int,
    base_frame: int,
    track_index: int | None = None,
    items: list[Any] | None = None,
) -> None:
    del fps
    source_items = list(items) if items is not None else _subtitle_items(timeline, track_index)
    actual = sorted(
        (str(item.GetName()).strip(), int(item.GetStart()), int(item.GetEnd()))
        for item in source_items
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
