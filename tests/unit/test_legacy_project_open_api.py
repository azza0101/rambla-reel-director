import json
from pathlib import Path

from fastapi.testclient import TestClient


def test_get_existing_legacy_project_auto_writes_manifest_without_analyze(tmp_path):
    from backend.app.debug_server import create_app

    source = tmp_path / "allowed" / "source.mp4"
    source.parent.mkdir()
    source.write_bytes(b"video")

    def normalize(command):
        Path(command[-1]).write_bytes(b"wav")

    project_root = tmp_path / "projects"
    client = TestClient(create_app(
        project_root=project_root,
        allowed_media_roots=[source.parent],
        probe_runner=lambda _: {"duration": 3, "fps": 25, "width": 640, "height": 360, "has_audio": True},
        audio_probe_runner=lambda _: 3.0,
        audio_command_runner=normalize,
    ))
    project_id = client.post("/api/curation/projects", json={"name": "Legacy reel"}).json()["project_id"]
    assert client.post(f"/api/curation/projects/{project_id}/source/local", json={"path": str(source)}).status_code == 200

    manifest = project_root / project_id / "project.rambla.json"
    manifest.unlink()
    assert (project_root / project_id / "project.json").is_file()

    response = client.get(f"/api/curation/projects/{project_id}")
    assert response.status_code == 200
    assert response.json()["project_id"] == project_id
    assert response.json()["resolve_calls"] == 0
    assert manifest.is_file()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "rambla-project-1"
    assert payload["project_id"] == project_id


def test_current_project_manifest_remains_openable_after_auto_migration(tmp_path):
    from backend.app.curation_project import ProjectStore

    store = ProjectStore(
        tmp_path / "projects",
        probe_runner=lambda _: {"duration": 3, "fps": 25, "width": 640, "height": 360, "has_audio": False},
    )
    project = store.create("Current reel")
    manifest = store.manifest_path(project.project_id)
    opened = store.load_manifest(manifest)
    assert opened.project_id == project.project_id
