"""Authenticated browser-backed TikTok and Instagram Reel discovery."""
from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus, urlparse

from .browser_profiles import BrowserProfileManager
from .vertical_social import VerticalRemoteCandidate


SOCIAL_SEARCH_URLS = {
    "tiktok": "https://www.tiktok.com/search/video?q={query}",
    "instagram": "https://www.instagram.com/explore/search/keyword/?q={query}",
}

# Scope authenticated extraction to the actual result surface.  Reading every
# a[href] on an authenticated TikTok page also sees account/sidebar links and
# can therefore mistake the user's own videos for search results.
SOCIAL_RESULT_SELECTORS = {
    "tiktok": (
        '[data-e2e="search-card-video-link"][href*="/video/"], '
        '[data-e2e="search-card-video"] a[href*="/video/"], '
        'div[class*="DivItemContainerForSearch"] a[href*="/video/"]'
    ),
    "instagram": 'main a[href*="/reel/"], main a[href*="/reels/"]',
}


def _canonical_social_url(provider: str, value: str) -> tuple[str, str, str | None] | None:
    try:
        parsed = urlparse(str(value or ""))
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"}:
        return None
    host = (parsed.hostname or "").casefold()
    parts = [part for part in (parsed.path or "").split("/") if part]
    if provider == "tiktok":
        if not host.endswith("tiktok.com") or len(parts) < 3 or not parts[0].startswith("@") or parts[1] != "video":
            return None
        provider_id = parts[2]
        creator = parts[0][1:] or None
        return f"https://www.tiktok.com/{parts[0]}/video/{provider_id}", provider_id, creator
    if provider == "instagram":
        if not host.endswith("instagram.com") or len(parts) < 2 or parts[0] not in {"reel", "reels"}:
            return None
        provider_id = parts[1]
        return f"https://www.instagram.com/reel/{provider_id}/", provider_id, None
    raise ValueError("unsupported social provider")


def extract_social_result_links(provider: str, anchors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if provider not in SOCIAL_SEARCH_URLS:
        raise ValueError("unsupported social provider")
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for anchor in anchors:
        canonical = _canonical_social_url(provider, str(anchor.get("href") or ""))
        if canonical is None:
            continue
        source_page, provider_id, creator = canonical
        if source_page in seen:
            continue
        seen.add(source_page)
        text = " ".join(str(anchor.get("text") or anchor.get("aria") or "").split())
        preview = str(anchor.get("img") or "").strip()
        output.append({
            "source_page": source_page,
            "provider_id": provider_id,
            "creator": creator,
            "text": text,
            "preview_url": preview if preview.startswith(("http://", "https://")) else "",
        })
    return output


async def _page_anchors(
    page: Any,
    provider: str | None = None,
    *,
    search_only: bool = False,
) -> list[dict[str, Any]]:
    if search_only:
        if provider not in SOCIAL_RESULT_SELECTORS:
            raise ValueError("unsupported social provider")
        # The --dump-dom fallback cannot execute selector JS, but exposes an
        # equivalent scoped extractor populated by its HTML parser.
        dump_extractor = getattr(page, "search_result_anchors", None)
        if callable(dump_extractor):
            rows = dump_extractor(provider)
            return await rows if hasattr(rows, "__await__") else rows
        selector = SOCIAL_RESULT_SELECTORS[provider]
    else:
        selector = "a[href]"
    return await page.eval_on_selector_all(
        selector,
        """els => els.map(a => {
          const card = a.closest(
            '[data-e2e="search-card-video"], div[class*="DivItemContainerForSearch"], article'
          ) || a;
          const image = card.querySelector('img') || a.querySelector('img');
          return {
            href: a.href || '',
            text: (card.innerText || a.innerText || a.textContent || '').trim(),
            aria: a.getAttribute('aria-label') || '',
            img: (image && (image.currentSrc || image.src)) || ''
          };
        })""",
    )


async def _page_title(page: Any) -> str:
    title = getattr(page, "title", None)
    if not callable(title):
        return ""
    try:
        value = title()
        value = await value if hasattr(value, "__await__") else value
    except Exception:
        return ""
    return " ".join(str(value or "").split())[:180]


class BrowserSocialSource:
    supported_source_classes = ("SOURCE_NATIVE_SOCIAL", "CLOSE_SEMANTIC_EDITORIAL")

    def __init__(self, provider: str, profile_manager: BrowserProfileManager, *, fallback: Any = None) -> None:
        if provider not in SOCIAL_SEARCH_URLS:
            raise ValueError("unsupported social provider")
        self.provider_name = provider
        self.profile_manager = profile_manager
        self.fallback = fallback
        self.last_attempt: dict[str, Any] = {}

    async def _browser_search(self, query: str, limit: int) -> dict[str, Any]:
        url = SOCIAL_SEARCH_URLS[self.provider_name].format(query=quote_plus(query))

        async def collect(page: Any, _context: Any) -> dict[str, Any]:
            found: list[dict[str, Any]] = []
            seen: set[str] = set()
            current_url = str(getattr(page, "url", "") or "")
            parsed = urlparse(current_url)
            if self.provider_name == "tiktok":
                if not (parsed.hostname or "").casefold().endswith("tiktok.com") or not parsed.path.startswith("/search/video"):
                    raise RuntimeError(f"TikTok search navigation left /search/video: {current_url[:220]}")
            elif self.provider_name == "instagram":
                if not (parsed.hostname or "").casefold().endswith("instagram.com"):
                    raise RuntimeError(f"Instagram search navigation left instagram.com: {current_url[:220]}")

            wait_error = ""
            waiter = getattr(page, "wait_for_selector", None)
            if callable(waiter):
                try:
                    await waiter(SOCIAL_RESULT_SELECTORS[self.provider_name], timeout=12_000)
                except Exception as exc:
                    # A real zero-result page and a delayed SPA both land here.
                    # Continue through the bounded scroll loop, but retain the
                    # state so diagnostics distinguish it from a valid grid.
                    wait_error = type(exc).__name__

            all_video_links = 0
            try:
                all_anchors = await _page_anchors(page)
                all_video_links = len(extract_social_result_links(self.provider_name, all_anchors))
            except Exception:
                pass

            for scroll_index in range(4):
                anchors = await _page_anchors(page, self.provider_name, search_only=True)
                for row in extract_social_result_links(self.provider_name, anchors):
                    if row["source_page"] not in seen:
                        seen.add(row["source_page"])
                        found.append(row)
                    if len(found) >= limit:
                        break
                if len(found) >= limit:
                    break
                if scroll_index < 3:
                    await page.evaluate("window.scrollBy(0, Math.max(window.innerHeight * 1.8, 1400))")
                    await page.wait_for_timeout(900)

            state = "search_results" if found else ("search_results_timeout" if wait_error else "zero_results")
            return {
                "rows": found[:limit],
                "diagnostics": {
                    "browser_state": state,
                    "current_url": current_url[:300],
                    "page_title": await _page_title(page),
                    "all_video_link_count": all_video_links,
                    "search_result_link_count": len(found),
                    **({"search_wait_error": wait_error} if wait_error else {}),
                },
            }

        return await self.profile_manager.run_in_profile(self.provider_name, collect, start_url=url)

    async def search(
        self,
        query: str,
        *,
        orientation: str | None,
        min_duration: float,
        max_duration: float,
        limit: int,
    ) -> list[VerticalRemoteCandidate]:
        clean = " ".join(str(query or "").split())
        if not clean or limit <= 0 or orientation not in {None, "portrait"}:
            return []
        browser_error: str | None = None
        browser_error_detail: str | None = None
        browser_diagnostics: dict[str, Any] = {}
        raw: list[dict[str, Any]] = []
        try:
            payload = await self._browser_search(clean, limit)
            raw = list(payload.get("rows") or [])
            browser_diagnostics = dict(payload.get("diagnostics") or {})
        except Exception as exc:
            browser_error = type(exc).__name__
            browser_error_detail = " ".join(str(exc).split())[:240] or None

        if raw:
            # Browser search cards do not expose a trustworthy source duration.
            # Keep a short localization hint so 3.5 s probes stay near the opening
            # instead of jumping to 20–50 s in a Reel that may only last 5–15 s.
            duration_hint = max(float(min_duration), min(float(max_duration), 12.0))
            rows = [
                VerticalRemoteCandidate(
                    provider=self.provider_name,
                    provider_id=row["provider_id"],
                    query=clean,
                    source_page=row["source_page"],
                    creator_name=row.get("creator"),
                    creator_page=(
                        f"https://www.tiktok.com/@{row['creator']}" if self.provider_name == "tiktok" and row.get("creator") else None
                    ),
                    title=row.get("text") or f"{self.provider_name} video {row['provider_id']}",
                    description=row.get("text") or f"{self.provider_name} video {row['provider_id']}",
                    duration=duration_hint,
                    width=1080,
                    height=1920,
                    orientation="portrait",
                    preview_url=row.get("preview_url") or "",
                    selected_rendition_url=row["source_page"],
                    rendition_width=1080,
                    rendition_height=1920,
                    rights_state="review_required",
                    provider_rank=index,
                    source_duration=0.0,
                    source_authenticity=.995,
                )
                for index, row in enumerate(raw[:limit])
            ]
            self.last_attempt = {
                "provider": self.provider_name,
                "query": clean,
                "hits": len(rows),
                "browser": True,
                "fallback_used": False,
                "authenticated_search_valid": True,
                **browser_diagnostics,
            }
            return rows

        fallback_rows: list[VerticalRemoteCandidate] = []
        if self.fallback is not None:
            try:
                fallback_rows = await self.fallback.search(
                    clean, orientation=orientation, min_duration=min_duration,
                    max_duration=max_duration, limit=limit,
                )
            except Exception:
                fallback_rows = []
        self.last_attempt = {
            "provider": self.provider_name,
            "query": clean,
            "hits": len(fallback_rows),
            "browser": True,
            "fallback_used": bool(self.fallback is not None),
            "authenticated_search_valid": False,
            **browser_diagnostics,
            **({"browser_error": browser_error} if browser_error else {}),
            **({"browser_error_detail": browser_error_detail} if browser_error_detail else {}),
        }
        return fallback_rows

    def drain_vertical_attempts(self) -> list[dict[str, Any]]:
        if not self.last_attempt:
            return []
        row = dict(self.last_attempt)
        self.last_attempt = {}
        return [row]
