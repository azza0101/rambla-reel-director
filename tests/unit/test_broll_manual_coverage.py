"""Regression: generic/place manual queries are real server searches and do not scroll."""
from backend.app.timeline_export_ui import PANEL, JS
from backend.app.curation_ui_v2 import render_curation_page_v2
import inspect
from backend.app import curation_server


def test_custom_search_controls():
    assert 'id="customSearchV138"' in PANEL
    assert 'id="customQueryV138"' in PANEL
    assert "params.set('manual_query',manualQuery)" in JS
    assert "loadGenericCoverageV33(true,'custom',query)" in JS


def test_research_run_never_auto_scrolls_to_workflow_header():
    html = render_curation_page_v2("scroll-v122")
    assert "else if(['videos','social','images'].includes(kind))openOnlyWorkflowStepV42(7,false)" in html
    assert 'customSearchV138' in html


def test_server_exposes_manual_query_and_preserves_prior_assets():
    source = inspect.getsource(curation_server.create_app)
    assert 'manual_query: str = ""' in source
    assert 'if manual_query:' in source
    assert 'query_groups = [(manual_query if scope == "places" else "", [manual_query])]' in source
    assert 'merge_unique([prior,items]' in source
    assert 'and not manual_query.strip()' in source
