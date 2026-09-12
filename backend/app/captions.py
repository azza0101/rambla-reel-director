"""Timestamp-preserving caption artifact generation from local ASR segments."""

from __future__ import annotations

from fractions import Fraction
from typing import Any


def _srt_timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{millis:03d}"


def render_srt(segments: list[dict[str, Any]]) -> str:
    cues: list[str] = []
    previous_end = 0.0
    for index, segment in enumerate(segments, 1):
        start, end = float(segment["start"]), float(segment["end"])
        text = str(segment["text"]).strip()
        if start < previous_end:
            raise ValueError("caption segments overlap")
        if start < 0 or end <= start or not text:
            raise ValueError("caption segment has invalid time or text")
        cues.append(f"{index}\n{_srt_timestamp(start)} --> {_srt_timestamp(end)}\n{text}")
        previous_end = end
    return "\n\n".join(cues) + ("\n" if cues else "")


def validate_overlay_probe(probe: dict[str, Any], *, expected_frames: int, fps: int) -> int:
    videos = [stream for stream in probe.get("streams", []) if stream.get("codec_type") == "video"]
    if len(videos) != 1:
        raise ValueError("expected one caption video stream")
    stream = videos[0]
    if stream.get("pix_fmt") not in {"argb", "rgba", "yuva444p10le"}:
        raise ValueError("caption overlay lacks alpha channel")
    if Fraction(stream.get("r_frame_rate", "0/1")) != fps:
        raise ValueError("caption frame rate differs from timeline")
    frames = int(stream.get("nb_frames") or 0)
    if frames != expected_frames:
        raise ValueError("caption frame count differs from planned range")
    return frames


def validate_caption_target(
    source: dict[str, Any],
    target: dict[str, Any],
    *,
    name: str,
    broll_start: int,
    broll_end: int,
) -> None:
    if target.get("timeline_id") == source.get("timeline_id") or target.get("name") != name or not name.startswith("REEL_AI_v"):
        raise ValueError("caption target is not the expected generated duplicate")
    broll = [
        clip for clip in target.get("video", [])
        if clip.get("track") == 2 and clip.get("name") == "workflow-113f.mp4"
        and clip.get("start") == broll_start and clip.get("end") == broll_end
    ]
    if len(broll) != 1:
        raise ValueError("caption target B-roll is not at the verified exact range")
