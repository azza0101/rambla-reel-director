import json
from pathlib import Path

from fastapi.testclient import TestClient


def _client(tmp_path):
    from backend.app.curation_server import create_app

    project_root = tmp_path / "projects"
    allowed = tmp_path / "allowed"; allowed.mkdir()
    source = allowed / "source.mp4"; source.write_bytes(b"video")
    client = TestClient(create_app(
        project_root=project_root,
        allowed_media_roots=[allowed],
        probe_runner=lambda _: {"duration": 12, "fps": 25, "width": 1080, "height": 1920, "has_audio": False},
        audio_probe_runner=lambda _: 12.0,
    ))
    return client, project_root, source


def test_project_library_rename_clean_and_delete_endpoints(tmp_path):
    client, root, source = _client(tmp_path)
    created = client.post("/api/curation/projects", json={"name": "Old"}).json()
    pid = created["project_id"]
    assert client.post(f"/api/curation/projects/{pid}/source/local", json={"path": str(source)}).status_code == 200

    run = root / pid / "run"; run.mkdir(parents=True, exist_ok=True)
    (run / "transcript-raw.json").write_text('{"segments":[]}', encoding="utf-8")
    (run / "semantic-chunks.json").write_text("[]", encoding="utf-8")
    (run / "visual-plan.json").write_text('{"schema_version":"legacy"}', encoding="utf-8")
    (run / "online-candidates.json").write_text("[]", encoding="utf-8")
    cache = run / "asset-cache"; cache.mkdir(); (cache / "clip.mp4").write_bytes(b"media")

    library = client.get("/api/curation/projects")
    assert library.status_code == 200
    assert library.json()["projects"][0]["project_id"] == pid
    assert library.json()["projects"][0]["size_bytes"] > 0

    renamed = client.patch(f"/api/curation/projects/{pid}", json={"name": "KURA Ethical"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "KURA Ethical"
    assert client.get(f"/api/curation/projects/{pid}").json()["name"] == "KURA Ethical"

    cleaned = client.post(f"/api/curation/projects/{pid}/media/clean")
    assert cleaned.status_code == 200
    assert cleaned.json()["cleanup"]["deleted_bytes"] >= 5
    assert cleaned.json()["resolve_calls"] == 0
    assert (run / "transcript-raw.json").is_file()
    assert (run / "semantic-chunks.json").is_file()
    assert (run / "visual-plan.json").is_file()
    assert not (run / "online-candidates.json").exists()
    assert not cache.exists()

    deleted = client.delete(f"/api/curation/projects/{pid}")
    assert deleted.status_code == 200
    assert deleted.json()["resolve_calls"] == 0
    assert not (root / pid).exists()


def test_delete_and_clean_refuse_active_project_stage(tmp_path):
    import backend.app.debug_server as debug

    client, root, source = _client(tmp_path)
    pid = client.post("/api/curation/projects", json={"name": "Busy"}).json()["project_id"]
    client.post(f"/api/curation/projects/{pid}/source/local", json={"path": str(source)})
    run = root / pid / "run"; run.mkdir(parents=True, exist_ok=True)
    state = debug.RunState("busy-maintenance", source, run, status="RUNNING", stage_type="videos")
    debug.RUNS[state.run_id] = state
    try:
        assert client.post(f"/api/curation/projects/{pid}/media/clean").status_code == 409
        assert client.delete(f"/api/curation/projects/{pid}").status_code == 409
    finally:
        debug.RUNS.pop(state.run_id, None)


def test_beat_research_endpoint_starts_dedicated_worker_without_analyze(tmp_path):
    calls = []

    async def fake_research(state, beat_id, mode):
        calls.append((state.stage_type, beat_id, mode))

    from backend.app.curation_server import create_app
    project_root = tmp_path / "projects"
    allowed = tmp_path / "allowed"; allowed.mkdir()
    source = allowed / "source.mp4"; source.write_bytes(b"video")
    client = TestClient(create_app(
        project_root=project_root, allowed_media_roots=[allowed], research_runner=fake_research,
        probe_runner=lambda _: {"duration": 12, "fps": 25, "width": 1080, "height": 1920, "has_audio": False},
    ))
    pid = client.post("/api/curation/projects", json={"name": "Research"}).json()["project_id"]
    client.post(f"/api/curation/projects/{pid}/source/local", json={"path": str(source)})
    run = project_root / pid / "run"; run.mkdir(parents=True, exist_ok=True)
    for name, payload in {
        "transcript-raw.json": {"segments": []},
        "semantic-chunks.json": [{"id": "chunk-1", "text": "hello"}],
        "semantic-beats.json": {"beats": []},
        "visual-plan.json": {"schema_version": "rambla-visual-plan-1", "visual_beats": [{"id": "beat-1", "action": "BROLL", "covered_chunk_ids": ["chunk-1"], "start": 0, "end": 2, "original_text": "hello", "shots": [{"shot_id":"s1","description":"people walking","image_queries":["people walking"],"video_queries":["people walking"]}], "editorial_function":"show","core_meaning":"people walk","subtext":"movement","visual_mode":"single","avoid": []}]},
    }.items(): (run / name).write_text(json.dumps(payload), encoding="utf-8")
    # Active retrieval root requires an imported-plan snapshot matching visual-plan.
    from backend.app.editorial_import import active_retrieval_root
    rr = active_retrieval_root(run); rr.mkdir(parents=True, exist_ok=True)
    (rr / "imported-plan.json").write_text((run / "visual-plan.json").read_text(encoding="utf-8"), encoding="utf-8")

    response = client.post(f"/api/curation/projects/{pid}/beats/beat-1/research", json={"mode": "append"})
    assert response.status_code == 200
    body = response.json()
    assert body["stage"] == "research:append:beat-1"
    assert body["resolve_calls"] == 0
    import time; time.sleep(.05)
    assert calls == [("research:append:beat-1", "beat-1", "append")]
