"""Best-effort portrait social discovery for Shorts, TikTok and Instagram.

Discovery is deliberately separate from editorial reasoning. It returns public,
portrait candidates that the existing bounded clip localizer can materialize and
Qwen-rank. TikTok/Instagram remain opportunistic public-web providers: failures
are isolated and never block YouTube Shorts, stock, images, or project restore.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs, unquote, urlparse

import httpx


VERTICAL_PROVIDERS = {"youtube_shorts", "tiktok", "instagram"}


@dataclass(frozen=True, slots=True)
class VerticalRemoteCandidate:
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
    scene_evidence: tuple[Any, ...] = ()
    acquisition_mode: str = "bounded_window"
    source_duration: float = 0.0
    source_class: str = "SOURCE_NATIVE_SOCIAL"
    source_authenticity: float | None = None
    preview_rendition_url: str | None = None


class _ResultLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "a":
            return
        values = {key: value for key, value in attrs}
        classes = (values.get("class") or "").split()
        href = values.get("href")
        if href and "result__a" in classes:
            self.hrefs.append(href)


def social_search_phrases(query: str) -> list[str]:
    """Keep semantic intent first, then add phone-native discovery vocabulary."""
    base = " ".join(str(query or "").split())
    if not base:
        return []
    values = [base, f"{base} pov", f"{base} iphone", f"{base} candid phone video"]
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.casefold()
        if key not in seen:
            seen.add(key); out.append(value)
    return out[:4]


def _unwrap_search_href(href: str) -> str:
    value = href.strip()
    if value.startswith("//"):
        value = "https:" + value
    parsed = urlparse(value)
    if parsed.hostname and parsed.hostname.endswith("duckduckgo.com"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        if target:
            return unquote(target)
    return value


def _provider_url(value: str, provider: str) -> str | None:
    try:
        parsed = urlparse(value)
    except ValueError:
        return None
    host = (parsed.hostname or "").casefold()
    path = parsed.path or ""
    if parsed.scheme not in {"http", "https"}:
        return None
    if provider == "tiktok":
        if not host.endswith("tiktok.com") or "/video/" not in path or "/@" not in path:
            return None
    elif provider == "instagram":
        if not host.endswith("instagram.com") or not (path.startswith("/reel/") or path.startswith("/reels/")):
            return None
    else:
        return None
    return f"https://{host}{path}"


def extract_search_links(html: str, provider: str, *, limit: int) -> list[str]:
    if provider not in {"tiktok", "instagram"}:
        raise ValueError("unsupported web social provider")
    if limit <= 0:
        return []
    parser = _ResultLinkParser(); parser.feed(html or "")
    output: list[str] = []; seen: set[str] = set()
    for href in parser.hrefs:
        public = _provider_url(_unwrap_search_href(href), provider)
        if public and public not in seen:
            seen.add(public); output.append(public)
        if len(output) >= limit:
            break
    return output


def _dimensions(info: dict[str, Any]) -> tuple[int, int]:
    width = int(info.get("width") or 0); height = int(info.get("height") or 0)
    if width > 0 and height > 0:
        return width, height
    best = (0, 0)
    for row in info.get("formats") or []:
        if not isinstance(row, dict): continue
        w, h = int(row.get("width") or 0), int(row.get("height") or 0)
        if w > 0 and h > 0 and w * h > best[0] * best[1]: best = (w, h)
    return best


def _thumbnail(info: dict[str, Any]) -> str:
    direct = str(info.get("thumbnail") or "").strip()
    if direct.startswith(("http://", "https://")): return direct
    rows = [row for row in info.get("thumbnails") or [] if isinstance(row, dict) and str(row.get("url") or "").startswith(("http://", "https://"))]
    if not rows: return ""
    best = max(rows, key=lambda row: int(row.get("width") or 0) * int(row.get("height") or 0))
    return str(best.get("url") or "")


def normalize_social_metadata(provider: str, source_page: str, query: str, info: dict[str, Any], *, provider_rank: int) -> VerticalRemoteCandidate:
    if provider not in VERTICAL_PROVIDERS: raise ValueError("unsupported vertical social provider")
    if not query.strip(): raise ValueError("search query is required")
    if provider in {"tiktok", "instagram"}: source_page = _provider_url(source_page, provider) or ""
    if not source_page.startswith(("http://", "https://")): raise ValueError("public source URL is required")
    width, height = _dimensions(info)
    dimensions_known = width > 0 and height > 0
    if dimensions_known and height <= width:
        raise ValueError("vertical social result must be portrait")
    if not dimensions_known and provider != "youtube_shorts":
        raise ValueError("vertical social result must be portrait")
    duration = float(info.get("duration") or 0.0)
    if duration <= 0: raise ValueError("duration is required")
    provider_id = str(info.get("id") or source_page.rstrip("/").split("/")[-1]).strip()
    if not provider_id: raise ValueError("provider id is required")
    thumb = _thumbnail(info)
    if not thumb and provider == "youtube_shorts":
        thumb = f"https://i.ytimg.com/vi/{provider_id}/hqdefault.jpg"
    if not thumb: raise ValueError("thumbnail is required")
    title = str(info.get("title") or info.get("description") or f"{provider} video {provider_id}").strip()
    creator = str(info.get("uploader") or info.get("channel") or info.get("creator") or "").strip() or None
    authenticity = .94 if provider == "youtube_shorts" else .98
    return VerticalRemoteCandidate(
        provider=provider, provider_id=provider_id, query=query.strip(), source_page=source_page,
        creator_name=creator, creator_page=None, title=title,
        description=str(info.get("description") or title).strip(), duration=duration,
        width=width, height=height, orientation="portrait", preview_url=thumb,
        selected_rendition_url=source_page, rendition_width=width, rendition_height=height,
        rights_state="review_required", provider_rank=provider_rank, source_duration=duration,
        source_authenticity=authenticity,
    )


def _probe_with_ytdlp(url: str) -> dict[str, Any]:
    from yt_dlp import YoutubeDL
    options = {"quiet": True,"no_warnings": True,"skip_download": True,"noplaylist": True,"socket_timeout": 10,"retries": 0}
    with YoutubeDL(options) as ydl: value = ydl.extract_info(url, download=False)
    return value if isinstance(value, dict) else {}


def _search_youtube_shorts(query: str, limit: int) -> list[dict[str, Any]]:
    """Use cheap flat discovery; real orientation is verified on the bounded clip.

    Fully extracting every ytsearch entry multiplied network calls and also made
    Shorts discovery brittle. Flat rows normally contain id/title/duration, which
    is enough to build /shorts/{id}; missing dimensions are intentionally deferred.
    """
    from yt_dlp import YoutubeDL
    count = max(6, min(18, limit * 4))
    options = {
        "quiet": True,"no_warnings": True,"skip_download": True,
        "extract_flat": "in_playlist","playlistend": count,
        "socket_timeout": 10,"retries": 0,
    }
    with YoutubeDL(options) as ydl:
        payload = ydl.extract_info(f"ytsearch{count}:{query} #shorts", download=False)
    return [entry for entry in payload.get("entries", []) if isinstance(entry, dict)] if isinstance(payload, dict) else []


SearchHtml = Callable[[str], Awaitable[str]]
ProbeFn = Callable[[str], Awaitable[dict[str, Any]]]


class VerticalSocialSource:
    """Portrait-only best-effort source. Failures stay provider-local."""
    supported_source_classes = ("SOURCE_NATIVE_SOCIAL", "CLOSE_SEMANTIC_EDITORIAL")

    def __init__(self, provider: str, *, search_html: SearchHtml | None = None, probe: ProbeFn | None = None) -> None:
        if provider not in VERTICAL_PROVIDERS: raise ValueError("unsupported vertical social provider")
        self.provider_name = provider; self.search_html = search_html; self.probe = probe; self.last_attempt: dict[str, Any] = {}

    async def _web_html(self, phrase: str) -> str:
        if self.search_html is not None: return await self.search_html(phrase)
        domain = 'site:tiktok.com "/video/"' if self.provider_name == "tiktok" else 'site:instagram.com/reel'
        search = f"{domain} {phrase}"
        async with httpx.AsyncClient(timeout=12, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 RAMBLA-Reel-Director/0.5"}) as client:
            response = await client.get("https://html.duckduckgo.com/html/", params={"q": search}); response.raise_for_status(); return response.text

    async def _probe(self, url: str) -> dict[str, Any]:
        if self.probe is not None: return await self.probe(url)
        return await asyncio.to_thread(_probe_with_ytdlp, url)

    async def search(self, query: str, *, orientation: str | None, min_duration: float, max_duration: float, limit: int) -> list[VerticalRemoteCandidate]:
        if not query.strip() or limit <= 0: return []
        if orientation not in {None, "portrait"}: return []
        candidates: list[VerticalRemoteCandidate] = []; errors: list[str] = []; seen_pages: set[str] = set(); used_phrases: list[str] = []
        try:
            for phrase in social_search_phrases(query.strip()):
                if len(candidates) >= limit: break
                used_phrases.append(phrase)
                if self.provider_name == "youtube_shorts":
                    infos = await asyncio.to_thread(_search_youtube_shorts, phrase, min(limit * 3, 12))
                    rows = []
                    for info in infos:
                        video_id = str(info.get("id") or "").strip()
                        if video_id: rows.append((f"https://www.youtube.com/shorts/{video_id}", info))
                else:
                    html = await self._web_html(phrase)
                    urls = extract_search_links(html, self.provider_name, limit=max(3, limit * 2))
                    rows = []
                    for url in urls:
                        if url in seen_pages: continue
                        seen_pages.add(url)
                        try: rows.append((url, await self._probe(url)))
                        except Exception as exc: errors.append(type(exc).__name__)
                for source_page, info in rows:
                    if source_page in seen_pages and self.provider_name == 'youtube_shorts':
                        continue
                    seen_pages.add(source_page)
                    try: row = normalize_social_metadata(self.provider_name, source_page, query, info, provider_rank=len(candidates))
                    except (TypeError, ValueError): continue
                    if not (min_duration <= row.duration <= min(max_duration, 240.0)): continue
                    candidates.append(row)
                    if len(candidates) >= limit: break
            self.last_attempt = {"provider": self.provider_name,"query": query.strip(),"phrases": used_phrases,"hits": len(candidates),"errors": errors}
            return candidates
        except Exception as exc:
            self.last_attempt = {"provider": self.provider_name,"query": query.strip(),"phrases": used_phrases,"hits": 0,"error": type(exc).__name__}
            return []


def build_default_vertical_sources() -> list[Any]:
    """Build Shorts/social sources plus an optional Google Videos discovery lane."""
    public = {
        provider: VerticalSocialSource(provider)
        for provider in ("youtube_shorts", "tiktok", "instagram")
    }
    browser_enabled = str(os.environ.get("RAMBLA_ENABLE_SOCIAL_BROWSER", "")).casefold() in {"1", "true", "yes", "on"}
    web_enabled = str(os.environ.get("RAMBLA_ENABLE_WEB_VIDEO", "")).casefold() in {"1", "true", "yes", "on"}

    if browser_enabled:
        from .browser_profiles import BrowserProfileManager
        from .social_browser_source import BrowserSocialSource

        root = Path(os.environ.get(
            "RAMBLA_BROWSER_PROFILE_ROOT",
            str(Path.home() / ".rambla-reel-director" / "browser-profiles"),
        ))
        manager = BrowserProfileManager(root)
        sources: list[Any] = [
            public["youtube_shorts"],
            BrowserSocialSource("tiktok", manager, fallback=public["tiktok"]),
            BrowserSocialSource("instagram", manager, fallback=public["instagram"]),
        ]
    else:
        sources = [public["youtube_shorts"], public["tiktok"], public["instagram"]]

    if web_enabled:
        from .web_video_source import WebVideoSource
        sources.append(WebVideoSource())
    return sources
