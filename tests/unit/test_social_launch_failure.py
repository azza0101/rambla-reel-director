import asyncio
from types import SimpleNamespace

import pytest


def test_search_uses_login_browser_and_preserves_launch_failure(monkeypatch, tmp_path):
    from backend.app import browser_profiles as m
    import playwright.async_api

    calls = []

    async def launch(**kwargs):
        calls.append(kwargs)
        raise RuntimeError('ProcessSingleton: profile already in use')

    class Driver:
        async def __aenter__(self):
            return SimpleNamespace(chromium=SimpleNamespace(launch_persistent_context=launch))

        async def __aexit__(self, *args):
            pass

    async def forbidden_fallback(*args):
        pytest.fail('A failed live browser must not silently become a static search')

    monkeypatch.setattr(playwright.async_api, 'async_playwright', Driver)
    monkeypatch.setattr(m, '_installed_browser', lambda: 'installed-browser.exe')
    monkeypatch.setattr(m, '_default_chromium_dom_runner', forbidden_fallback)
    with pytest.raises(m.BrowserUnavailableError, match='profile_in_use'):
        asyncio.run(m._default_playwright_runner(tmp_path, 'https://www.tiktok.com/', lambda *_: None))
    assert len(calls) == 1
    assert calls[0]['executable_path'] == 'installed-browser.exe'
