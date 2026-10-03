from io import BytesIO
import json
from pathlib import Path
import zipfile

from fastapi.testclient import TestClient

from backend.app.curation_project import ProjectStore
from backend.app.curation_server import create_app


def package(name: str) -> bytes:
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(f"Edit/Titles/{name}/{name}.setting", "Tools = ordered() {}")
    return stream.getvalue()


def app_fixture(tmp_path):
    projects = tmp_path / "projects"
    bundled = tmp_path / "bundled"
    library = tmp_path / "library"
    installed = tmp_path / "installed"
    bundled.mkdir()
    (bundled / "KURA_paper_title_v9.drfx").write_bytes(package("KURA_paper_title_v9"))
    store = ProjectStore(projects, probe_runner=lambda _: {})
    project = store.create("Template test")
    app = create_app(
        project_root=projects,
        resolve_template_library_root=library,
        resolve_template_bundled_root=bundled,
        resolve_template_install_root=installed,
    )
    return TestClient(app), project, bundled, library, installed


def test_default_selection_is_bundled_kura_and_persists_custom_choice(tmp_path):
    client, project, _, _, _ = app_fixture(tmp_path)

    initial = client.get(f"/api/curation/projects/{project.project_id}/resolve-title-template")
    assert initial.status_code == 200
    assert initial.json()["template"]["resolve_name"] == "KURA_paper_title_v9"
    assert initial.json()["template"]["default"] is True

    uploaded = client.post(
        "/api/curation/resolve-title-templates",
        content=package("Custom_Title"),
        headers={"X-Rambla-Filename": "custom.drfx", "Content-Type": "application/octet-stream"},
    )
    assert uploaded.status_code == 200
    custom_id = uploaded.json()["template"]["template_id"]

    selected = client.put(
        f"/api/curation/projects/{project.project_id}/resolve-title-template",
        json={"template_id": custom_id},
    )
    assert selected.status_code == 200
    assert selected.json()["template"]["resolve_name"] == "Custom_Title"
    assert client.get(f"/api/curation/projects/{project.project_id}/resolve-title-template").json()["template"]["template_id"] == custom_id


def test_legacy_hash_only_selection_migrates_to_current_default(tmp_path):
    client, project, _, library, _ = app_fixture(tmp_path)
    selection_path = library.parent / "projects" / project.project_id / "resolve-title-template.json"
    selection_path.write_text(json.dumps({"template_id": "sha256-legacy-bundled-title"}), encoding="utf-8")

    response = client.get(f"/api/curation/projects/{project.project_id}/resolve-title-template")

    assert response.status_code == 200
    assert response.json()["template"]["resolve_name"] == "KURA_paper_title_v9"
    stored = json.loads(selection_path.read_text(encoding="utf-8"))
    assert stored["template_id"] == response.json()["template"]["template_id"]
    assert stored["resolve_name"] == "KURA_paper_title_v9"


def test_upload_rejects_invalid_package_and_unknown_selection(tmp_path):
    client, project, _, _, _ = app_fixture(tmp_path)

    bad = client.post(
        "/api/curation/resolve-title-templates",
        content=b"no",
        headers={"X-Rambla-Filename": "bad.drfx", "Content-Type": "application/octet-stream"},
    )
    assert bad.status_code == 422
    assert "valid DRFX" in bad.json()["detail"]

    missing = client.put(
        f"/api/curation/projects/{project.project_id}/resolve-title-template",
        json={"template_id": "sha256-missing"},
    )
    assert missing.status_code == 404


def test_install_reports_restart_then_installed_and_list_has_no_paths(tmp_path):
    client, _, _, _, _ = app_fixture(tmp_path)
    row = client.get("/api/curation/resolve-title-templates").json()["templates"][0]

    first = client.post(f"/api/curation/resolve-title-templates/{row['template_id']}/install")
    second = client.post(f"/api/curation/resolve-title-templates/{row['template_id']}/install")

    assert first.json()["status"] == "restart_required"
    assert second.json()["status"] == "installed"
    assert "source_path" not in json.dumps(client.get("/api/curation/resolve-title-templates").json())


def test_deleted_selected_package_is_invalid_without_kura_fallback(tmp_path):
    client, project, _, library, _ = app_fixture(tmp_path)
    uploaded = client.post(
        "/api/curation/resolve-title-templates",
        content=package("Custom_Title"),
        headers={"X-Rambla-Filename": "custom.drfx", "Content-Type": "application/octet-stream"},
    ).json()["template"]
    client.put(
        f"/api/curation/projects/{project.project_id}/resolve-title-template",
        json={"template_id": uploaded["template_id"]},
    )
    next(library.glob("*.drfx")).unlink()

    response = client.get(f"/api/curation/projects/{project.project_id}/resolve-title-template")

    assert response.status_code == 409
    assert "missing" in response.json()["detail"].casefold()
