import asyncio
from pathlib import Path

import pytest


def test_profile_dirs_are_provider_scoped_and_reject_unknown(tmp_path):
    from backend.app.browser_profiles import BrowserProfileManager

    manager = BrowserProfileManager(tmp_path)
    assert manager.profile_dir("tiktok") == tmp_path / "tiktok"
    assert manager.profile_dir("instagram") == tmp_path / "instagram"
    with pytest.raises(ValueError, match="unsupported social provider"):
        manager.profile_dir("facebook")


def test_run_in_profile_serializes_same_provider_and_passes_callback(tmp_path):
    from backend.app.browser_profiles import BrowserProfileManager

    active = 0
    maximum = 0
    seen = []

    async def fake_runner(profile_dir, start_url, callback):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        try:
            await asyncio.sleep(0.01)
            return await callback("PAGE", "CONTEXT")
        finally:
            active -= 1

    manager = BrowserProfileManager(tmp_path, playwright_runner=fake_runner)

    async def callback(page, context):
        seen.append((page, context))
        return "ok"

    async def exercise():
        return await asyncio.gather(
            manager.run_in_profile("tiktok", callback, start_url="https://www.tiktok.com/"),
            manager.run_in_profile("tiktok", callback, start_url="https://www.tiktok.com/"),
        )

    assert asyncio.run(exercise()) == ["ok", "ok"]
    assert maximum == 1
    assert seen == [("PAGE", "CONTEXT"), ("PAGE", "CONTEXT")]


def test_open_login_uses_dedicated_profile_without_credentials(tmp_path):
    from backend.app.browser_profiles import BrowserProfileManager

    calls = []

    def fake_login_launcher(provider, profile_dir, start_url):
        calls.append((provider, profile_dir, start_url))
        return 321

    manager = BrowserProfileManager(tmp_path, login_launcher=fake_login_launcher)
    result = manager.open_login("tiktok")

    assert result == {"provider": "tiktok", "status": "started", "pid": 321}
    assert calls == [("tiktok", tmp_path / "tiktok", "https://www.tiktok.com/")]
    serialized = repr(result).casefold()
    assert "password" not in serialized
    assert "cookie" not in serialized
    assert "token" not in serialized


def test_default_login_opens_real_browser_profile_without_playwright(monkeypatch, tmp_path):
    import backend.app.browser_profiles as profiles

    launched = []

    class FakeProcess:
        pid = 987

    def fake_which(name):
        return r"C:\Program Files\Microsoft\Edge\Application\msedge.exe" if name in {"msedge", "msedge.exe"} else None

    def fake_popen(command, **kwargs):
        launched.append((command, kwargs))
        return FakeProcess()

    monkeypatch.setattr(profiles.shutil, "which", fake_which)
    monkeypatch.setattr(profiles.subprocess, "Popen", fake_popen)

    pid = profiles._default_login_launcher("tiktok", tmp_path / "tiktok", "https://www.tiktok.com/")

    assert pid == 987
    command = launched[0][0]
    assert command[0].lower().endswith("msedge.exe")
    assert f"--user-data-dir={tmp_path / 'tiktok'}" in command
    assert "https://www.tiktok.com/" in command
    joined = " ".join(command).casefold()
    assert "playwright" not in joined
    assert "social_browser_login" not in joined
    assert "password" not in joined


def test_status_exposes_readiness_not_profile_path_or_secrets(tmp_path):
    from backend.app.browser_profiles import BrowserProfileManager

    (tmp_path / "tiktok").mkdir(parents=True)
    manager = BrowserProfileManager(tmp_path)
    status = manager.status()

    assert status["tiktok"]["profile_ready"] is True
    assert status["instagram"]["profile_ready"] is False
    assert "profile_dir" not in status["tiktok"]
    assert "cookies" not in repr(status).casefold()


def test_chromium_dom_runner_reuses_profile_without_playwright(monkeypatch, tmp_path):
    import asyncio
    import backend.app.browser_profiles as profiles

    calls = []

    class Result:
        returncode = 0
        stdout = '<html><body><a href="/@wildlife/video/777">elephant clip</a></body></html>'
        stderr = ''

    monkeypatch.setattr(profiles, "_installed_browser", lambda: r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")
    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return Result()
    monkeypatch.setattr(profiles.subprocess, "run", fake_run)

    async def collect(page, _context):
        return await page.eval_on_selector_all("a[href]", "ignored")

    rows = asyncio.run(profiles._default_chromium_dom_runner(
        tmp_path / "tiktok",
        "https://www.tiktok.com/search/video?q=elephants",
        collect,
    ))
    assert rows[0]["href"] == "https://www.tiktok.com/@wildlife/video/777"
    command = calls[0][0]
    assert "--headless=new" in command
    assert "--dump-dom" in command
    assert any(part.startswith("--user-data-dir=") for part in command)


def test_status_reports_usable_social_search_backend_without_exposing_profile_path(monkeypatch, tmp_path):
    import backend.app.browser_profiles as profiles

    monkeypatch.setattr(profiles.importlib.util, "find_spec", lambda name: None if name == "playwright" else object())
    monkeypatch.setattr(profiles, "_installed_browser", lambda: r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")
    (tmp_path / "tiktok").mkdir(parents=True)
    status = profiles.BrowserProfileManager(tmp_path).status()

    assert status["tiktok"]["profile_ready"] is True
    assert status["tiktok"]["search_ready"] is True
    assert status["tiktok"]["search_backend"] == "chromium_dom"
    assert "profile_dir" not in repr(status).casefold()
