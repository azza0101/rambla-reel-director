"""Source searches must never jump the editor back to the B-roll section header."""
from backend.app.curation_ui_v2 import render_curation_page_v2


def test_search_completion_preserves_user_scroll_position():
    html=render_curation_page_v2("test-scroll-fix")
    assert "else if(['videos','social','images'].includes(kind))openOnlyWorkflowStepV42(7,false)" in html
    assert "if(kind==='director_api')openOnlyWorkflowStepV42(6)" in html


def test_manual_search_keeps_input_and_query_in_gallery():
    html=render_curation_page_v2("test-scroll-fix")
    assert "form.onsubmit=async e=>" in html
    assert "query_overrides:{'*':query}" in html
