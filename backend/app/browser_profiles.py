"""Persistent RAMBLA-owned browser profiles for authenticated social discovery.

The module deliberately keeps credentials out of RAMBLA. Users authenticate in a
visible browser window; Playwright later reuses the dedicated profile directory.
"""
from __future__ import annotations

import asyncio
import inspect
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Awaitable, Callable


SUPPORTED_SOCIAL_PROVIDERS = ("tiktok", "instagram")
DEFAULT_START_URLS = {
    "tiktok": "https://www.tiktok.com/",
    "instagram": "https://www.instagram.com/",
}

PlaywrightRunner = Callable[[Path, str | None, Callable[[Any, Any], Any]], Awaitable[Any]]
LoginLauncher = Callable[[str, Path, str], int]


class BrowserUnavailableError(RuntimeError):
    pass


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
    from playwright.async_api import async_playwright

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
            raise BrowserUnavailableError("No supported Chromium browser available (" + ", ".join(failures) + ")")
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


def _default_login_launcher(provider: str, profile_dir: Path, start_url: str) -> int:
    profile_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "backend.app.social_browser_login",
        "--provider",
        provider,
        "--profile-dir",
        str(profile_dir),
        "--url",
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

    def status(self) -> dict[str, dict[str, bool]]:
        return {
            provider: {"profile_ready": self.profile_dir(provider).is_dir()}
            for provider in SUPPORTED_SOCIAL_PROVIDERS
        }
