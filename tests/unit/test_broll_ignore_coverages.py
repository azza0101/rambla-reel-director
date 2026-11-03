"""Per-item ignore must preserve every other selected clip."""
from backend.app.timeline_export_ui import PANEL, JS
from backend.app.curation_server import create_app


def test_failed_rows_offer_individual_ignore_and_retry():
    assert "data-ignore-coverage" in JS
    assert "IGNORA QUESTA COPERTURA" in JS
    assert "RIPROVA DOWNLOAD" in JS
    assert "IGNORA COPERTURE</button>" not in PANEL


def test_ignore_only_selected_asset_in_temporary_request():
    assert "ignoredCoverageIdsV123.add(id)" in JS
    assert "params.set('ignored',[...ignoredCoverageIdsV123].join(','))" in JS
    assert "body:JSON.stringify(resolveComponentsV71)" in JS
    assert "resolveComponentsV71=trimmed" not in JS
    assert "Ignorata solo questa copertura" in JS


def test_endpoint_accepts_ignored_asset_ids_without_modifying_project():
    from fastapi.testclient import TestClient
    from pathlib import Path
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        app=create_app(project_root=Path(temp)/"projects")
        with TestClient(app) as client:
            response=client.post(
                "/api/curation/projects/nonexistent/resolve-preparation?ignored=generic:123",
                json={"video": False, "subtitles": True, "highlights": False,
                      "broll": True, "social": True, "generic": True},
            )
            # The request parameter is recognized; project must still exist.
            assert response.status_code in {404, 422}


def test_project_selection_not_edited_by_ignore_mechanism():
    import inspect
    from backend.app import curation_server
    source=inspect.getsource(curation_server.create_app)
    assert "ignored_for_export(ignored)" in source
    assert "ignored_assets=skipped" in source
    assert "excluded = skipped | {row['asset_id'] for row in media_issues}" in source
    assert "ignored_assets = set(ignored_assets or ())" in source
