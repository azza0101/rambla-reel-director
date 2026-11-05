"""Safe one-way capture from the active Resolve timeline into RAMBLA."""
from __future__ import annotations

import os
import sys
import time
import hashlib
import json
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=2)
def _visible_resolve_windows_for_period(period: int) -> tuple[tuple[int, str], ...]:
    if os.name != 'nt':
        return ()
    command = ("[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); "
               "@(Get-Process -Name Resolve -ErrorAction SilentlyContinue | "
               "Where-Object { $_.MainWindowTitle } | "
               "ForEach-Object { @{pid=$_.Id;title=$_.MainWindowTitle} }) | ConvertTo-Json -Compress")
    try:
        result = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=4,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), check=True)
        rows = json.loads(result.stdout or '[]')
        if isinstance(rows, dict): rows = [rows]
        return tuple((int(row['pid']), str(row['title'])) for row in rows if row.get('title'))
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError):
        return ()


def visible_resolve_windows() -> list[dict[str, Any]]:
    return [{'pid': pid, 'title': title} for pid, title in
            _visible_resolve_windows_for_period(int(time.monotonic() // 10))]


def missing_timeline_detail(project_name: str, windows: list[dict[str, Any]]) -> str:
    manager = [row for row in windows if str(row.get('title') or '').strip().casefold() == 'project manager']
    projects = [row for row in windows if str(row.get('title') or '').strip().casefold().startswith('davinci resolve')]
    if manager and projects:
        title = str(projects[0]['title'])
        return (f'RMBL legge "{project_name or "nessun progetto"}" senza timeline, ma rileva anche "{title}". '
                'Potrebbero esserci due istanze Resolve: salva e chiudi solo la finestra Project Manager, '
                'poi riprova RICOLLEGA BRIDGE.')
    return f'Resolve risponde, ma il progetto "{project_name or "nessuno"}" non ha una timeline attiva. Apri la timeline e riprova.'


def timeline_range(timeline: Any) -> tuple[int, int, str]:
    timeline_start = int(timeline.GetStartFrame())
    timeline_end = int(timeline.GetEndFrame()) - 1
    relative_end = max(0, timeline_end - timeline_start)

    def absolute_mark(value: Any) -> int:
        frame = int(value)
        # Resolve 21 reports timeline marks relative to the timeline start,
        # even when the timeline itself starts at a large timecode frame.
        if 0 <= frame <= relative_end:
            return timeline_start + frame
        return frame

    marks = timeline.GetMarkInOut() or {}
    for kind in ("audio", "video"):
        row = marks.get(kind) or {}
        if "in" in row or "out" in row:
            mark_in = absolute_mark(row.get("in", 0))
            mark_out = absolute_mark(row.get("out", relative_end))
            mark_in = max(timeline_start, min(timeline_end, mark_in))
            mark_out = max(timeline_start, min(timeline_end, mark_out))
            if mark_out >= mark_in:
                return mark_in, mark_out, kind
    return timeline_start, timeline_end, "timeline"


def require_explicit_capture_range(range_source: str) -> None:
    """Prevent a forced IN/OUT capture from silently rendering everything."""
    if str(range_source or "timeline") == "timeline":
        raise ValueError("Imposta i punti IN e OUT in Resolve prima di ricalcolare l'audio")


def detect_video_ranges(timeline: Any, mark_in: int, mark_out: int, fps: float,
                        include_v1: bool = False) -> list[dict[str, Any]]:
    """Return enabled overlay ranges, optionally including the base V1 track."""
    if fps <= 0:
        return []
    ranges: list[dict[str, Any]] = []
    first_track = 1 if include_v1 else 2
    for track in range(first_track, int(timeline.GetTrackCount("video") or 0) + 1):
        if timeline.GetIsTrackEnabled("video", track) is False:
            continue
        track_name = str(timeline.GetTrackName("video", track) or f"V{track}")
        for item in timeline.GetItemListInTrack("video", track) or []:
            start = max(mark_in, int(item.GetStart()))
            end = min(mark_out + 1, int(item.GetEnd()))
            if end <= start:
                continue
            ranges.append({
                "start": round((start - mark_in) / fps, 6),
                "end": round((end - mark_in) / fps, 6),
                "track": track,
                "track_name": track_name,
                "clip_name": str(item.GetName() or "Video"),
            })
    return sorted(ranges, key=lambda row: (row["start"], row["end"], row["track"]))


def phrase_has_video(start: float, end: float, ranges: list[dict[str, Any]], threshold: float = .5) -> bool:
    duration = max(0.001, float(end) - float(start))
    intersections = sorted(
        (max(float(start), float(row["start"])), min(float(end), float(row["end"])))
        for row in ranges
        if min(float(end), float(row["end"])) > max(float(start), float(row["start"]))
    )
    covered = 0.0; cursor = float(start)
    for left, right in intersections:
        left = max(left, cursor)
        if right > left:
            covered += right - left; cursor = right
    return covered / duration >= threshold


def _call(value: Any, name: str, *args: Any, default: Any = None) -> Any:
    try:
        method = getattr(value, name, None)
        return method(*args) if callable(method) else default
    except Exception:
        return default


def timeline_audio_fingerprint(timeline: Any, mark_in: int, mark_out: int, fps: float) -> str:
    """Stable signature for the audible edit inside the captured interval."""
    payload: dict[str, Any] = {
        "timeline_id": str(_call(timeline, "GetUniqueId", default="") or ""),
        "mark_in": int(mark_in), "mark_out": int(mark_out), "fps": float(fps), "tracks": [],
    }
    for track in range(1, int(_call(timeline, "GetTrackCount", "audio", default=0) or 0) + 1):
        enabled = _call(timeline, "GetIsTrackEnabled", "audio", track, default=True) is not False
        row = {"index": track, "enabled": enabled,
               "name": str(_call(timeline, "GetTrackName", "audio", track, default=f"A{track}") or f"A{track}"),
               "items": []}
        if enabled:
            for item in _call(timeline, "GetItemListInTrack", "audio", track, default=[]) or []:
                start = float(_call(item, "GetStart", True, default=_call(item, "GetStart", default=0)) or 0)
                end = float(_call(item, "GetEnd", True, default=_call(item, "GetEnd", default=0)) or 0)
                if end <= mark_in or start >= mark_out + 1:
                    continue
                media = _call(item, "GetMediaPoolItem")
                row["items"].append({
                    "id": str(_call(item, "GetUniqueId", default="") or ""),
                    "media_id": str(_call(media, "GetUniqueId", default="") or ""),
                    "name": str(_call(item, "GetName", default="") or ""),
                    "start": start, "end": end,
                    "left_offset": _call(item, "GetLeftOffset", True, default=_call(item, "GetLeftOffset", default=0)),
                    "right_offset": _call(item, "GetRightOffset", True, default=_call(item, "GetRightOffset", default=0)),
                })
        payload["tracks"].append(row)
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def count_audio_items(timeline: Any, mark_in: int, mark_out: int) -> int:
    count=0
    for track in range(1,int(_call(timeline,"GetTrackCount","audio",default=0) or 0)+1):
        if _call(timeline,"GetIsTrackEnabled","audio",track,default=True) is False: continue
        for item in _call(timeline,"GetItemListInTrack","audio",track,default=[]) or []:
            start=float(_call(item,"GetStart",True,default=_call(item,"GetStart",default=0)) or 0)
            end=float(_call(item,"GetEnd",True,default=_call(item,"GetEnd",default=0)) or 0)
            if end>mark_in and start<mark_out+1: count+=1
    return count


def can_reuse_audio_capture(previous: dict[str, Any], current: dict[str, Any], *, guide_ready: bool,
                            force_recalculate: bool = False) -> bool:
    """Reuse a guide only for the exact same, still-audible Resolve edit."""
    if force_recalculate or not guide_ready or int(current.get("audio_item_count") or 0) <= 0:
        return False
    identity_fields = ("resolve_timeline_id", "mark_in", "mark_out", "fps")
    if any(str(previous.get(key)) != str(current.get(key)) for key in identity_fields):
        return False
    fingerprint = str(current.get("audio_fingerprint") or "")
    return bool(fingerprint and fingerprint == str(previous.get("audio_fingerprint") or ""))


def inspect_active_timeline(*, resolve: Any | None = None, detect_videos: bool = True,
                            include_v1: bool = False, include_cut_snapshot: bool = False) -> dict[str, Any]:
    resolve = resolve or connect_resolve()
    project = resolve.GetProjectManager().GetCurrentProject()
    if not project:
        raise RuntimeError("Apri un progetto DaVinci Resolve")
    timeline = project.GetCurrentTimeline()
    if not timeline:
        raise RuntimeError("Apri una timeline DaVinci Resolve")
    start, end, range_source = timeline_range(timeline)
    fps = float(timeline.GetSetting("timelineFrameRate") or 0)
    result = {
        "resolve_project": project.GetName(), "resolve_timeline": timeline.GetName(),
        "resolve_timeline_id": str(timeline.GetUniqueId()), "fps": fps,
        "mark_in": start, "mark_out": end, "range_source": range_source,
        "duration": (end - start + 1) / fps,
        "detect_videos": bool(detect_videos),
        "include_v1": bool(include_v1),
        "existing_video_ranges": detect_video_ranges(timeline, start, end, fps, include_v1) if detect_videos else [],
        "audio_item_count": count_audio_items(timeline,start,end),
        "audio_fingerprint": timeline_audio_fingerprint(timeline, start, end, fps),
    }
    if include_cut_snapshot:
        from .resolve_cut_source import capture_cut_source
        try:
            result['cut_source'] = capture_cut_source(timeline,start,end)
        except Exception as exc:
            result['cut_source'] = {'supported':False,'issues':[f'Snapshot CUT non disponibile: {type(exc).__name__}: {exc}']}
    return result


def connect_resolve() -> Any:
    api = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Blackmagic Design/DaVinci Resolve/Support/Developer/Scripting"
    modules = str(api / "Modules")
    if modules not in sys.path:
        sys.path.insert(0, modules)
    os.environ.setdefault("RESOLVE_SCRIPT_API", str(api))
    os.environ.setdefault("RESOLVE_SCRIPT_LIB", r"C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll")
    import DaVinciResolveScript as dvr  # type: ignore
    resolve = dvr.scriptapp("Resolve")
    if not resolve:
        raise RuntimeError("DaVinci Resolve non è aperto")
    return resolve


def capture_active_timeline(output_dir: Path, *, resolve: Any | None = None, timeout: float = 300,
                            detect_videos: bool = True, include_v1: bool = False) -> dict[str, Any]:
    resolve = resolve or connect_resolve()
    pm = resolve.GetProjectManager(); project = pm.GetCurrentProject()
    if not project:
        raise RuntimeError("Apri un progetto DaVinci Resolve")
    timeline = project.GetCurrentTimeline()
    if not timeline:
        raise RuntimeError("Apri una timeline DaVinci Resolve")
    start, end, range_source = timeline_range(timeline)
    fps = float(timeline.GetSetting("timelineFrameRate") or 0)
    existing_video_ranges = detect_video_ranges(timeline, start, end, fps, include_v1) if detect_videos else []
    audio_fingerprint = timeline_audio_fingerprint(timeline, start, end, fps)
    from .resolve_cut_source import capture_cut_source
    try:
        cut_source = capture_cut_source(timeline, start, end)
    except Exception as exc:
        cut_source = {'supported':False,'issues':[f'Snapshot CUT non disponibile: {type(exc).__name__}: {exc}']}
    output_dir = Path(output_dir).resolve(); output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"rambla-bridge-{int(time.time() * 1000)}"
    previous_format = project.GetCurrentRenderFormatAndCodec() or {}
    previous_mode = project.GetCurrentRenderMode()
    # Resolve's scripting API does not expose MP3 and advertises Wave without a
    # selectable codec. Render AAC in a tiny MP4 from a disposable duplicate.
    # Disabling video only on the duplicate makes long captures much faster and
    # guarantees that the editor's source timeline is never changed.
    media_pool = project.GetMediaPool()
    render_timeline = timeline.DuplicateTimeline(f"__RAMBLA_AUDIO_CAPTURE__{int(time.time())}")
    if render_timeline:
        if project.SetCurrentTimeline(render_timeline):
            for index in range(1, int(render_timeline.GetTrackCount("video") or 0) + 1):
                render_timeline.SetTrackEnable("video", index, False)
        else:
            media_pool.DeleteTimelines([render_timeline]); render_timeline = timeline
    else:
        render_timeline = timeline
    job = None
    try:
        files = []
        failures = []
        successful_label = ""
        for label, codec in (("Audio Only", None), ("H264_NVIDIA", "H264_NVIDIA"), ("H264", "H264")):
            if codec is None:
                if project.LoadRenderPreset("Audio Only") is False:
                    failures.append(f"{label}: preset non disponibile")
                    continue
            elif project.SetCurrentRenderFormatAndCodec("mp4", codec) is False:
                failures.append(f"{label}: non disponibile")
                continue
            project.SetCurrentRenderMode(1)
            settings = {"TargetDir": str(output_dir), "CustomName": stem, "SelectAllFrames": False,
                        "MarkIn": start, "MarkOut": end, "ExportVideo": codec is not None, "ExportAudio": True}
            if codec is not None:
                settings.update({"FormatWidth": 320, "FormatHeight": 180, "AudioCodec": "aac",
                                 "AudioSampleRate": 48000})
            if project.SetRenderSettings(settings) is False:
                failures.append(f"{label}: impostazioni rifiutate")
                continue
            job = project.AddRenderJob()
            if not job:
                failures.append(f"{label}: job non creato")
                continue
            started = project.StartRendering([job], False)
            if started is not False:
                deadline = time.monotonic() + timeout
                while project.IsRenderingInProgress() and time.monotonic() < deadline:
                    time.sleep(.25)
                status = project.GetRenderJobStatus(job) or {}
                if project.IsRenderingInProgress():
                    project.StopRendering(); failures.append(f"{label}: timeout")
                elif str(status.get("JobStatus") or "").casefold() in {"complete", "completed"}:
                    files = sorted(output_dir.glob(stem + ".*"), key=lambda p: p.stat().st_mtime_ns, reverse=True)
                    if files:
                        successful_label = label
                        break
                    failures.append(f"{label}: file non prodotto")
                else:
                    failures.append(f"{label}: {status.get('JobStatus') or 'stato sconosciuto'}")
            else:
                failures.append(f"{label}: avvio fallito")
            project.DeleteRenderJob(job); job = None
        if not files:
            raise RuntimeError("Render audio non completato (" + " · ".join(failures) + ")")
        return {"audio_path": str(files[0]), "resolve_project": project.GetName(),
                "resolve_timeline": timeline.GetName(), "resolve_timeline_id": str(timeline.GetUniqueId()),
                "fps": fps, "mark_in": start, "mark_out": end, "range_source": range_source,
                "duration": (end - start + 1) / fps, "detect_videos": bool(detect_videos),
                "include_v1": bool(include_v1),
                "existing_video_ranges": existing_video_ranges,
                "audio_fingerprint": audio_fingerprint, "reused_audio": False,
                "cut_source": cut_source,
                "audio_capture_format": ("WAV Audio Only" if successful_label == "Audio Only" else successful_label + " MP4/AAC") + " (temporary copy)"}
    finally:
        if job:
            project.DeleteRenderJob(job)
        if previous_format.get("format") and previous_format.get("codec"):
            project.SetCurrentRenderFormatAndCodec(previous_format["format"], previous_format["codec"])
        project.SetCurrentRenderMode(previous_mode)
        project.SetCurrentTimeline(timeline)
        if render_timeline is not timeline:
            media_pool.DeleteTimelines([render_timeline])
