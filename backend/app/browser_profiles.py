"""Persistent RAMBLA-owned browser profiles for authenticated social discovery.

The module deliberately keeps credentials out of RAMBLA. Users authenticate in a
visible browser window; Playwright later reuses the dedicated profile directory.
"""
from __future__ import annotations

import asyncio
import inspect
import importlib.util
import json
import os
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess
from typing import Any, Awaitable, Callable
from urllib.parse import urljoin


SUPPORTED_SOCIAL_PROVIDERS = ("tiktok", "instagram", "envato")
DEFAULT_START_URLS = {
    "tiktok": "https://www.tiktok.com/",
    "instagram": "https://www.instagram.com/",
    "envato": "https://elements.envato.com/",
}

PlaywrightRunner = Callable[[Path, str | None, Callable[[Any, Any], Any]], Awaitable[Any]]
LoginLauncher = Callable[[str, Path, str], int]


class BrowserUnavailableError(RuntimeError):
    pass


def normal_chrome_profile() -> tuple[Path, str] | None:
    """Return the current user's real Chrome user-data root and last-used profile."""
    override = os.environ.get("RAMBLA_CHROME_USER_DATA_DIR", "").strip()
    if override:
        root = Path(override)
    elif os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        root = Path(os.environ["LOCALAPPDATA"]) / "Google" / "Chrome" / "User Data"
    else:
        root = Path.home() / ".config" / "google-chrome"
    if not root.is_dir():
        return None
    profile = os.environ.get("RAMBLA_CHROME_PROFILE", "").strip()
    if not profile:
        try:
            payload = json.loads((root / "Local State").read_text(encoding="utf-8"))
            profile = str(((payload.get("profile") or {}).get("last_used") or "")).strip()
        except Exception:
            profile = ""
    profile = profile or "Default"
    if not (root / profile).is_dir():
        profile = "Default" if (root / "Default").is_dir() else profile
    return root, profile


def _installed_chrome() -> str | None:
    for name in ("chrome", "chrome.exe", "google-chrome"):
        found = shutil.which(name)
        if found:
            return found
    if os.name == "nt":
        for root in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")):
            if not root:
                continue
            candidate = Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe"
            if candidate.is_file():
                return str(candidate)
    return None


class _DomAnchorParser(HTMLParser):
    _STRUCTURAL_TAGS = {"html", "body", "main", "section", "div", "article", "li", "a"}

    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.rows: list[dict[str, Any]] = []
        self.current: dict[str, Any] | None = None
        self._stack: list[tuple[str, dict[str, str | None]]] = []

    def _scope_flags(self, tag: str, values: dict[str, str | None]) -> tuple[bool, bool]:
        frames = [*self._stack, (tag, values)]
        tiktok = any(
            attrs.get("data-e2e") in {"search-card-video", "search-card-video-link", "search_video-item"}
            or "DivItemContainerForSearch" in str(attrs.get("class") or "")
            for _name, attrs in frames
        )
        instagram = any(name == "main" for name, _attrs in frames)
        return tiktok, instagram

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        clean_tag = tag.casefold()
        values = {key: value for key, value in attrs}
        if clean_tag == "a" and values.get("href"):
            tiktok_scope, instagram_scope = self._scope_flags(clean_tag, values)
            self.current = {
                "href": urljoin(self.base_url, str(values["href"])),
                "text_parts": [],
                "aria": str(values.get("aria-label") or ""),
                "img": "",
                "_tiktok_search_scope": tiktok_scope,
                "_instagram_search_scope": instagram_scope,
            }
        elif self.current is not None and clean_tag == "img":
            source = values.get("src") or values.get("data-src")
            if source:
                self.current["img"] = urljoin(self.base_url, str(source))
        if clean_tag in self._STRUCTURAL_TAGS:
            self._stack.append((clean_tag, values))

    def handle_data(self, data: str) -> None:
        if self.current is not None and data.strip():
            self.current["text_parts"].append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        clean_tag = tag.casefold()
        if clean_tag == "a" and self.current is not None:
            self.rows.append({
                "href": str(self.current["href"]),
                "text": " ".join(self.current["text_parts"]),
                "aria": str(self.current["aria"]),
                "img": str(self.current["img"]),
                "_tiktok_search_scope": bool(self.current["_tiktok_search_scope"]),
                "_instagram_search_scope": bool(self.current["_instagram_search_scope"]),
            })
            self.current = None
        if clean_tag in self._STRUCTURAL_TAGS:
            for index in range(len(self._stack) - 1, -1, -1):
                if self._stack[index][0] == clean_tag:
                    del self._stack[index:]
                    break


class _DumpDomPage:
    def __init__(self, html: str, url: str) -> None:
        parser = _DomAnchorParser(url)
        parser.feed(html or "")
        self._anchors = parser.rows
        self._html = html or ""
        self.url = url

    @staticmethod
    def _public_row(row: dict[str, Any]) -> dict[str, str]:
        return {
            "href": str(row.get("href") or ""),
            "text": str(row.get("text") or ""),
            "aria": str(row.get("aria") or ""),
            "img": str(row.get("img") or ""),
        }

    async def eval_on_selector_all(self, selector: str, _script: str) -> list[dict[str, str]]:
        if selector != "a[href]":
            return []
        return [self._public_row(row) for row in self._anchors]

    async def search_result_anchors(self, provider: str) -> list[dict[str, str]]:
        key = "_tiktok_search_scope" if provider == "tiktok" else "_instagram_search_scope"
        if provider not in {"tiktok", "instagram"}:
            raise ValueError("unsupported social provider")
        return [self._public_row(row) for row in self._anchors if row.get(key)]

    async def content(self) -> str:
        return self._html

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
        "--timeout=15000",
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
    except subprocess.TimeoutExpired as exc:
        # Chrome can finish the DOM dump while a child retains the pipe. A
        # complete document can still be inspected; a partial one cannot.
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        if "<html" in output.casefold() and "</html>" in output.casefold():
            completed = subprocess.CompletedProcess(command, 0, output, "")
        else:
            raise BrowserUnavailableError(
                "search_timeout: Chrome did not return a complete search page within 25 seconds; "
                "login state unknown. Close only the RAMBLA social login windows, then retry verification."
            ) from exc
    except Exception as exc:
        raise BrowserUnavailableError(f"Chromium DOM automation failed: {type(exc).__name__}") from exc
    if int(getattr(completed, "returncode", 1)) != 0:
        stderr = str(getattr(completed, "stderr", "") or "").casefold()
        if "processsingleton" in stderr or "lock file can not be created" in stderr:
            reason = "profile_in_use: close the RAMBLA social login browser window, then retry"
        elif "access is denied" in stderr or "accesso negato" in stderr:
            reason = "browser_access_denied: browser launch was denied by the current environment"
        else:
            reason = f"browser_exit_{completed.returncode}"
        raise BrowserUnavailableError(reason)
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
        browser = _installed_browser()
        if not browser:
            raise BrowserUnavailableError("No supported Edge/Chrome browser found")
        try:
            context = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir), executable_path=browser,
                headless=True, accept_downloads=True, chromium_sandbox=True,
            )
        except Exception as exc:
            # Use the same executable as OPEN. Never switch browsers against
            # one profile or replace a failed dynamic search with a DOM dump.
            detail = str(exc)
            import logging
            logging.getLogger(__name__).error("Social browser launch failed: %s", detail)
            lowered = detail.casefold()
            if any(marker in lowered for marker in ("processsingleton", "profile already in use", "user data directory is already in use")):
                reason = "profile_in_use: close the RAMBLA login window before verification"
            elif "access is denied" in lowered or "accesso negato" in lowered:
                reason = "browser_access_denied: browser launch or IPC was denied"
            else:
                reason = "browser_launch_failed: " + " ".join(detail.split())[:280]
            raise BrowserUnavailableError(reason) from exc
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
    for name in ("msedge", "msedge.exe", "chrome", "chrome.exe", "google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    if os.name == "nt":
        roots = [
            Path(root) for root in (
                os.environ.get("PROGRAMFILES"),
                os.environ.get("PROGRAMFILES(X86)"),
                os.environ.get("LOCALAPPDATA"),
            ) if root
        ]
        # Keep the browser preference global.  Interleaving candidates per
        # installation root could return Chrome from Program Files before the
        # preferred Edge installation in Program Files (x86).
        candidates = [root / "Microsoft" / "Edge" / "Application" / "msedge.exe" for root in roots]
        candidates += [root / "Google" / "Chrome" / "Application" / "chrome.exe" for root in roots]
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
    return None


def open_url_in_normal_chrome(start_url: str) -> int:
    """Open a new window in the user's active Chrome profile.

    Omitting ``--user-data-dir`` is intentional: Chrome routes the request to
    its existing ProcessSingleton, while ``--profile-directory`` selects the
    profile that already owns the user's provider sessions.
    """
    browser = _installed_chrome()
    if not browser:
        raise BrowserUnavailableError("Google Chrome not found")
    resolved = normal_chrome_profile()
    profile = resolved[1] if resolved is not None else "Default"
    command = [browser, f"--profile-directory={profile}", "--new-window", start_url]
    kwargs: dict[str, Any] = {"stdin": subprocess.DEVNULL}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        kwargs["start_new_session"] = True
    process = subprocess.Popen(command, **kwargs)
    try:
        code = process.wait(timeout=6)
    except subprocess.TimeoutExpired:
        code = None
    if code not in {None, 0}:
        raise BrowserUnavailableError(f"Google Chrome exited with code {code}")
    return int(process.pid)


def _default_login_launcher(provider: str, profile_dir: Path, start_url: str) -> int:
    """Open every external provider in the user's current Chrome session."""
    return open_url_in_normal_chrome(start_url)


class BrowserProfileManager:
    def __init__(
        self,
        root: Path,
        *,
        playwright_runner: PlaywrightRunner | None = None,
        login_launcher: LoginLauncher | None = None,
        owns_live_session: bool = False,
    ) -> None:
        self.root = Path(root)
        self.owns_live_session = owns_live_session
        self.connection_ready = {}
        from .live_social_sessions import LiveSocialSessions
        self._runner = playwright_runner or LiveSocialSessions()
        self._login_launcher = login_launcher or _default_login_launcher
        self._locks = {provider: asyncio.Lock() for provider in SUPPORTED_SOCIAL_PROVIDERS}

    async def open_login_async(self, provider: str) -> dict[str, Any]:
        focus = getattr(self._runner, "focus_existing", None)
        if focus and await focus(self.profile_dir(provider)):
            return {"provider": provider, "status": "focused", "session": "visible_persistent"}
        connected = getattr(self._runner, "is_connected", lambda _p: False)(self.profile_dir(provider))
        if connected:
            async def show(page, _context):
                await page.bring_to_front()
                return {"provider": provider, "status": "focused", "session": "visible_persistent"}
            return await self.run_in_profile(provider, show, start_url=None)
        return await asyncio.to_thread(self.open_login, provider)

    async def close(self):
        closer = getattr(self._runner, "close", None)
        if closer:
            await closer()

    def profile_dir(self, provider: str) -> Path:
        clean = str(provider or "").casefold().strip()
        if clean not in SUPPORTED_SOCIAL_PROVIDERS:
            raise ValueError("unsupported social provider")
        if clean == "envato":
            resolved = normal_chrome_profile()
            if resolved is not None:
                return resolved[0]
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
        result = {"provider": clean, "status": "started", "pid": int(pid)}
        if self._login_launcher is _default_login_launcher:
            result["session"] = "normal_chrome"
        return result

    async def check_search(self, provider: str) -> dict[str, Any]:
        """Read the open page only: no test query, navigation, or new browser."""
        from .social_page_evidence import inspect_search_html, challenge_required
        from urllib.parse import urlparse
        if provider not in {'tiktok','instagram'}:raise ValueError('unsupported social provider')
        if not getattr(self._runner,'is_connected',lambda p:False)(self.profile_dir(provider)):
            self.connection_ready[provider]=False
            return {'provider':provider,'ready':False,'login_state':'unknown','browser_state':'browser_closed','detail':'Open the RAMBLA browser and sign in; no test search was performed.'}
        async def inspect(page,context):
            html=await page.content()
            evidence=inspect_search_html(html)
            parsed=urlparse(str(page.url));host=(parsed.hostname or '').lower()
            valid=host==provider+'.com' or host.endswith('.'+provider+'.com')
            challenge=challenge_required(html)
            login=evidence.login_required or parsed.path.startswith(('/login','/accounts/login'))
            grid=valid and parsed.path.startswith('/search') and ('search_video-item' in html or 'search-card-video' in html)
            confirmed=valid and not challenge and not login and (evidence.signed_in or grid or self.connection_ready.get(provider,False))
            ready=valid and not challenge and not login and bool(evidence.visible_text.strip())
            ready=bool(ready or confirmed)
            self.connection_ready[provider]=bool(confirmed)
            return {'provider':provider,'ready':bool(ready),'login_state':'required' if login else 'verified' if evidence.signed_in else 'unknown',
                    'browser_state':'challenge_required' if challenge else 'login_required' if login else 'session_ready' if confirmed else 'session_unconfirmed' if ready else 'session_unknown',
                    'detail':'TikTok/Instagram verification required: resolve it manually in the open window. No automatic retry.' if challenge else 'Connected session reused; no test search performed.' if confirmed else 'Browser open; session not confirmed. You can start the real search. No test search performed.' if ready else 'Open the provider page and complete any login request.'}
        try:return await self.run_in_profile(provider,inspect,start_url=None)
        except Exception as exc:
            self.connection_ready[provider]=False
            return {'provider':provider,'ready':False,'login_state':'unknown','detail':str(exc)[:400],'error':type(exc).__name__}

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
                "profile_ready": (
                    bool(normal_chrome_profile())
                    if provider == "envato"
                    else self.profile_dir(provider).is_dir()
                ),
                "search_ready": search_ready,
                "search_backend": search_backend,
                "connection_ready": bool(self.connection_ready.get(provider)) and bool(
                    getattr(self._runner, "is_connected", lambda _p: False)(self.profile_dir(provider))
                ),
            }
            for provider in SUPPORTED_SOCIAL_PROVIDERS
        }
