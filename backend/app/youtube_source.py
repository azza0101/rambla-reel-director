"""YouTube discovery normalization for evidence-first sourcing.

This module does not decide reuse rights and does not download media.  It turns
an injected discovery result into stable public metadata plus lightweight scene
evidence.  Bounded acquisition is handled separately by ``acquisition.py``.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from urllib.parse import urlsplit, urlunsplit

from .scene_locator import SceneEvidence


DiscoverFn = Callable[[str, int], Awaitable[list[dict[str, Any]]] | list[dict[str, Any]]]


@dataclass(frozen=True, slots=True)
class YouTubeCandidate:
    video_id: str
    query: str
    source_page: str
    title: str
    creator_name: str | None
    duration: float
    width: int
    height: int
    orientation: str
    thumbnail_url: str
    rights_state: str
    scene_evidence: tuple[SceneEvidence, ...]


def _orientation(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        return "unknown"
    if width == height:
        return "square"
    return "portrait" if height > width else "landscape"


def _safe_thumbnail(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return ""
    # Provider thumbnail query strings are transient and unnecessary for durable discovery metadata.
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def normalize_youtube_result(row: dict[str, Any], *, query: str) -> YouTubeCandidate:
    video_id = str(row.get("id") or row.get("video_id") or "").strip()
    if not video_id:
        raise ValueError("YouTube video id is required")
    if not query.strip():
        raise ValueError("YouTube discovery query is required")
    duration = float(row.get("duration") or 0.0)
    if duration <= 0:
        raise ValueError("YouTube duration is required")
    width = int(row.get("width") or 0)
    height = int(row.get("height") or 0)
    title = str(row.get("title") or f"YouTube video {video_id}").strip()
    creator_name = str(row.get("channel") or row.get("creator") or "").strip() or None
    thumbnail = _safe_thumbnail(row.get("thumbnail") or row.get("thumbnail_url"))

    evidence_rows: list[SceneEvidence] = []
    raw_evidence = row.get("scene_evidence") or []
    if isinstance(raw_evidence, list):
        for evidence in raw_evidence:
            if not isinstance(evidence, dict):
                continue
            timestamp = float(evidence.get("timestamp_seconds") or 0.0)
            if not 0.0 <= timestamp <= duration:
                continue
            score = float(evidence.get("metadata_score") or 0.0)
            score = max(0.0, min(1.0, score))
            evidence_rows.append(
                SceneEvidence(
                    timestamp_seconds=timestamp,
                    text=str(evidence.get("text") or "").strip(),
                    image_path=(str(evidence.get("image_path")).strip() if evidence.get("image_path") else None),
                    metadata_score=score,
                )
            )

    return YouTubeCandidate(
        video_id=video_id,
        query=query.strip(),
        source_page=f"https://www.youtube.com/watch?v={video_id}",
        title=title,
        creator_name=creator_name,
        duration=duration,
        width=width,
        height=height,
        orientation=_orientation(width, height),
        thumbnail_url=thumbnail,
        rights_state="review_required",
        scene_evidence=tuple(sorted(evidence_rows, key=lambda item: item.timestamp_seconds)),
    )


class YouTubeSource:
    """Thin injectable discovery adapter; no credentials or scraper dependency in core tests."""

    def __init__(self, *, discover: DiscoverFn):
        self.discover = discover

    async def search(
        self,
        query: str,
        *,
        min_duration: float,
        max_duration: float,
        limit: int,
    ) -> list[YouTubeCandidate]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("YouTube discovery query is required")
        if min_duration < 0 or max_duration <= 0 or min_duration > max_duration:
            raise ValueError("invalid duration bounds")
        if limit <= 0:
            raise ValueError("limit must be positive")

        result = self.discover(query.strip(), limit)
        raw = await result if inspect.isawaitable(result) else result
        if not isinstance(raw, list):
            raise ValueError("YouTube discovery must return a list")

        output: list[YouTubeCandidate] = []
        for row in raw:
            if not isinstance(row, dict):
                continue
            try:
                candidate = normalize_youtube_result(row, query=query.strip())
            except (TypeError, ValueError):
                continue
            if min_duration <= candidate.duration <= max_duration:
                output.append(candidate)
            if len(output) >= limit:
                break
        return output
