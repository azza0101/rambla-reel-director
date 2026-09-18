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
    assert "mode:'replace'" in html
    assert "mode:'append'" in html
    assert "['tiktok','instagram']" in html
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
