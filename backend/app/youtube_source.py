"""YouTube discovery normalization for evidence-first sourcing.

This module does not decide reuse rights and does not download media. It turns
an injected discovery result into stable public metadata plus lightweight scene
evidence. ``YouTubeOnlineSourceAdapter`` exposes that metadata through the same
preview-ranking contract used by stock providers, while bounded acquisition is
handled separately by ``acquisition.py``.
"""

from __future__ import annotations

import asyncio
import inspect
import os
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from urllib.parse import urlsplit, urlunsplit

from .scene_locator import SceneEvidence
from .source_strategy import SOURCE_CLASSES


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
    source_class: str = "CLOSE_SEMANTIC_EDITORIAL"
    source_authenticity: float | None = None


@dataclass(frozen=True, slots=True)
class YouTubeRemoteCandidate:
    """Duck-compatible remote candidate enriched for long-video acquisition."""

    provider: str
    provider_id: str
    query: str
    source_page: str
    creator_name: str | None
    creator_page: str | None
    title: str
    description: str
    duration: float
    width: int
    height: int
    orientation: str
    preview_url: str
    selected_rendition_url: str
    rendition_width: int
    rendition_height: int
    rights_state: str
    provider_rank: int
    scene_evidence: tuple[SceneEvidence, ...]
    acquisition_mode: str
    source_duration: float
    source_class: str = "CLOSE_SEMANTIC_EDITORIAL"
    source_authenticity: float | None = None
    preview_rendition_url: str | None = None


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
    creator_name = str(row.get("channel") or row.get("creator") or row.get("uploader") or "").strip() or None
    thumbnail = _safe_thumbnail(row.get("thumbnail") or row.get("thumbnail_url"))
    source_class = str(row.get("source_class") or "CLOSE_SEMANTIC_EDITORIAL")
    if source_class not in SOURCE_CLASSES:
        raise ValueError("unsupported YouTube source class")
    authenticity = row.get("source_authenticity")
    if authenticity is not None:
        authenticity = float(authenticity)
        if not 0.0 <= authenticity <= 1.0:
            raise ValueError("source authenticity must be between 0 and 1")

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
        source_class=source_class,
        source_authenticity=authenticity,
    )


class YouTubeSource:
    """Thin injectable discovery adapter; no credentials or scraper dependency in core tests."""

    def __init__(self, *, discover: DiscoverFn):
        self.discover = discover

    async def search(self, query: str, *, min_duration: float, max_duration: float, limit: int) -> list[YouTubeCandidate]:
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


def _interleave(groups: list[list[Any]], limit: int) -> list[Any]:
    output=[]
    for index in range(max((len(group) for group in groups), default=0)):
        for group in groups:
            if index < len(group):
                output.append(group[index])
                if len(output) >= limit:
                    return output
    return output


class YouTubeOnlineSourceAdapter:
    """Expose YouTube plus optional portrait social discovery through one source port.

    The augmentation is opt-in through RAMBLA_ENABLE_VERTICAL_SOCIAL so existing
    offline/unit behavior never performs network discovery unexpectedly.
    """

    supported_source_classes = (
        "EXACT_RECEIPT", "EXACT_ENTITY_EVENT", "SOURCE_NATIVE_SOCIAL",
        "ARCHIVAL_REPERTORY", "PRODUCT_UI_DEMO", "CULTURAL_REFERENCE",
        "CLOSE_SEMANTIC_EDITORIAL",
    )

    def __init__(self, source: YouTubeSource, *, provider_name: str = "youtube", portrait_only: bool = False, vertical_sources: list[Any] | None = None):
        if provider_name not in {"youtube", "youtube_shorts"}:
            raise ValueError("unsupported YouTube provider identity")
        self.source = source
        self.provider_name = provider_name
        self.portrait_only = bool(portrait_only)
        self.vertical_sources = vertical_sources
        self._vertical_attempts: list[dict[str, Any]] = []

    def drain_vertical_attempts(self) -> list[dict[str, Any]]:
        attempts=list(self._vertical_attempts)
        self._vertical_attempts.clear()
        return attempts

    async def search(self, query: str, *, orientation: str | None, min_duration: float, max_duration: float, limit: int) -> list[Any]:
        if orientation is not None and orientation not in {"portrait", "landscape", "square"}:
            raise ValueError("unsupported orientation")
        rows = await self.source.search(query, min_duration=min_duration, max_duration=max_duration, limit=max(limit, limit * 3 if self.portrait_only else limit))
        normal: list[YouTubeRemoteCandidate] = []
        for rank, row in enumerate(rows):
            if self.portrait_only and row.orientation != "portrait":
                continue
            if orientation is not None and row.orientation != orientation:
                continue
            if not row.thumbnail_url:
                continue
            source_page = f"https://www.youtube.com/shorts/{row.video_id}" if self.provider_name == "youtube_shorts" else row.source_page
            normal.append(YouTubeRemoteCandidate(
                provider=self.provider_name, provider_id=row.video_id, query=row.query,
                source_page=source_page, creator_name=row.creator_name, creator_page=None,
                title=row.title, description=row.title, duration=row.duration,
                width=row.width, height=row.height, orientation=row.orientation,
                preview_url=row.thumbnail_url, selected_rendition_url=source_page,
                rendition_width=row.width, rendition_height=row.height,
                rights_state=row.rights_state, provider_rank=rank,
                scene_evidence=row.scene_evidence, acquisition_mode="bounded_window",
                source_duration=row.duration,
                source_class="SOURCE_NATIVE_SOCIAL" if self.provider_name == "youtube_shorts" else row.source_class,
                source_authenticity=row.source_authenticity,
            ))
            if len(normal) >= limit:
                break

        if self.provider_name != "youtube" or str(os.environ.get('RAMBLA_ENABLE_VERTICAL_SOCIAL','')).casefold() not in {'1','true','yes','on'}:
            return normal[:limit]

        if self.vertical_sources is None:
            from .vertical_social import build_default_vertical_sources
            vertical_sources = build_default_vertical_sources()
        else:
            vertical_sources = self.vertical_sources
        groups=[]
        outcomes=await asyncio.gather(*[
            source.search(query,orientation='portrait',min_duration=min_duration,max_duration=max_duration,limit=min(2,limit))
            for source in vertical_sources
        ],return_exceptions=True)
        for source,outcome in zip(vertical_sources,outcomes):
            provider=str(getattr(source,'provider_name',type(source).__name__))
            if isinstance(outcome,BaseException):
                self._vertical_attempts.append({'provider':provider,'query':query,'hits':0,'error':type(outcome).__name__})
                groups.append([])
                continue
            rows=list(outcome)
            attempt=dict(getattr(source,'last_attempt',{}) or {})
            attempt.setdefault('provider',provider);attempt.setdefault('query',query);attempt.setdefault('hits',len(rows))
            self._vertical_attempts.append(attempt)
            groups.append(rows)

        # Give each vertical provider one fair slot before normal long-form YouTube.
        return _interleave(groups+[normal],limit)
