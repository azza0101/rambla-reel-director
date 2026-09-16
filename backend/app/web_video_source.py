"""Google Videos discovery for news/recent footage with preview/link fallback."""
from __future__ import annotations

import hashlib
import inspect
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs, quote_plus, urlencode, urlparse, urlunparse


DiscoverFn = Callable[[str, int], Awaitable[list[dict[str, Any]]] | list[dict[str, Any]]]


@dataclass(frozen=True, slots=True)
class WebVideoRemoteCandidate:
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
    source_class: str = "CLOSE_SEMANTIC_EDITORIAL"
    source_authenticity: float | None = .80
    preview_rendition_url: str | None = None


def _clean_public_url(value: str) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.startswith("/url?"):
        raw = "https://www.google.com" + raw
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None
    host = (parsed.hostname or "").casefold()
    if parsed.scheme not in {"http", "https"} or not host:
        return None
    if host == "google.com" or host.endswith(".google.com"):
        if parsed.path != "/url":
            return None
        values = parse_qs(parsed.query)
        raw = (values.get("q") or values.get("url") or [""])[0]
        try:
            parsed = urlparse(raw)
        except ValueError:
            return None
        host = (parsed.hostname or "").casefold()
        if parsed.scheme not in {"http", "https"} or not host or host.endswith("google.com"):
            return None
    safe_pairs = []
    for key, values in parse_qs(parsed.query, keep_blank_values=False).items():
        if key.casefold().startswith("utm_") or key.casefold() in {"gclid", "fbclid", "ved"}:
            continue
        safe_pairs.extend((key, value) for value in values)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", urlencode(safe_pairs), ""))


def _orientation(source_page: str, width: int, height: int) -> str:
    path = urlparse(source_page).path.casefold()
    host = (urlparse(source_page).hostname or "").casefold()
    if "/shorts/" in path or (host.endswith("tiktok.com") and "/video/" in path) or (host.endswith("instagram.com") and ("/reel/" in path or "/reels/" in path)):
        return "portrait"
    if width > 0 and height > 0:
        if height > width:
            return "portrait"
        if width > height:
            return "landscape"
        return "square"
    return "unknown"


def extract_google_video_results(anchors: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in anchors:
        source_page = _clean_public_url(str(row.get("href") or ""))
        if not source_page or source_page in seen:
            continue
        preview = str(row.get("img") or "").strip()
        if not preview.startswith(("http://", "https://")):
            continue
        title = " ".join(str(row.get("text") or row.get("aria") or "").split())
        if not title:
            title = urlparse(source_page).hostname or "web video"
        width = int(row.get("img_width") or 0)
        height = int(row.get("img_height") or 0)
        seen.add(source_page)
        output.append({
            "source_page": source_page,
            "title": title,
            "preview_url": preview,
            "width": width,
            "height": height,
            "orientation": _orientation(source_page, width, height),
        })
        if len(output) >= limit:
            break
    return output


async def _default_google_discover(query: str, limit: int) -> list[dict[str, Any]]:
    from playwright.async_api import async_playwright

    url = f"https://www.google.com/search?tbm=vid&hl=en&q={quote_plus(query)}"
    async with async_playwright() as playwright:
        browser = None
        failures: list[str] = []
        for channel in ("msedge", "chrome", None):
            try:
                kwargs: dict[str, Any] = {"headless": True}
                if channel:
                    kwargs["channel"] = channel
                browser = await playwright.chromium.launch(**kwargs)
                break
            except Exception as exc:
                failures.append(f"{channel or 'chromium'}:{type(exc).__name__}")
        if browser is None:
            raise RuntimeError("Google video browser unavailable (" + ", ".join(failures) + ")")
        try:
            page = await browser.new_page(viewport={"width": 1440, "height": 1200})
            await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
            await page.wait_for_timeout(700)
            anchors = await page.eval_on_selector_all(
                "a[href]",
                """els => els.map(a => {
                  const img=a.querySelector('img');
                  return {href:a.href||'',text:(a.innerText||a.textContent||'').trim(),aria:a.getAttribute('aria-label')||'',img:img?(img.currentSrc||img.src||''):'',img_width:img?(img.naturalWidth||0):0,img_height:img?(img.naturalHeight||0):0};
                })""",
            )
            return extract_google_video_results(list(anchors or []), limit=limit)
        finally:
            await browser.close()


class WebVideoSource:
    """Google Videos-backed discovery. Downloadability is optional, discovery is not."""

    provider_name = "web_video"
    supported_source_classes = (
        "EXACT_ENTITY_EVENT", "SOURCE_NATIVE_SOCIAL", "ARCHIVAL_REPERTORY",
        "CULTURAL_REFERENCE", "CLOSE_SEMANTIC_EDITORIAL",
    )

    def __init__(self, *, discover: DiscoverFn | None = None) -> None:
        self.discover = discover or _default_google_discover
        self.last_attempt: dict[str, Any] = {}

    async def search(
        self,
        query: str,
        *,
        orientation: str | None,
        min_duration: float,
        max_duration: float,
        limit: int,
    ) -> list[WebVideoRemoteCandidate]:
        clean = " ".join(str(query or "").split())
        if not clean or limit <= 0:
            return []
        try:
            raw = self.discover(clean, max(limit * 2, limit))
            rows = await raw if inspect.isawaitable(raw) else raw
        except Exception as exc:
            self.last_attempt = {"provider": self.provider_name, "query": clean, "hits": 0, "error": type(exc).__name__}
            return []
        if not isinstance(rows, list):
            rows = []
        if rows and "source_page" not in rows[0]:
            rows = extract_google_video_results(rows, limit=max(limit * 2, limit))
        rows = sorted(
            (row for row in rows if isinstance(row, dict)),
            key=lambda row: (str(row.get("orientation")) != "portrait",),
        )
        duration_hint = max(float(min_duration), min(float(max_duration), 60.0))
        output: list[WebVideoRemoteCandidate] = []
        for index, row in enumerate(rows):
            source_page = _clean_public_url(str(row.get("source_page") or ""))
            preview = str(row.get("preview_url") or "").strip()
            if not source_page or not preview.startswith(("http://", "https://")):
                continue
            width = int(row.get("width") or 0)
            height = int(row.get("height") or 0)
            orient = str(row.get("orientation") or _orientation(source_page, width, height))
            provider_id = hashlib.sha256(source_page.encode("utf-8")).hexdigest()[:18]
            title = " ".join(str(row.get("title") or "web video").split())
            output.append(WebVideoRemoteCandidate(
                provider="web_video",
                provider_id=provider_id,
                query=clean,
                source_page=source_page,
                creator_name=None,
                creator_page=None,
                title=title,
                description=title,
                duration=duration_hint,
                width=width,
                height=height,
                orientation=orient,
                preview_url=preview,
                selected_rendition_url=source_page,
                rendition_width=width,
                rendition_height=height,
                rights_state="review_required",
                provider_rank=index,
                source_duration=0.0,
            ))
            if len(output) >= limit:
                break
        self.last_attempt = {"provider": self.provider_name, "query": clean, "hits": len(output), "engine": "google_videos"}
        return output
