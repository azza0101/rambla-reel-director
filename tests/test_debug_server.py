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
    assert "$('stop').onclick" in page
    assert "`/v1/debug/runs/${activeRunId}/cancel`" in page


def test_project_api_persists_registered_source_and_rejects_outside_media():
    """Removing project-scoped asset resolution would expose arbitrary files again."""
    from backend.app.debug_server import create_app

    root = _project_test_root()
    try:
        source = root / "allowed" / "source.mp4"
        source.parent.mkdir()
        source.write_bytes(b"video")
        def normalize(command): Path(command[-1]).write_bytes(b"wav")
        client = TestClient(create_app(project_root=root / "projects", allowed_media_roots=[root / "allowed"], probe_runner=lambda _: {"duration": 3, "fps": 25, "width": 640, "height": 360, "has_audio": True}, audio_probe_runner=lambda _: 3.0, audio_command_runner=normalize))

        created = client.post("/api/curation/projects", json={"name": "Demo reel"})
        assert created.status_code == 201
        project_id = created.json()["project_id"]

        registered = client.post(f"/api/curation/projects/{project_id}/source/local", json={"path": str(source)})
        assert registered.status_code == 200
        assert registered.json()["source_video"]["duration"] == 3.0
        assert registered.json()["guide_audio"]["mode"] == "original"

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


def test_guide_audio_selection_normalizes_tracks_and_changes_analysis_signature():
    from backend.app.debug_server import create_app

    root = _project_test_root(); commands = []
    def run(command):
        commands.append(command); Path(command[-1]).write_bytes(b"wav")
    try:
        source = root / "source.mp4"; source.write_bytes(b"video")
        app = create_app(project_root=root / "projects", allowed_media_roots=[root],
            probe_runner=lambda _: {"duration": 10, "fps": 25, "width": 640, "height": 360, "has_audio": True},
            audio_probe_runner=lambda _: 8.0, audio_command_runner=run)
        client = TestClient(app); pid = client.post("/api/curation/projects", json={}).json()["project_id"]
        registered = client.post(f"/api/curation/projects/{pid}/source/local", json={"path": str(source)}).json()
        original = client.post(f"/api/curation/projects/{pid}/guide/original").json()
        external = client.put(f"/api/curation/projects/{pid}/guide/upload?filename=voice.mp3", content=b"audio").json()

        assert original["guide_audio"]["mode"] == "original"
        assert external["guide_audio"]["mode"] == "external"
        assert external["guide_audio"]["duration"] == 8.0
        assert external["guide_duration_warning"].endswith("2.00s")
        assert registered["guide_audio"]["mode"] == "original"
        assert registered["analysis_signature"] == original["analysis_signature"]
        assert external["analysis_signature"] != original["analysis_signature"]
        assert all(command[-7:-1] == ["-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le"] for command in commands)
    finally:
        shutil.rmtree(root)


def test_run_command_carries_project_guide_and_signature(monkeypatch):
    from backend.app.debug_server import RunState, _command
    monkeypatch.setenv("RAMBLA_DEBUG_COMMAND_JSON", '["python","runner.py","--video","{video}","--output-dir","{output}"]')
    state = RunState("r", Path("source.mp4"), Path("run"), guide_audio=Path("guide.wav"), analysis_signature="abc")
    command = _command(state)
    assert command[-4:] == ["--guide-audio", "guide.wav", "--analysis-signature", "abc"]


def test_task7_http_acceptance_path(monkeypatch):
    import asyncio
    import backend.app.debug_server as server
    root = _project_test_root(); run = root / "run"; run.mkdir(); gate = asyncio.Event()
    def normalize(command): Path(command[-1]).write_bytes(b"wav")
    async def held_worker(state):
        state.status = "RUNNING"; state.progress["prepare"] = 100
        await gate.wait()
    monkeypatch.setattr(server, "_run", held_worker)
    try:
        app = server.create_app(project_root=root / "projects", curation_run_root=run,
            probe_runner=lambda _: {"duration": 6, "fps": 25, "width": 1080, "height": 1920, "has_audio": True},
            audio_probe_runner=lambda _: 6.0, audio_command_runner=normalize)
        assert sum(getattr(route, "path", None) == "/curation" for route in app.routes) == 1
        with TestClient(app) as client:
            page = client.get("/curation")
            assert page.status_code == 200
            for contract in ('id="file"', 'id="originalGuide"', 'id="replaceGuide"', 'id="analyze"', 'id="stop"', 'id="phrases"', 'id="videos"', 'id="images"', 'id="selected"', 'id="confirm"', "left>0", "data-m"):
                assert contract in page.text
            pid = client.post("/api/curation/projects", json={}).json()["project_id"]
            run = root / "projects" / pid / "run"
            run.mkdir()
            uploaded = client.put(f"/api/curation/projects/{pid}/source/upload?filename=reel.mp4", content=b"video").json()
            assert uploaded["guide_audio"]["mode"] == "original"
            original_signature = uploaded["analysis_signature"]
            replaced = client.put(f"/api/curation/projects/{pid}/guide/upload?filename=voice.mp3", content=b"voice").json()
            assert replaced["analysis_signature"] != original_signature
            started = client.post(f"/api/curation/projects/{pid}/analyze").json()
            snapshot = client.get(f"/v1/debug/runs/{started['run_id']}").json()
            assert snapshot["status"] == "RUNNING" and snapshot["total_progress"] > 0
            assert client.post(f"/v1/debug/runs/{started['run_id']}/cancel").json()["status"] == "CANCELLED"
            (run / "semantic-chunks.json").write_text('[{"id":"chunk-1","text":"Phrase"}]', encoding="utf-8")
            (run / "online-candidates.json").write_text("[]", encoding="utf-8")
            hydrated = client.get(f"/api/curation/projects/{pid}/curation").json()
            assert hydrated["chunks"][0]["text"] == "Phrase" and hydrated["resolve_calls"] == 0
            saved = client.put(f"/api/curation/projects/{pid}/curation/chunks/chunk-1/selection", json={"asset_ids": [], "no_broll": True}).json()
            assert saved["selection"]["no_broll"] is True and saved["resolve_calls"] == 0
            assert client.get(f"/api/curation/projects/{pid}/media/unknown/preview").status_code == 404
    finally:
        gate.set(); shutil.rmtree(root)


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
        legacy = root / "run"; legacy.mkdir()
        (legacy / "semantic-chunks.json").write_text('[{"id":"legacy","text":"Must not leak"}]', encoding="utf-8")
        client = TestClient(create_app(project_root=root / "projects", curation_run_root=legacy))
        project_id = client.post("/api/curation/projects", json={}).json()["project_id"]
        assert client.get(f"/api/curation/projects/{project_id}/curation").json()["chunks"] == []
        run = root / "projects" / project_id / "run"; run.mkdir()
        (run / "semantic-chunks.json").write_text('[{"id":"chunk-1","text":"A line"}]', encoding="utf-8")
        (run / "online-candidates.json").write_text('[]', encoding="utf-8")

        hydrated = client.get(f"/api/curation/projects/{project_id}/curation")
        saved = client.put(f"/api/curation/projects/{project_id}/curation/chunks/chunk-1/selection", json={"asset_ids": [], "no_broll": True})

        assert hydrated.status_code == 200
        assert hydrated.json()["chunks"][0]["text"] == "A line"
        assert saved.status_code == 200
        assert saved.json()["selection"] == {"chunk_id": "chunk-1", "no_broll": True, "selected_assets": []}
        assert (run / "selection-plan.json").is_file()
        other_id = client.post("/api/curation/projects", json={"name": "Other"}).json()["project_id"]
        other = client.get(f"/api/curation/projects/{other_id}/curation").json()
        assert other["chunks"] == [] and other["selection_plan"] == {"chunks": {}}
    finally:
        shutil.rmtree(root)


def test_project_analyze_reuses_existing_artifacts_without_starting_provider():
    """Removing reuse-first routing would trigger expensive analysis just to render curation."""
    from backend.app.debug_server import create_app

    root = _project_test_root()
    try:
        source = root / "source.mp4"; source.write_bytes(b"video")
        client = TestClient(create_app(project_root=root / "projects", allowed_media_roots=[root], probe_runner=lambda _: {"duration": 1, "fps": 25, "width": 1, "height": 1, "has_audio": False}))
        project = client.post("/api/curation/projects", json={}).json()
        project_id = project["project_id"]
        project = client.post(f"/api/curation/projects/{project_id}/source/local", json={"path": str(source)}).json()
        run = root / "projects" / project_id / "run"; run.mkdir()
        (run / "semantic-chunks.json").write_text('[]', encoding="utf-8")
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
