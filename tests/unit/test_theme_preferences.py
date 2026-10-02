from fastapi.testclient import TestClient


def _client(tmp_path):
    from backend.app.curation_server import create_app

    return TestClient(create_app(
        project_root=tmp_path / "projects",
        allowed_media_roots=[tmp_path],
        probe_runner=lambda _: {
            "duration": 1,
            "fps": 25,
            "width": 1080,
            "height": 1920,
            "has_audio": False,
        },
    ))


def test_theme_preferences_round_trip_outside_projects(tmp_path):
    client = _client(tmp_path)
    initial = client.get("/api/curation/theme-preferences")
    assert initial.status_code == 200
    payload = initial.json()["theme"]
    assert payload["canvas"]["mode"] == "solid"
    assert set(payload["sections"]) == {str(step) for step in range(1, 8)}

    payload["canvas"] = {"mode": "gradient", "color_a": "#123456", "color_b": "#0a8899"}
    payload["sections"]["5"] = {"mode": "solid", "color_a": "#224466", "color_b": "#224466"}
    saved = client.put("/api/curation/theme-preferences", json=payload)

    assert saved.status_code == 200
    assert saved.json()["theme"] == payload
    assert (tmp_path / "theme-preferences.json").is_file()
    assert _client(tmp_path).get("/api/curation/theme-preferences").json()["theme"] == payload


def test_theme_preferences_reject_css_injection(tmp_path):
    client = _client(tmp_path)
    payload = client.get("/api/curation/theme-preferences").json()["theme"]
    payload["canvas"]["color_a"] = "red;display:none"
    response = client.put("/api/curation/theme-preferences", json=payload)
    assert response.status_code == 422


def test_theme_settings_ui_is_at_the_end_and_updates_live():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("theme-settings")
    assert "⚙ IMPOSTAZIONI GRAFICHE" in html
    assert "applyThemePreferencesV45" in html
    assert "renderThemeSettingsV45" in html
    assert "/theme-preferences" in html
    assert "SALVA IMPOSTAZIONI" in html
    assert "RIPRISTINA COLORI" in html
    assert html.index("7 · Export timeline") < html.index("⚙ IMPOSTAZIONI GRAFICHE")
