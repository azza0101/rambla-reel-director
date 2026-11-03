"""Regression tests for local credentials and desktop UX surfaces."""
import os
import pytest


def test_provider_settings_save_update_delete_without_returning_secret(tmp_path, monkeypatch):
    from backend.app import desktop_controls as controls
    target=tmp_path / ".env.local"
    monkeypatch.setattr(controls, "_env_path", lambda: target)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    controls._save("groq", "gsk_test_first_value")
    assert os.environ["GROQ_API_KEY"]=="gsk_test_first_value"
    controls._save("groq", "gsk_test_second_value")
    text=target.read_text(encoding="utf-8")
    assert text.count("GROQ_API_KEY=")==1
    assert "gsk_test_first_value" not in text
    assert "gsk_test_second_value" in text
    controls._save("groq", None)
    assert "GROQ_API_KEY" not in os.environ
    assert "GROQ_API_KEY" not in target.read_text(encoding="utf-8")


def test_unknown_provider_never_reaches_filesystem(tmp_path, monkeypatch):
    from backend.app import desktop_controls as controls
    monkeypatch.setattr(controls, "_env_path", lambda: tmp_path / ".env.local")
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        controls._save("malicious", "value")
    assert exc.value.status_code==404
    assert not list(tmp_path.iterdir())


def test_desktop_controls_ui_exposes_stop_and_settings_without_echoing_keys():
    from backend.app.desktop_controls_ui import PANEL, JS
    assert 'id="rmblStopAnalysis"' in PANEL
    assert 'id="rmblSettings"' in PANEL
    assert "desktop-settings/" in JS
    assert "/v1/debug/runs/" in JS
    assert ".value=''" in JS
    assert "CPU " in JS and "RAM " in JS


def test_clean_director_exception_contains_exact_field_path():
    from backend.app.api_first_director import _clean_text
    with pytest.raises(ValueError, match="field.path: empty text field"):
        _clean_text("  ", path="field.path")
