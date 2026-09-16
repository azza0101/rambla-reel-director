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


def test_status_exposes_readiness_not_profile_path_or_secrets(tmp_path):
    from backend.app.browser_profiles import BrowserProfileManager

    (tmp_path / "tiktok").mkdir(parents=True)
    manager = BrowserProfileManager(tmp_path)
    status = manager.status()

    assert status["tiktok"]["profile_ready"] is True
    assert status["instagram"]["profile_ready"] is False
    assert "profile_dir" not in status["tiktok"]
    assert "cookies" not in repr(status).casefold()
