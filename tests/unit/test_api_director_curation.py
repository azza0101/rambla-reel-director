import json

from fastapi.testclient import TestClient


def test_api_director_route_requires_transcript_and_never_accepts_source_video_payload(monkeypatch, tmp_path):
    import backend.app.curation_server as server
    from backend.app import debug_server as debug

    debug.RUNS.clear()
    monkeypatch.setenv("GEMINI_API_KEY", "configured-for-test")

    async def fake_director(state, provider):
        assert provider in {"auto", "gemini", "groq"}
        state.status = "SUCCEEDED"
        state.return_code = 0

    monkeypatch.setattr(server, "_run_director_state", fake_director)

    allowed = tmp_path / "allowed"
    allowed.mkdir()
    source = allowed / "source.mp4"
    source.write_bytes(b"fixture")

    root = tmp_path / "projects"
    client = TestClient(server.create_app(
        project_root=root,
        allowed_media_roots=[allowed, root],
        probe_runner=lambda _: {
            "duration": 10,
            "fps": 25,
            "width": 1080,
            "height": 1920,
            "has_audio": False,
        },
    ))

    project = client.post("/api/curation/projects", json={"name": "V5 UI"}).json()
    pid = project["project_id"]
    response = client.post(
        f"/api/curation/projects/{pid}/source/local",
        json={"path": str(source)},
    )
    assert response.status_code == 200

    missing = client.post(
        f"/api/curation/projects/{pid}/director",
        json={"provider": "auto"},
    )
    assert missing.status_code == 422
    assert "analyze transcript" in missing.json()["detail"]

    run = root / pid / "run"
    run.mkdir(parents=True, exist_ok=True)
    (run / "transcript-raw.json").write_text(
        json.dumps({"language": "it", "segments": []}),
        encoding="utf-8",
    )
    (run / "semantic-chunks.json").write_text(
        json.dumps([{"id": "c1", "start": 0.0, "end": 1.0, "text": "ciao mondo"}]),
        encoding="utf-8",
    )
    (run / "analysis-signature.json").write_text(
        json.dumps({"analysis_signature": "test"}),
        encoding="utf-8",
    )

    started = client.post(
        f"/api/curation/projects/{pid}/director",
        json={"provider": "auto"},
    )
    assert started.status_code == 200
    body = started.json()
    assert body["status"] == "started"
    assert body["stage"] == "director_api"
    assert body["provider"] == "auto"
    assert body["source_video_sent_to_ai"] is False
    assert "video" not in body or body.get("video") is None
    assert body["run_id"] in debug.RUNS
    assert debug.RUNS[body["run_id"]].stage_type == "director_api"


def test_api_director_route_rejects_unknown_provider(monkeypatch, tmp_path):
    import backend.app.curation_server as server

    monkeypatch.setenv("GEMINI_API_KEY", "configured-for-test")
    client = TestClient(server.create_app(
        project_root=tmp_path / "projects",
        allowed_media_roots=[tmp_path],
        probe_runner=lambda _: {
            "duration": 1,
            "fps": 25,
            "width": 1080,
            "height": 1920,
            "has_audio": False,
        },
    ))
    project = client.post("/api/curation/projects", json={"name": "provider"}).json()
    response = client.post(
        f"/api/curation/projects/{project['project_id']}/director",
        json={"provider": "openai"},
    )
    assert response.status_code in {404, 422}


def test_ai_status_exposes_auto_gemini_and_groq_without_keys(monkeypatch, tmp_path):
    import backend.app.curation_server as server

    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test")
    client = TestClient(server.create_app(
        project_root=tmp_path / "projects",
        allowed_media_roots=[tmp_path],
        probe_runner=lambda _: {
            "duration": 1,
            "fps": 25,
            "width": 1080,
            "height": 1920,
            "has_audio": False,
        },
    ))

    body = client.get("/api/curation/ai/status").json()
    assert body["providers"]["auto"]["configured"] is True
    assert body["providers"]["gemini"]["configured"] is True
    assert body["providers"]["groq"]["configured"] is True
    assert body["providers"]["groq"]["model"] == "qwen/qwen3.8-27b"
    serialized = repr(body)
    assert "gemini-test" not in serialized
    assert "groq-test" not in serialized
