"""Envato Elements stock-video discovery.

Search/preview only. This provider never downloads or licenses Envato assets.
The curator opens the official item page in their own logged-in browser.
"""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import os
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import quote_plus, urljoin, urlparse

import httpx



DiscoverFn = Callable[[str, int], Awaitable[list[dict[str, Any]]] | list[dict[str, Any]]]


def parse_mcp_result(body: str) -> list[dict[str, Any]]:
    """Parse the official Streamable HTTP JSON/SSE tool response, not its UI."""
    messages = [json.loads(line[5:].strip()) for line in body.splitlines() if line.startswith('data:')]
    if not messages:
        messages = [json.loads(body)]
    envelope = messages[-1]
    if envelope.get('error'):
        raise ValueError('Envato MCP protocol error')
    result = envelope.get('result', {})
    if result.get('isError'):
        raise ValueError('Envato MCP search failed')
    for block in result.get('content', []):
        if block.get('type') == 'text':
            payload = json.loads(block['text'])
            if isinstance(payload.get('items'), list):
                return [{'source_page': r.get('item_url'), 'preview_url': r.get('cover_image'),
                         'title': r.get('title'), 'author': r.get('author')} for r in payload['items']]
    raise ValueError('Envato MCP parser mismatch: items missing')


async def _mcp_discover(query: str, limit: int) -> list[dict[str, Any]]:
    # Official endpoint and search_stock_video schema verified against tools/list.
    async with httpx.AsyncClient(timeout=12) as client:
        response = await client.post('https://mcp.envato.com/mcp',
            headers={'Accept': 'application/json, text/event-stream'},
            json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {
                'name': 'search_stock_video', 'arguments': {'searchTerms': query[:60],
                'perPage': min(20, limit), 'sortBy': 'relevance',
                'filters': {'categories': 'Stock Footage'}}}})
        response.raise_for_status()
    return parse_mcp_result(response.text)
_ITEM_PATH = re.compile(r"/[^?#]+-[A-Z0-9]{6,12}/?$", re.I)


@dataclass(frozen=True, slots=True)
class EnvatoRemoteCandidate:
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
    source_authenticity: float | None = .97
    acquisition_mode: str = "manual_link"
    source_duration: float = 0.0
    preview_rendition_url: str | None = None


def _clean_item_url(value: str) -> str | None:
    raw = str(value or "").strip()
    if raw.startswith("/"):
        raw = urljoin("https://elements.envato.com", raw)
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None
    host = (parsed.hostname or "").casefold()
    if parsed.scheme not in {"http", "https"} or host != "elements.envato.com":
        return None
    if not _ITEM_PATH.fullmatch(parsed.path or ""):
        return None
    return f"https://elements.envato.com{parsed.path.rstrip('/')}"


def _image_from_attrs(values: dict[str, str | None]) -> str:
    for key in ("src", "data-src", "data-lazy-src"):
        value = str(values.get(key) or "").strip()
        if value.startswith(("https://", "http://")):
            return value
    srcset = str(values.get("srcset") or "").strip()
    if srcset:
        candidates = [part.strip().split()[0] for part in srcset.split(",") if part.strip()]
        for value in reversed(candidates):
            if value.startswith(("https://", "http://")):
                return value
    return ""


class _EnvatoSearchParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.current: dict[str, Any] | None = None
        self.rows: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value for key, value in attrs}
        if tag.casefold() == "a":
            source = _clean_item_url(str(values.get("href") or ""))
            if source:
                self.current = {
                    "source_page": source,
                    "title": "",
                    "preview_url": "",
                    "alt": "",
                }
                return
        if tag.casefold() == "img" and self.current is not None:
            preview = _image_from_attrs(values)
            if preview and not self.current["preview_url"]:
                self.current["preview_url"] = preview
            alt = " ".join(str(values.get("alt") or "").split())
            if alt and not self.current["alt"]:
                self.current["alt"] = alt

    def handle_data(self, data: str) -> None:
        if self.current is not None:
            self.current["title"] += " " + str(data or "")

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "a" or self.current is None:
            return
        row = self.current
        self.current = None
        title = " ".join(str(row.get("title") or "").split())
        alt = " ".join(str(row.get("alt") or "").split())
        row["title"] = alt or title
        if row["source_page"] and row["preview_url"] and row["title"]:
            self.rows.append(row)


def parse_envato_search_html(html: str, *, limit: int) -> list[dict[str, Any]]:
    parser = _EnvatoSearchParser()
    parser.feed(html or "")
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in parser.rows:
        source = str(row.get("source_page") or "")
        if not source or source in seen:
            continue
        seen.add(source)
        output.append(row)
        if len(output) >= limit:
            break
    return output


def _search_url(query: str) -> str:
    clean = " ".join(str(query or "").split())
    # Envato's current SEO search routes encode spaces as literal '+' tokens
    # in the path (surfaced as %2B in canonical URLs).
    token = quote_plus(clean).replace("+", "%2B")
    return "https://elements.envato.com/stock-video/" + token


async def _http_discover(query: str, limit: int) -> list[dict[str, Any]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/153 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
        response = await client.get(_search_url(query))
        response.raise_for_status()
    return parse_envato_search_html(response.text, limit=limit)


async def _default_discover(query: str, limit: int) -> list[dict[str, Any]]:
    try:
        return await _http_discover(query, limit)
    except Exception:
        return []


class EnvatoSource:
    """Best-effort Envato search cards. No automatic asset acquisition."""

    provider_name = "envato"
    supported_source_classes = ("GENERIC_STOCK", "CLOSE_SEMANTIC_EDITORIAL")

    def __init__(self, *, discover: DiscoverFn | None = None, profile_dir: Path | None = None) -> None:
        self.discover = discover or _mcp_discover
        self._custom_discover = discover is not None
        self.profile_dir = Path(profile_dir) if profile_dir else None
        self._browser_lock = asyncio.Lock()
        self._playwright = None
        self._context = None
        self._browser_disabled_reason: str | None = None
        self.last_attempt: dict[str, Any] = {}

    async def _ensure_browser(self):
        if self._context is not None:
            return self._context
        if self._browser_disabled_reason:
            return None
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            browser = None
            failures = []
            for channel in ("msedge", "chrome", None):
                try:
                    kwargs = {"headless": True}
                    if channel:
                        kwargs["channel"] = channel
                    browser = await self._playwright.chromium.launch(**kwargs)
                    break
                except Exception as exc:
                    failures.append(f"{channel or 'chromium'}:{type(exc).__name__}")
            if browser is None:
                self._browser_disabled_reason = "public browser unavailable: " + ",".join(failures)
                return None
            self._context = await browser.new_context(viewport={"width": 1440, "height": 1400})
        except Exception as exc:
            self._browser_disabled_reason = type(exc).__name__
        return self._context

    async def _authenticated_discover(self, query: str, limit: int) -> list[dict[str, Any]]:
        async with self._browser_lock:
            context = await self._ensure_browser()
            if context is None:
                return []
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto(_search_url(query), wait_until="domcontentloaded", timeout=20_000)
            await page.wait_for_timeout(900)
            try:
                await page.evaluate("window.scrollTo(0, Math.min(document.body.scrollHeight, 1800))")
                await page.wait_for_timeout(500)
            except Exception:
                pass
            raw = await page.eval_on_selector_all(
                "a[href]",
                """els => els.map(a => {
                    const card = a.closest('article,li,[data-testid*="item"],[class*="card"],[class*="Card"]') || a.parentElement || a;
                    const img = a.querySelector('img') || card.querySelector('img');
                    return {
                        href: a.href || a.getAttribute('href') || '',
                        title: (img?.alt || a.innerText || card.innerText || a.textContent || '').trim(),
                        preview_url: (img?.currentSrc || img?.src || '')
                    };
                })""",
            )
            output = []
            seen = set()
            for row in list(raw or []):
                if not isinstance(row, dict):
                    continue
                source = _clean_item_url(str(row.get("href") or ""))
                preview = str(row.get("preview_url") or "").strip()
                title = " ".join(str(row.get("title") or "").split())
                if not source or source in seen or not title:
                    continue
                if not preview.startswith(("http://", "https://")):
                    continue
                seen.add(source)
                output.append({"source_page": source, "title": title, "preview_url": preview})
                if len(output) >= limit:
                    break
            return output

    async def search(
        self,
        query: str,
        *,
        orientation: str | None,
        min_duration: float,
        max_duration: float,
        limit: int,
    ) -> list[EnvatoRemoteCandidate]:
        clean = " ".join(str(query or "").split())
        if not clean or limit <= 0:
            return []
        try:
            variation_round = max(0, int(json.loads(os.environ.get("RAMBLA_SOCIAL_SEARCH_OPTIONS", "{}") or "{}").get("variation_round") or 0))
        except (TypeError, ValueError, json.JSONDecodeError):
            variation_round = 0
        discovery_limit = min(20, max(limit * 2, limit)) if not variation_round else 20
        try:
            raw = self.discover(clean, discovery_limit)
            rows = await raw if inspect.isawaitable(raw) else raw
        except Exception as exc:
            self.last_attempt = {
                "provider": self.provider_name,
                "query": clean,
                "hits": 0,
                "error": type(exc).__name__,
                "status": "failed", "engine": "envato_mcp", "parser": "mcp-items-v1",
                "http_status": exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None,
                "raw_items": None, "parsed_items": 0, "valid_items": 0, "cards_surfaced": 0,
            }
            return []
        if not isinstance(rows, list):
            rows = []
        if variation_round and rows:
            offset = ((variation_round - 1) * limit) % len(rows)
            rows = rows[offset:] + rows[:offset]
        output: list[EnvatoRemoteCandidate] = []
        seen: set[str] = set()
        duration_hint = max(float(min_duration), min(float(max_duration), 20.0))
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            source = _clean_item_url(str(row.get("source_page") or row.get("href") or ""))
            preview = str(row.get("preview_url") or "").strip()
            title = " ".join(str(row.get("title") or "").split())
            if not source or source in seen or not preview.startswith(("http://", "https://")) or not title:
                continue
            seen.add(source)
            provider_id = hashlib.sha256(source.encode("utf-8")).hexdigest()[:18]
            output.append(
                EnvatoRemoteCandidate(
                    provider="envato",
                    provider_id=provider_id,
                    query=clean,
                    source_page=source,
                    creator_name=None,
                    creator_page=None,
                    title=title,
                    description=title,
                    duration=duration_hint,
                    width=640,
                    height=360,
                    orientation="landscape",
                    preview_url=preview,
                    selected_rendition_url=source,
                    rendition_width=640,
                    rendition_height=360,
                    rights_state="subscription_license_required",
                    provider_rank=index,
                    source_duration=0.0,
                )
            )
            if len(output) >= limit:
                break
        self.last_attempt = {
            "provider": self.provider_name,
            "query": clean,
            "hits": len(output),
            "engine": "injected" if self._custom_discover else "envato_mcp",
            "request_query":clean if self._custom_discover else clean[:60],
            "http_status": None if self._custom_discover else 200,
            "parser": "mcp-items-v1", "status": "completed",
            "raw_items": len(rows), "parsed_items": len(rows), "valid_items": len(output), "cards_surfaced": 0,
            "browser_state": "ready" if self._context is not None else (self._browser_disabled_reason or "not_used"),
        }
        return output
