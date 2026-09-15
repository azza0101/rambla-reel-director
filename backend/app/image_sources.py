from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote

import httpx

from .online_assets import ProviderError


@dataclass(frozen=True, slots=True)
class RemoteImageCandidate:
    provider: str
    provider_id: str
    query: str
    source_page: str
    title: str
    description: str
    thumbnail_url: str
    full_url: str
    width: int
    height: int
    orientation: str
    rights_state: str
    provider_rank: int
    kind: str = "image"


class ImageSource(Protocol):
    async def search(self, query: str, *, limit: int) -> list[RemoteImageCandidate]: ...


def _orientation(width: int, height: int) -> str:
    return "square" if width == height else "portrait" if height > width else "landscape"


class WikimediaImageSource:
    endpoint = "https://commons.wikimedia.org/w/api.php"

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.transport = transport

    async def search(self, query: str, *, limit: int) -> list[RemoteImageCandidate]:
        params = {"action": "query", "format": "json", "generator": "search", "gsrsearch": query,
                  "gsrnamespace": 6, "gsrlimit": min(max(limit * 3, limit), 20), "prop": "imageinfo",
                  "iiprop": "url|size|mime|mediatype|extmetadata", "iiurlwidth": 640}
        async with httpx.AsyncClient(transport=self.transport, timeout=10, headers={"User-Agent": "RAMBLA-Curation/0.1 (local preview)"}) as client:
            response = await client.get(self.endpoint, params=params)
        if response.status_code >= 400:
            raise ProviderError("wikimedia", "http_error", "Wikimedia request failed")
        pages = response.json().get("query", {}).get("pages", {})
        output = []
        for rank, (page_id, page) in enumerate(pages.items() if isinstance(pages, dict) else []):
            info = (page.get("imageinfo") or [{}])[0]
            thumb, full = info.get("thumburl"), info.get("url")
            if not thumb or not full:
                continue
            mime = str(info.get("mime") or "")
            media_type = str(info.get("mediatype") or "").upper()
            if (mime and not mime.startswith("image/")) or (media_type and media_type not in {"BITMAP", "DRAWING"}):
                continue
            width, height = int(info.get("width") or 0), int(info.get("height") or 0)
            license_data = info.get("extmetadata", {}).get("LicenseShortName", {})
            rights = "known_public_license" if license_data.get("value") else "review_required"
            title = str(page.get("title") or page_id)
            output.append(RemoteImageCandidate("wikimedia", str(page_id), query,
                "https://commons.wikimedia.org/wiki/" + quote(title.replace(" ", "_")), title, "", thumb, full,
                width, height, _orientation(width, height), rights, rank))
        return output[:limit]


class PexelsPhotoSource:
    endpoint = "https://api.pexels.com/v1/search"

    def __init__(self, api_key: str | None, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.api_key = api_key.strip() if api_key else None
        self.transport = transport

    async def search(self, query: str, *, limit: int) -> list[RemoteImageCandidate]:
        if not self.api_key:
            raise ProviderError("pexels", "credential_required", "Pexels API key is not configured")
        async with httpx.AsyncClient(transport=self.transport, timeout=10, headers={"Authorization": self.api_key}) as client:
            response = await client.get(self.endpoint, params={"query": query, "per_page": min(limit, 80)})
        if response.status_code >= 400:
            raise ProviderError("pexels", "http_error", "Pexels request failed")
        output = []
        for rank, row in enumerate(response.json().get("photos", [])):
            src = row.get("src") or {}
            thumb, full = src.get("medium"), src.get("original")
            if not thumb or not full:
                continue
            width, height = int(row.get("width") or 0), int(row.get("height") or 0)
            output.append(RemoteImageCandidate("pexels", str(row.get("id")), query, str(row.get("url")),
                str(row.get("alt") or "Pexels photo"), "", thumb, full, width, height,
                _orientation(width, height), "provider_stock_terms", rank))
        return output[:limit]


async def search_image_candidates(query: str, *, sources: list[ImageSource], per_source_limit: int = 6) -> tuple[list[RemoteImageCandidate], list[dict[str, str]]]:
    results = await asyncio.gather(*(source.search(query, limit=per_source_limit) for source in sources), return_exceptions=True)
    rows: list[RemoteImageCandidate] = []
    errors: list[dict[str, str]] = []
    for source, result in zip(sources, results):
        if isinstance(result, Exception):
            errors.append({"provider": type(source).__name__.replace("ImageSource", "").casefold(), "code": getattr(result, "code", type(result).__name__)})
        else:
            rows.extend(result)
    seen: set[tuple[str, str]] = set()
    return [row for row in rows if not ((row.provider, row.provider_id) in seen or seen.add((row.provider, row.provider_id)))], errors
