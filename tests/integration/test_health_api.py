from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_health():
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_identifies_the_running_desktop_build(monkeypatch):
    from backend.app.debug_server import create_app as create_debug_app
    monkeypatch.setenv('RAMBLA_BUILD_TOKEN','desktop-build-7')
    response=TestClient(create_debug_app()).get('/health')
    assert response.json()['build_token']=='desktop-build-7'
