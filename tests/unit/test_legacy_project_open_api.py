import json
from pathlib import Path

from fastapi.testclient import TestClient


def test_open_project_file_api_migrates_legacy_project_json_without_analyze(tmp_path):
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

    legacy_path = project_root / project_id / "project.json"
    legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
    manifest = project_root / project_id / "project.rambla.json"
    manifest.unlink()

    response = client.post("/api/curation/projects/open-file", json=legacy)
    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == project_id
    assert body["project_file_migrated"] is True
    assert body["resolve_calls"] == 0
    assert manifest.is_file()


def test_open_project_file_api_accepts_current_manifest(tmp_path):
    from backend.app.debug_server import create_app

    project_root = tmp_path / "projects"
    client = TestClient(create_app(
        project_root=project_root,
        probe_runner=lambda _: {"duration": 3, "fps": 25, "width": 640, "height": 360, "has_audio": False},
    ))
    project_id = client.post("/api/curation/projects", json={"name": "Current reel"}).json()["project_id"]
    payload = json.loads((project_root / project_id / "project.rambla.json").read_text(encoding="utf-8"))

    response = client.post("/api/curation/projects/open-file", json=payload)
    assert response.status_code == 200
    assert response.json()["project_id"] == project_id
    assert response.json()["project_file_migrated"] is False
