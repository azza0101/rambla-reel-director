from pathlib import Path

from fastapi.testclient import TestClient


def test_management_ui_exposes_project_library_clean_media_and_per_beat_research():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("management-test")
    for text in (
        "PROJECTS", "CLEAN MEDIA", "NEW SEARCH", "ADD TIKTOK + IG",
        "Project Library", "Disk usage", "RENAME", "DELETE",
    ):
        assert text in html
    assert "api('/projects')" in html
    assert "method:'PATCH'" in html
    assert "method:'DELETE'" in html
    assert "/media/clean" in html
    assert "/research`" in html or "/research" in html
    assert "researchBeatV2('replace')" in html
    assert "researchBeatV2('append',['tiktok','instagram'])" in html
    assert "startStage('analyze')" not in html[html.index("async function researchBeatV2"):html.index("function installManagementV2")]


def test_management_ui_project_delete_and_clean_have_confirmations():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("management-test")
    assert "confirm(" in html
    assert "Transcript and editorial plan stay safe" in html
    assert "permanently delete" in html


def test_management_ui_keeps_initial_shelves_compact_but_supports_show_more():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("management-test")
    assert "SHOW MORE" in html
    assert "expandedShelvesV2" in html


def test_product_server_serves_management_curation_page(tmp_path):
    from backend.app.curation_server import create_app

    root = tmp_path / "projects"
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    client = TestClient(create_app(
        project_root=root,
        allowed_media_roots=[allowed],
        probe_runner=lambda _: {"duration": 1, "fps": 25, "width": 1080, "height": 1920, "has_audio": False},
    ))
    response = client.get("/curation")
    assert response.status_code == 200
    assert "PROJECTS" in response.text
    assert "CLEAN MEDIA" in response.text
    assert "NEW SEARCH" in response.text
    assert "ADD TIKTOK + IG" in response.text


def test_acceptance_launcher_starts_product_server():
    launcher = Path("tools/start_curation_acceptance.ps1").read_text(encoding="utf-8")
    assert "backend.app.curation_server:app" in launcher
    assert "RAMBLA_ENABLE_VERTICAL_SOCIAL = '1'" in launcher


def test_product_ui_has_global_social_only_search_next_to_broll():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("social-global")
    assert 'id="findVideos"' in html
    assert 'id="findSocial"' in html
    assert html.index('id="findVideos"') < html.index('id="findSocial"') < html.index('id="findImages"')
    assert "FIND SOCIAL" in html
    assert "startStage('source/social')" in html


def test_management_ui_keeps_existing_layout_and_adds_api_director_controls():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("api-director")
    assert 'id="analyze"' in html
    assert 'id="findVideos"' in html
    assert 'id="findImages"' in html
    assert 'id="directorProviderV5"' in html
    assert 'id="generateDirectorV5"' in html
    assert "MANUAL / IMPORT" in html
    assert "AUTO" in html
    assert "GEMINI API" in html
    assert "GROQ API" in html
    assert "GENERATE PLAN" in html
    assert "transcript only" in html
    assert "api('/ai/status')" in html
    assert "/director" in html


def test_product_server_ai_status_never_exposes_api_key(monkeypatch, tmp_path):
    from backend.app.curation_server import create_app

    monkeypatch.setenv("GEMINI_API_KEY", "test-key-do-not-expose")
    monkeypatch.setenv("RAMBLA_DIRECTOR_MODEL", "gemini-3.8-flash")
    client = TestClient(create_app(
        project_root=tmp_path / "projects",
        allowed_media_roots=[tmp_path],
        probe_runner=lambda _: {"duration": 1, "fps": 25, "width": 1080, "height": 1920, "has_audio": False},
    ))

    response = client.get("/api/curation/ai/status")
    assert response.status_code == 200
    body = response.json()
    assert body["providers"]["gemini"]["configured"] is True
    assert body["providers"]["gemini"]["model"] == "gemini-3.8-flash"
    assert body["providers"]["gemini"]["source_video_sent_to_ai"] is False
    assert "groq" in body["providers"]
    assert "auto" in body["providers"]
    assert "test-key-do-not-expose" not in repr(body)


def test_api_first_product_keeps_curation_identity_without_v2_branding():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("v5-brand")
    assert "<h1>RAMBLA Curation</h1>" in html
    assert "RAMBLA Curation V2" not in html
    assert "CURATION V2" not in html
    assert "Choose the editorial engine" in html
    assert "GEMINI API" in html
    assert "transcript only" in html


def test_product_ui_clears_stale_director_running_state_on_terminal_failure():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("director-terminal")
    assert "window.ramblaRunTerminal" in html
    assert "stage_type==='director_api'" in html
    assert "Director ${String(r.status||'FAILED').toLowerCase()}" in html


def test_curation_ui_has_clean_console_copy_button():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("copy-console")
    assert 'id="copyConsole"' in html
    assert "COPY CONSOLE" in html
    assert "function cleanConsoleText()" in html
    assert "$('copyConsole').onclick=copyConsole" in html


def test_copy_console_javascript_keeps_newlines_escaped_in_rendered_html():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("copy-console-js")
    assert r"summary+'\n'+pre" in html
    assert r"rows.join('\n\n')" in html
    assert "summary+'\n'+pre" not in html


def test_product_ui_exposes_clickable_envato_search_shelf():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("envato")
    assert "ENVATO ELEMENTS" in html
    assert 'id="envatoVideosV2"' in html
    assert "a?.provider==='envato'?window.open(a.source_page" in html
    assert "download/licensing stays manual" in html
