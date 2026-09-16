def test_management_ui_exposes_project_library_clean_media_and_per_beat_research():
    from backend.app.curation_ui_v2 import render_curation_page_v2

    html = render_curation_page_v2("management-test")
    for text in (
        "PROJECTS", "CLEAN MEDIA", "NEW SEARCH", "ADD RESULTS",
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
