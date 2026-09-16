from pathlib import Path

from fastapi.testclient import TestClient


def test_debug_server_direct_entrypoint_exposes_product_ui_and_management_routes(tmp_path):
    from backend.app.debug_server import create_app

    root = tmp_path / "projects"
    client = TestClient(create_app(
        project_root=root,
        allowed_media_roots=[tmp_path],
        probe_runner=lambda _: {"duration": 1, "fps": 25, "width": 1080, "height": 1920, "has_audio": False},
    ))

    html = client.get("/curation").text
    for marker in ("PROJECTS", "CLEAN MEDIA", "NEW SEARCH", "ADD RESULTS", "Project Library"):
        assert marker in html

    routes = {(route.path, method) for route in client.app.routes for method in (getattr(route, "methods", set()) or set())}
    assert ("/api/curation/projects", "GET") in routes
    assert ("/api/curation/projects/{project_id}", "PATCH") in routes
    assert ("/api/curation/projects/{project_id}", "DELETE") in routes
    assert ("/api/curation/projects/{project_id}/media/clean", "POST") in routes
    assert ("/api/curation/projects/{project_id}/beats/{beat_id}/research", "POST") in routes
