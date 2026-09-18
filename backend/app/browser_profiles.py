"""Persistent RAMBLA-owned browser profiles for authenticated social discovery.

The module deliberately keeps credentials out of RAMBLA. Users authenticate in a
visible browser window; Playwright later reuses the dedicated profile directory.
"""
from __future__ import annotations

import asyncio
import inspect
import importlib.util
import os
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess
from typing import Any, Awaitable, Callable
from urllib.parse import urljoin


SUPPORTED_SOCIAL_PROVIDERS = ("tiktok", "instagram")
DEFAULT_START_URLS = {
    "tiktok": "https://www.tiktok.com/",
    "instagram": "https://www.instagram.com/",
}

PlaywrightRunner = Callable[[Path, str | None, Callable[[Any, Any], Any]], Awaitable[Any]]
LoginLauncher = Callable[[str, Path, str], int]


class BrowserUnavailableError(RuntimeError):
    pass


class _DomAnchorParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.rows: list[dict[str, str]] = []
        self.current: dict[str, Any] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value for key, value in attrs}
        if tag.casefold() == "a" and values.get("href"):
            self.current = {
                "href": urljoin(self.base_url, str(values["href"])),
                "text_parts": [],
                "aria": str(values.get("aria-label") or ""),
                "img": "",
            }
        elif self.current is not None and tag.casefold() == "img":
            source = values.get("src") or values.get("data-src")
            if source:
                self.current["img"] = urljoin(self.base_url, str(source))

    def handle_data(self, data: str) -> None:
        if self.current is not None and data.strip():
            self.current["text_parts"].append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "a" or self.current is None:
            return
        self.rows.append({
            "href": str(self.current["href"]),
            "text": " ".join(self.current["text_parts"]),
            "aria": str(self.current["aria"]),
            "img": str(self.current["img"]),
        })
        self.current = None


class _DumpDomPage:
    def __init__(self, html: str, url: str) -> None:
        parser = _DomAnchorParser(url)
        parser.feed(html or "")
        self._anchors = parser.rows
        self.url = url

    async def eval_on_selector_all(self, selector: str, _script: str) -> list[dict[str, str]]:
        if selector != "a[href]":
            return []
        return list(self._anchors)

    async def evaluate(self, _script: str) -> None:
        return None

    async def wait_for_timeout(self, _milliseconds: int) -> None:
        return None


async def _default_chromium_dom_runner(
    profile_dir: Path,
    start_url: str | None,
    callback: Callable[[Any, Any], Any],
) -> Any:
    """Fallback social automation using installed Edge/Chrome only.

    This is intentionally narrow: Chromium renders the authenticated search page
    with the RAMBLA-owned profile and dumps the resulting DOM. It needs neither
    Playwright nor pip, and never reads the user's normal browser profile.
    """
    if not start_url:
        raise BrowserUnavailableError("social search URL required")
    browser = _installed_browser()
    if not browser:
        raise BrowserUnavailableError("No supported Edge/Chrome browser found")
    profile_dir.mkdir(parents=True, exist_ok=True)
    command = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--disable-extensions",
        "--no-first-run",
        "--no-default-browser-check",
        f"--user-data-dir={profile_dir}",
        "--profile-directory=Default",
        "--virtual-time-budget=8000",
        "--dump-dom",
        start_url,
    ]
    kwargs: dict[str, Any] = {
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "timeout": 25,
        "check": False,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def run_dump():
        return subprocess.run(command, **kwargs)

    try:
        completed = await asyncio.to_thread(run_dump)
    except Exception as exc:
        raise BrowserUnavailableError("Chromium DOM automation failed") from exc
    if int(getattr(completed, "returncode", 1)) != 0:
        raise BrowserUnavailableError("Chromium DOM automation failed")
    page = _DumpDomPage(str(getattr(completed, "stdout", "") or ""), start_url)
    result = callback(page, None)
    if inspect.isawaitable(result):
        result = await result
    return result


async def _default_playwright_runner(
    profile_dir: Path,
    start_url: str | None,
    callback: Callable[[Any, Any], Any],
) -> Any:
    """Run one callback in the saved Edge/Chrome profile without opening UI.

    Login is a separate headed process. Retrieval reuses those cookies in a
    background persistent context so a reel search does not flash many browser
    windows while querying several beats.
    """
    try:
        from playwright.async_api import async_playwright
    except (ImportError, ModuleNotFoundError):
        return await _default_chromium_dom_runner(profile_dir, start_url, callback)

    profile_dir.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        context = None
        failures: list[str] = []
        for channel in ("msedge", "chrome", None):
            try:
                kwargs = {
                    "user_data_dir": str(profile_dir),
                    "headless": True,
                    "accept_downloads": True,
                }
                if channel:
                    kwargs["channel"] = channel
                context = await playwright.chromium.launch_persistent_context(**kwargs)
                break
            except Exception as exc:  # provider/browser specific, surfaced compactly
                failures.append(f"{channel or 'chromium'}:{type(exc).__name__}")
        if context is None:
            try:
                return await _default_chromium_dom_runner(profile_dir, start_url, callback)
            except BrowserUnavailableError as exc:
                raise BrowserUnavailableError("No supported Chromium browser available (" + ", ".join(failures) + ")") from exc
        try:
            page = context.pages[0] if context.pages else await context.new_page()
            if start_url:
                await page.goto(start_url, wait_until="domcontentloaded", timeout=20_000)
            result = callback(page, context)
            if inspect.isawaitable(result):
                result = await result
            return result
        finally:
            try:
                await context.close()
            except Exception:
                pass


def _installed_browser() -> str | None:
    """Return an installed Chromium browser without reading a user's main profile."""
    for name in ("msedge", "msedge.exe", "chrome", "chrome.exe", "google-chrome"):
        found = shutil.which(name)
        if found:
            return found
    if os.name == "nt":
        candidates = []
        for root in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")):
            if not root:
                continue
            candidates.extend((
                Path(root) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
                Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe",
            ))
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
    return None


def _default_login_launcher(provider: str, profile_dir: Path, start_url: str) -> int:
    """Open the login page in a RAMBLA-owned persistent browser profile.

    Login itself does not need Playwright. This keeps credentials in the real
    browser and lets the curation UI work even when the server venv has no pip.
    """
    del provider  # provider is already encoded by start_url/profile_dir
    profile_dir.mkdir(parents=True, exist_ok=True)
    browser = _installed_browser()
    if not browser:
        raise BrowserUnavailableError("No supported Edge/Chrome browser found")
    command = [
        browser,
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        start_url,
    ]
    kwargs: dict[str, Any] = {"stdin": subprocess.DEVNULL}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        kwargs["start_new_session"] = True
    process = subprocess.Popen(command, **kwargs)
    return int(process.pid)


class BrowserProfileManager:
    def __init__(
        self,
        root: Path,
        *,
        playwright_runner: PlaywrightRunner | None = None,
        login_launcher: LoginLauncher | None = None,
    ) -> None:
        self.root = Path(root)
        self._runner = playwright_runner or _default_playwright_runner
        self._login_launcher = login_launcher or _default_login_launcher
        self._locks = {provider: asyncio.Lock() for provider in SUPPORTED_SOCIAL_PROVIDERS}

    def profile_dir(self, provider: str) -> Path:
        clean = str(provider or "").casefold().strip()
        if clean not in SUPPORTED_SOCIAL_PROVIDERS:
            raise ValueError("unsupported social provider")
        return self.root / clean

    async def run_in_profile(
        self,
        provider: str,
        callback: Callable[[Any, Any], Any],
        *,
        start_url: str | None = None,
    ) -> Any:
        clean = str(provider or "").casefold().strip()
        directory = self.profile_dir(clean)
        directory.mkdir(parents=True, exist_ok=True)
        async with self._locks[clean]:
            return await self._runner(directory, start_url, callback)

    def open_login(self, provider: str, *, start_url: str | None = None) -> dict[str, Any]:
        clean = str(provider or "").casefold().strip()
        directory = self.profile_dir(clean)
        directory.mkdir(parents=True, exist_ok=True)
        url = start_url or DEFAULT_START_URLS[clean]
        pid = self._login_launcher(clean, directory, url)
        return {"provider": clean, "status": "started", "pid": int(pid)}

    def status(self) -> dict[str, dict[str, Any]]:
        if importlib.util.find_spec("playwright") is not None:
            search_backend = "playwright"
            search_ready = True
        elif _installed_browser():
            search_backend = "chromium_dom"
            search_ready = True
        else:
            search_backend = "unavailable"
            search_ready = False
        return {
            provider: {
                "profile_ready": self.profile_dir(provider).is_dir(),
                "search_ready": search_ready,
                "search_backend": search_backend,
            }
            for provider in SUPPORTED_SOCIAL_PROVIDERS
        }
