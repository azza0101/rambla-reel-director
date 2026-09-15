from pathlib import Path
import json
import shutil
import uuid

from fastapi.testclient import TestClient

from backend.app.debug_server import ArtifactProgressTracker, DebugEvent, RunState, parse_worker_line, render_debug_page


def _project_test_root() -> Path:
    root = Path.cwd() / ".test-project-api" / uuid.uuid4().hex
    root.mkdir(parents=True)
    return root


def test_parse_worker_line_accepts_structured_event():
    event = parse_worker_line('RAMBLA_EVENT {"stage":"qwen_final","progress":72,"message":"5 frames","data":{"candidate":"A"}}')
    assert event == DebugEvent("qwen_final", "5 frames", 72.0, {"candidate": "A"})


def test_artifact_tracker_reports_real_milestones_once(tmp_path: Path):
    tracker = ArtifactProgressTracker(tmp_path)
    assert tracker.scan() == []
    (tmp_path / "transcript-raw.json").write_text("{}", encoding="utf-8")
    assert [(e.stage, e.progress) for e in tracker.scan()] == [("asr", 100.0)]
    assert tracker.scan() == []
    (tmp_path / "semantic-beats.json").write_text("{}", encoding="utf-8")
    (tmp_path / "online-candidates.json").write_text("[]", encoding="utf-8")
    assert [(e.stage, e.progress) for e in tracker.scan()] == [("semantic_chunking", 100.0), ("online_search", 100.0)]


def test_weighted_total_progress_is_monotonic():
    state = RunState("r1", Path("input.mp4"), Path("run"))
    assert state.total() == 0.0
    state.progress["prepare"] = 100.0
    first = state.total()
    state.progress["asr"] = 50.0
    assert state.total() > first


def test_page_has_one_click_live_debug_ui():
    page = render_debug_page()
    assert "ESEGUI" in page
    assert "EventSource" in page
    assert "ASR / trascrizione" in page
    assert "EvidenceIntent" in page
    assert "Qwen final" in page
    assert "KURA_Finto etico_draft 1.mp4" in page


def test_project_api_persists_registered_source_and_rejects_outside_media():
    """Removing project-scoped asset resolution would expose arbitrary files again."""
    from backend.app.debug_server import create_app

    root = _project_test_root()
    try:
        source = root / "allowed" / "source.mp4"
        source.parent.mkdir()
        source.write_bytes(b"video")
        client = TestClient(create_app(project_root=root / "projects", allowed_media_roots=[root / "allowed"], probe_runner=lambda _: {"duration": 3, "fps": 25, "width": 640, "height": 360, "has_audio": True}))

        created = client.post("/api/curation/projects", json={"name": "Demo reel"})
        assert created.status_code == 201
        project_id = created.json()["project_id"]

        registered = client.post(f"/api/curation/projects/{project_id}/source/local", json={"path": str(source)})
        assert registered.status_code == 200
        assert registered.json()["source_video"]["duration"] == 3.0

        unknown = client.get(f"/api/curation/projects/{project_id}/media/not-an-asset/preview")
        assert unknown.status_code == 404
    finally:
        shutil.rmtree(root)


def test_project_api_accepts_upload_without_browser_path():
    """Removing the upload route would make the setup flow depend on local browser paths."""
    from backend.app.debug_server import create_app

    root = _project_test_root()
    try:
        client = TestClient(create_app(project_root=root / "projects", probe_runner=lambda _: {"duration": 4, "fps": 24, "width": 1280, "height": 720, "has_audio": False}))
        project_id = client.post("/api/curation/projects", json={}).json()["project_id"]

        response = client.put(f"/api/curation/projects/{project_id}/source/upload?filename=clip.mp4", content=b"video")

        assert response.status_code == 200
        assert response.json()["source_video"]["path"].endswith("clip.mp4")
    finally:
        shutil.rmtree(root)


def test_legacy_arbitrary_path_media_route_is_not_exposed():
    """Restoring a browser-supplied path parameter would reintroduce filesystem serving."""
    from backend.app.debug_server import create_app

    response = TestClient(create_app()).get("/api/curation/media?path=C:/Windows/win.ini")

    assert response.status_code == 404


def test_project_hydration_reads_artifacts_and_persists_no_broll():
    """Removing project hydration or atomic selection storage loses a saved editorial decision."""
    from backend.app.debug_server import create_app

    root = _project_test_root()
    try:
        run = root / "run"
        run.mkdir()
        (run / "semantic-chunks.json").write_text('[{"id":"chunk-1","text":"A line"}]', encoding="utf-8")
        (run / "online-candidates.json").write_text('[]', encoding="utf-8")
        client = TestClient(create_app(project_root=root / "projects", curation_run_root=run))
        project_id = client.post("/api/curation/projects", json={}).json()["project_id"]

        hydrated = client.get(f"/api/curation/projects/{project_id}/curation")
        saved = client.put(f"/api/curation/projects/{project_id}/curation/chunks/chunk-1/selection", json={"asset_ids": [], "no_broll": True})

        assert hydrated.status_code == 200
        assert hydrated.json()["chunks"][0]["text"] == "A line"
        assert saved.status_code == 200
        assert saved.json()["selection"] == {"chunk_id": "chunk-1", "no_broll": True, "selected_assets": []}
        assert (run / "selection-plan.json").is_file()
    finally:
        shutil.rmtree(root)


def test_project_analyze_reuses_existing_artifacts_without_starting_provider():
    """Removing reuse-first routing would trigger expensive analysis just to render curation."""
    from backend.app.debug_server import create_app

    root = _project_test_root()
    try:
        run = root / "run"
        run.mkdir()
        (run / "semantic-chunks.json").write_text('[]', encoding="utf-8")
        client = TestClient(create_app(project_root=root / "projects", curation_run_root=run))
        project = client.post("/api/curation/projects", json={}).json()
        project_id = project["project_id"]
        (run / "analysis-signature.json").write_text(json.dumps({"analysis_signature": project["analysis_signature"]}), encoding="utf-8")

        response = client.post(f"/api/curation/projects/{project_id}/analyze")

        assert response.status_code == 200
        assert response.json() == {"status": "reused", "resolve_calls": 0}
    finally:
        shutil.rmtree(root)


def test_cancel_terminates_running_process_and_is_idempotent():
    from backend.app.debug_server import RUNS, RunState, create_app

    class Process:
        returncode = None
        terminated = 0
        def terminate(self):
            self.terminated += 1
            self.returncode = -15
        async def wait(self):
            return self.returncode

    process = Process()
    state = RunState("cancel-test", Path("source.mp4"), Path("run"), status="RUNNING", process=process)
    RUNS[state.run_id] = state
    try:
        client = TestClient(create_app())
        first = client.post("/v1/debug/runs/cancel-test/cancel")
        second = client.post("/v1/debug/runs/cancel-test/cancel")
        assert first.json()["status"] == "CANCELLED"
        assert second.json()["status"] == "CANCELLED"
        assert process.terminated == 1
    finally:
        RUNS.pop(state.run_id, None)


def test_cancel_kills_worker_that_ignores_terminate(monkeypatch):
    import asyncio
    from backend.app.debug_server import RUNS, RunState, create_app

    class Process:
        returncode = None
        killed = False
        def terminate(self): pass
        def kill(self): self.killed = True; self.returncode = -9
        async def wait(self):
            if not self.killed: raise asyncio.TimeoutError
            return self.returncode

    async def immediate(awaitable, timeout): return await awaitable
    monkeypatch.setattr(asyncio, "wait_for", immediate)
    process = Process(); state = RunState("kill-test", Path("source.mp4"), Path("run"), status="RUNNING", process=process)
    RUNS[state.run_id] = state
    try:
        response = TestClient(create_app()).post("/v1/debug/runs/kill-test/cancel")
        assert response.json()["status"] == "CANCELLED"
        assert process.killed is True
    finally:
        RUNS.pop(state.run_id, None)
