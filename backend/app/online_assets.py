"""Online B-roll provider contracts and Pexels normalization.

This module is deliberately independent from Resolve and model inference.  It
turns provider responses into stable candidate metadata that later stages can
filter, preview, rank and persist safely.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

import httpx


@dataclass(frozen=True, slots=True)
class RemoteCandidate:
    """Provider-neutral remote video candidate before local materialization."""

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
    source_class: str = "GENERIC_STOCK"
    source_authenticity: float | None = None
    preview_rendition_url: str | None = None


class ProviderError(RuntimeError):
    """Sanitized provider failure; never contains credentials or signed URLs."""

    def __init__(self, provider: str, code: str, message: str):
        self.provider = provider
        self.code = code
        self.message = message
        super().__init__(f"{provider}:{code}: {message}")


def _safe_public_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return None
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _network_url(value: Any) -> str | None:
    """Validate a transient fetch URL while preserving its query/signature."""

    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return None
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None
    return value.strip()


def _positive_int(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def _positive_float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if number > 0 else 0.0


def _orientation(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        return "unknown"
    if width == height:
        return "square"
    return "portrait" if height > width else "landscape"


def _best_rendition(files: Iterable[dict[str, Any]], orientation: str) -> dict[str, Any] | None:
    valid: list[dict[str, Any]] = []
    for row in files:
        if not isinstance(row, dict):
            continue
        width = _positive_int(row.get("width"))
        height = _positive_int(row.get("height"))
        link = _network_url(row.get("link"))
        file_type = str(row.get("file_type") or "").lower()
        if not width or not height or not link or "mp4" not in file_type:
            continue
        valid.append({**row, "width": width, "height": height, "link": link})
    if not valid:
        return None

    def key(row: dict[str, Any]) -> tuple[int, int, int, str]:
        match = int(_orientation(row["width"], row["height"]) == orientation)
        quality = int(str(row.get("quality") or "").lower() == "hd")
        area = row["width"] * row["height"]
        return (match, area, quality, str(row.get("id") or ""))

    return max(valid, key=key)


def dedupe_candidates(rows: Iterable[RemoteCandidate]) -> list[RemoteCandidate]:
    """Stable provider-ID dedupe; first provider result wins."""

    seen: set[tuple[str, str]] = set()
    output: list[RemoteCandidate] = []
    for row in rows:
        key = (row.provider, row.provider_id)
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def filter_candidates(
    rows: Iterable[RemoteCandidate],
    *,
    orientation: str | None,
    min_duration: float,
    max_duration: float,
) -> list[RemoteCandidate]:
    if orientation is not None and orientation not in {"portrait", "landscape", "square"}:
        raise ValueError("unsupported orientation")
    if min_duration < 0 or max_duration <= 0 or min_duration > max_duration:
        raise ValueError("invalid duration bounds")

    filtered = [
        row
        for row in rows
        if (orientation is None or row.orientation == orientation)
        and min_duration <= row.duration <= max_duration
        and row.width > 0
        and row.height > 0
        and row.rendition_width > 0
        and row.rendition_height > 0
        and bool(row.source_page)
        and bool(row.preview_url)
        and bool(row.selected_rendition_url)
    ]
    return dedupe_candidates(filtered)


class PexelsSource:
    """Async Pexels video search with sanitized, provider-neutral output."""

    supported_source_classes = ("GENERIC_STOCK",)
    endpoint = "https://api.pexels.com/videos/search"

    def __init__(
        self,
        api_key: str | None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 10.0,
    ):
        self.api_key = api_key.strip() if isinstance(api_key, str) and api_key.strip() else None
        self.transport = transport
        self.timeout = timeout

    async def search(
        self,
        query: str,
        *,
        orientation: str | None,
        min_duration: float,
        max_duration: float,
        limit: int,
    ) -> list[RemoteCandidate]:
        if not self.api_key:
            raise ProviderError("pexels", "credential_required", "Pexels API key is not configured")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("search query must be non-empty")
        if orientation is not None and orientation not in {"portrait", "landscape", "square"}:
            raise ValueError("unsupported orientation")
        if min_duration < 0 or max_duration <= 0 or min_duration > max_duration:
            raise ValueError("invalid duration bounds")
        if limit <= 0:
            raise ValueError("limit must be positive")

        headers = {
            "Authorization": self.api_key,
            "User-Agent": "RAMBLA-Reel-Director/0.1",
        }
        params: dict[str, str | int] = {
            "query": query.strip(),
            "per_page": min(limit, 80),
        }
        if orientation is not None:
            params["orientation"] = orientation
        try:
            async with httpx.AsyncClient(
                transport=self.transport,
                timeout=self.timeout,
                headers=headers,
                follow_redirects=True,
            ) as client:
                response = await client.get(self.endpoint, params=params)
        except httpx.TimeoutException as exc:
            raise ProviderError("pexels", "timeout", "Pexels request timed out") from exc
        except httpx.RequestError as exc:
            raise ProviderError("pexels", "network_error", type(exc).__name__) from exc

        if response.status_code in {401, 403}:
            raise ProviderError("pexels", "credential_invalid", "Pexels rejected the configured credential")
        if response.status_code == 429:
            raise ProviderError("pexels", "rate_limited", "Pexels rate limit reached")
        if response.status_code >= 400:
            raise ProviderError("pexels", "http_error", f"Pexels returned HTTP {response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError("pexels", "invalid_response", "Pexels returned invalid JSON") from exc
        videos = payload.get("videos") if isinstance(payload, dict) else None
        if not isinstance(videos, list):
            raise ProviderError("pexels", "invalid_response", "Pexels response is missing videos")

        normalized: list[RemoteCandidate] = []
        for rank, video in enumerate(videos):
            candidate = self._normalize_video(video, query=query.strip(), provider_rank=rank)
            if candidate is not None:
                normalized.append(candidate)

        return filter_candidates(
            normalized,
            orientation=orientation,
            min_duration=min_duration,
            max_duration=max_duration,
        )[:limit]

    @staticmethod
    def _normalize_video(
        video: Any,
        *,
        query: str,
        provider_rank: int,
    ) -> RemoteCandidate | None:
        if not isinstance(video, dict):
            return None
        provider_id = str(video.get("id") or "").strip()
        width = _positive_int(video.get("width"))
        height = _positive_int(video.get("height"))
        duration = _positive_float(video.get("duration"))
        orientation = _orientation(width, height)
        source_page = _safe_public_url(video.get("url"))
        preview_url = _network_url(video.get("image"))
        rendition = _best_rendition(video.get("video_files") or [], orientation)
        if not provider_id or not source_page or not preview_url or rendition is None:
            return None

        creator = video.get("user") if isinstance(video.get("user"), dict) else {}
        creator_name = str(creator.get("name") or "").strip() or None
        creator_page = _safe_public_url(creator.get("url"))
        from urllib.parse import unquote
        slug=unquote(urlsplit(source_page).path).strip('/').split('/')[-1]
        inferred=' '.join(w for w in slug.split('-') if not w.isdigit())
        title = str(video.get("title") or (inferred if inferred!='video' else '') or f"Pexels video {provider_id}").strip()
        description = str(video.get("description") or title).strip()

        return RemoteCandidate(
            provider="pexels",
            provider_id=provider_id,
            query=query,
            source_page=source_page,
            creator_name=creator_name,
            creator_page=creator_page,
            title=title,
            description=description,
            duration=duration,
            width=width,
            height=height,
            orientation=orientation,
            preview_url=preview_url,
            selected_rendition_url=rendition["link"],
            preview_rendition_url=min((f for f in video.get('video_files',[]) if isinstance(f,dict) and 'mp4' in str(f.get('file_type','')) and _network_url(f.get('link')) and _positive_int(f.get('width'))>=480),key=lambda f:_positive_int(f.get('width'))*_positive_int(f.get('height')),default=rendition)['link'],
            rendition_width=rendition["width"],
            rendition_height=rendition["height"],
            rights_state="provider_stock_terms",
            provider_rank=provider_rank,
        )
