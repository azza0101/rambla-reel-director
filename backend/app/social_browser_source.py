"""Authenticated browser-backed TikTok and Instagram Reel discovery."""
from __future__ import annotations

from dataclasses import replace
from typing import Any
from urllib.parse import quote_plus, urlparse

from .browser_profiles import BrowserProfileManager
from .vertical_social import VerticalRemoteCandidate


SOCIAL_SEARCH_URLS = {
    "tiktok": "https://www.tiktok.com/search/video?q={query}",
    "instagram": "https://www.instagram.com/explore/search/keyword/?q={query}",
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


async def _page_anchors(page: Any) -> list[dict[str, Any]]:
    return await page.eval_on_selector_all(
        "a[href]",
        """els => els.map(a => ({
          href: a.href || '',
          text: (a.innerText || a.textContent || '').trim(),
          aria: a.getAttribute('aria-label') || '',
          img: (a.querySelector('img') && (a.querySelector('img').currentSrc || a.querySelector('img').src)) || ''
        }))""",
    )


class BrowserSocialSource:
    supported_source_classes = ("SOURCE_NATIVE_SOCIAL", "CLOSE_SEMANTIC_EDITORIAL")

    def __init__(self, provider: str, profile_manager: BrowserProfileManager, *, fallback: Any = None) -> None:
        if provider not in SOCIAL_SEARCH_URLS:
            raise ValueError("unsupported social provider")
        self.provider_name = provider
        self.profile_manager = profile_manager
        self.fallback = fallback
        self.last_attempt: dict[str, Any] = {}

    async def _browser_search(self, query: str, limit: int) -> list[dict[str, Any]]:
        url = SOCIAL_SEARCH_URLS[self.provider_name].format(query=quote_plus(query))

        async def collect(page: Any, _context: Any) -> list[dict[str, Any]]:
            found: list[dict[str, Any]] = []
            seen: set[str] = set()
            for scroll_index in range(3):
                anchors = await _page_anchors(page)
                for row in extract_social_result_links(self.provider_name, anchors):
                    if row["source_page"] not in seen:
                        seen.add(row["source_page"])
                        found.append(row)
                    if len(found) >= limit:
                        return found
                if scroll_index < 2:
                    await page.evaluate("window.scrollBy(0, Math.max(window.innerHeight * 1.6, 1200))")
                    await page.wait_for_timeout(550)
            return found

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
        raw: list[dict[str, Any]] = []
        try:
            raw = await self._browser_search(clean, limit)
        except Exception as exc:
            browser_error = type(exc).__name__

        if raw:
            duration_hint = max(float(min_duration), min(float(max_duration), 60.0))
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
            **({"browser_error": browser_error} if browser_error else {}),
        }
        return fallback_rows

    def drain_vertical_attempts(self) -> list[dict[str, Any]]:
        if not self.last_attempt:
            return []
        row = dict(self.last_attempt)
        self.last_attempt = {}
        return [row]
