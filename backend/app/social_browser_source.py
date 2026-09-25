"""Authenticated browser-backed TikTok and Instagram Reel discovery."""
from __future__ import annotations

from typing import Any
import os
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
        '[data-e2e="search_video-item"] a[href*="/video/"], '
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
            '[data-e2e="search_video-item"], [data-e2e="search-card-video"], div[class*="DivItemContainerForSearch"], article'
          ) || a;
          const image = card.querySelector('img') || a.querySelector('img');
          const video = card.querySelector('video');
          return {
            href: a.href || '',
            text: ((image && image.alt) || card.innerText || a.innerText || a.textContent || '').trim(),
            aria: a.getAttribute('aria-label') || (image && image.alt) || '',
            img: (image && (image.currentSrc || image.src || image.getAttribute('data-src'))) || (video && video.poster) || ''
          };
        })""",
    )


async def hydrate_search_thumbnails(page: Any, provider: str, limit: int) -> None:
    """Bring lazy result covers into view before taking the extraction snapshot."""
    if not callable(getattr(page, 'locator', None)):
        return
    cards = page.locator(SOCIAL_RESULT_SELECTORS[provider])
    for index in range(min(await cards.count(), limit, 12)):
        card = cards.nth(index)
        try:
            ready = await card.evaluate("""a => {
                const image=a.querySelector('img'),video=a.querySelector('video');
                return !!((image && (image.currentSrc || image.getAttribute('src'))) || (video && video.poster));
            }""")
            if not ready:
                await card.scroll_into_view_if_needed(timeout=2000)
                # TikTok mounts the cover after intersection with the viewport.
                await page.wait_for_timeout(350)
        except Exception:
            # A removed/virtualized card is not a provider failure. Its source
            # link remains useful, but must never be presented as a video clip.
            continue


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
        self._browser_disabled_reason: str | None = None
        self._browser_disabled_detail: str | None = None

    async def _browser_search(self, query: str, limit: int) -> dict[str, Any]:
        endpoint = os.environ.get("RAMBLA_SOCIAL_SESSION_URL", "")
        if endpoint and not getattr(self.profile_manager, "owns_live_session", False):
            # Sourcing workers share the UI server's page; never launch a second
            # process against its locked profile and never copy session cookies.
            import httpx
            parsed_endpoint = urlparse(endpoint)
            if parsed_endpoint.scheme != "http" or parsed_endpoint.hostname != "127.0.0.1":
                raise RuntimeError("Invalid local social session endpoint")
            async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
                response = await client.post(
                    endpoint.rstrip('/') + f"/api/curation/social/{self.provider_name}/session-search",
                    headers={"X-Rambla-Session": os.environ.get("RAMBLA_SOCIAL_SESSION_TOKEN", "")},
                    json={"query": query, "limit": max(1, min(limit, 30))},
                )
                if response.is_error:
                    raise RuntimeError("social_session_failed: " + str(response.json().get("detail", response.status_code))[:400])
                return response.json()
        url = SOCIAL_SEARCH_URLS[self.provider_name].format(query=quote_plus(query))

        async def collect(page: Any, _context: Any) -> dict[str, Any]:
            found: list[dict[str, Any]] = []
            seen: set[str] = set()
            current_url = str(getattr(page, "url", "") or "")
            parsed = urlparse(current_url)
            if parsed.path.startswith(("/login", "/accounts/login")):
                raise RuntimeError("login_required: sign in in the open RAMBLA window and keep it open, then verify again")
            if self.provider_name == "tiktok":
                if not (parsed.hostname or "").casefold().endswith("tiktok.com") or not parsed.path.startswith("/search/video"):
                    raise RuntimeError(f"TikTok search navigation left /search/video: {current_url[:220]}")
            elif self.provider_name == "instagram":
                if not (parsed.hostname or "").casefold().endswith("instagram.com"):
                    raise RuntimeError(f"Instagram search navigation left instagram.com: {current_url[:220]}")

            content = getattr(page, "content", None)
            html = (await content()).casefold() if callable(content) else ""
            from .social_page_evidence import inspect_search_html, challenge_required
            evidence = inspect_search_html(html)
            if evidence.login_required or "/accounts/login" in parsed.path:
                raise RuntimeError("login_required: sign in in the RAMBLA provider window and keep it open, then retry")
            if challenge_required(html):
                raise RuntimeError("challenge_required: complete verification in the RAMBLA provider login window")
            if callable(content) and not html.strip():
                raise RuntimeError("empty_browser_document: browser did not render the search page")
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
                await hydrate_search_thumbnails(page, self.provider_name, limit)
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
                    await page.evaluate("""() => {
                      const grid = document.querySelector('#grid-main');
                      if (grid && grid.scrollHeight > grid.clientHeight)
                        grid.scrollBy(0, Math.max(grid.clientHeight * 1.8, 1400));
                      else window.scrollBy(0, Math.max(window.innerHeight * 1.8, 1400));
                    }""")
                    await page.wait_for_timeout(900)

            if callable(content):
                html=(await content()).casefold()
                evidence = inspect_search_html(html)
            current_url = str(getattr(page, "url", "") or "")
            if urlparse(current_url).path.startswith(("/login", "/accounts/login")) or evidence.login_required:
                raise RuntimeError("login_required: sign in in the RAMBLA window and keep it open")
            if challenge_required(html):
                raise RuntimeError("challenge_required: complete verification in the open RAMBLA window")
            explicit_zero = any(mark in evidence.visible_text for mark in ("no results found", "no videos found", "nessun risultato", "no results for"))
            state = "search_results" if found else ("zero_results" if explicit_zero else "search_results_unavailable")
            return {
                "rows": found[:limit],
                "diagnostics": {
                    "browser_state": state,
                    "login_state": "verified" if evidence.signed_in else "unknown",
                    "current_url": current_url[:300],
                    "page_title": await _page_title(page) or " ".join(evidence.title)[:180],
                    "visible_text_length": len(evidence.visible_text),
                    "zero_result_evidence": explicit_zero,
                    "all_video_link_count": all_video_links,
                    "search_result_link_count": len(found),
                    **({"search_wait_error": wait_error} if wait_error else {}),
                },
            }

        try:
            payload = await self.profile_manager.run_in_profile(self.provider_name, collect, start_url=url)
        except Exception:
            if hasattr(self.profile_manager, "connection_ready"):
                self.profile_manager.connection_ready[self.provider_name] = False
            raise
        if hasattr(self.profile_manager, "connection_ready"):
            self.profile_manager.connection_ready[self.provider_name] = bool(payload.get('rows')) or payload.get('diagnostics', {}).get('browser_state') == 'zero_results'
        return payload

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
        if self._browser_disabled_reason:
            browser_error = self._browser_disabled_reason
            browser_error_detail = self._browser_disabled_detail
            browser_diagnostics = {"browser_state": "disabled_after_failure"}
        else:
            try:
                payload = await self._browser_search(clean, limit)
                raw = list(payload.get("rows") or [])
                browser_diagnostics = dict(payload.get("diagnostics") or {})
            except Exception as exc:
                browser_error = type(exc).__name__
                browser_error_detail = " ".join(str(exc).split())[:240] or None
                if browser_error in {"BrowserUnavailableError", "ModuleNotFoundError", "ImportError"}:
                    self._browser_disabled_reason = browser_error
                    self._browser_disabled_detail = browser_error_detail

        if 'challenge_required' in str(browser_error_detail or ''):
            self._browser_disabled_reason=browser_error or 'challenge_required'
            self._browser_disabled_detail=browser_error_detail
            self.last_attempt={'provider':self.provider_name,'query':clean,'browser_state':'challenge_required',
                               'browser_error':'challenge_required','browser_error_detail':browser_error_detail,
                               'fallback_used':False,'authenticated_search_valid':False}
            return []

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
        fallback_attempt: dict[str, Any] = {}
        if self.fallback is not None:
            try:
                fallback_rows = await self.fallback.search(
                    clean, orientation=orientation, min_duration=min_duration,
                    max_duration=max_duration, limit=limit,
                )
                fallback_attempt = dict(getattr(self.fallback, "last_attempt", {}) or {})
            except Exception as exc:
                fallback_rows = []
                fallback_attempt = {"error": type(exc).__name__}
        self.last_attempt = {
            "provider": self.provider_name,
            "query": clean,
            "hits": len(fallback_rows),
            "browser": True,
            "fallback_used": bool(self.fallback is not None),
            "fallback_attempt": fallback_attempt,
            "authenticated_search_valid": False,
            **browser_diagnostics,
            **({"browser_error": browser_error} if browser_error else {}),
            **({"browser_error_detail": browser_error_detail} if browser_error_detail else {}),
        }
        browser_completed = browser_diagnostics.get("browser_state") == "zero_results"
        fallback_completed = "hits" in fallback_attempt and not fallback_attempt.get("error") and not fallback_attempt.get("errors")
        if not fallback_rows and not browser_completed and not fallback_completed:
            self.last_attempt["error"] = fallback_attempt.get("error") or browser_error or browser_diagnostics.get("browser_state") or "social_search_unavailable"
            self.last_attempt.pop("hits", None)
        return fallback_rows

    def drain_vertical_attempts(self) -> list[dict[str, Any]]:
        if not self.last_attempt:
            return []
        row = dict(self.last_attempt)
        self.last_attempt = {}
        return [row]
