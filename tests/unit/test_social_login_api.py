from fastapi.testclient import TestClient


def test_social_login_api_launches_profile_without_credentials(tmp_path):
    calls = []

    class Manager:
        def open_login(self, provider, *, start_url=None):
            calls.append((provider, start_url))
            return {"provider": provider, "status": "started", "pid": 99}
        def status(self):
            return {"tiktok": {"profile_ready": True}, "instagram": {"profile_ready": False}}

    from backend.app.curation_server import create_app
    app = create_app(
        project_root=tmp_path / "projects",
        allowed_media_roots=[tmp_path],
        probe_runner=lambda _: {"duration": 1, "fps": 25, "width": 1080, "height": 1920, "has_audio": False},
        browser_profile_manager=Manager(),
    )
    client = TestClient(app)

    response = client.post("/api/curation/social/tiktok/login")
    assert response.status_code == 200
    assert response.json()["provider"] == "tiktok"
    assert response.json()["status"] == "started"
    assert response.json()["resolve_calls"] == 0
    assert calls == [("tiktok", None)]

    assert client.post("/api/curation/social/facebook/login").status_code == 404
    assert client.post("/api/curation/social/tiktok/login", json={"password": "secret"}).status_code in {200, 422}
    assert "secret" not in repr(response.json())


def test_social_status_exposes_readiness_without_paths_or_cookie_data(tmp_path):
    class Manager:
        def open_login(self, provider, *, start_url=None):
            return {"provider": provider, "status": "started", "pid": 1}
        def status(self):
            return {"tiktok": {"profile_ready": True}, "instagram": {"profile_ready": False}}

    from backend.app.curation_server import create_app
    client = TestClient(create_app(
        project_root=tmp_path / "projects",
        allowed_media_roots=[tmp_path],
        probe_runner=lambda _: {"duration": 1, "fps": 25, "width": 1080, "height": 1920, "has_audio": False},
        browser_profile_manager=Manager(),
    ))
    body = client.get("/api/curation/social/status").json()
    assert body["providers"]["tiktok"]["profile_ready"] is True
    assert body["providers"]["instagram"]["profile_ready"] is False
    assert body["resolve_calls"] == 0
    serialized = repr(body).casefold()
    assert "cookie" not in serialized
    assert "profile_dir" not in serialized
    assert "password" not in serialized
