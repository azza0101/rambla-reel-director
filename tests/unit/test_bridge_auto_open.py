from fastapi.testclient import TestClient

from backend.app.curation_server import create_app


def test_send_can_open_the_bridge_without_touching_resolve(tmp_path, monkeypatch):
    launched = []
    monkeypatch.setattr('backend.app.curation_server.launch_resolve_bridge_window', lambda: launched.append(True))
    client = TestClient(create_app(project_root=tmp_path / 'projects'))
    response = client.post('/api/curation/resolve-bridge/open-window')
    assert response.status_code == 200
    assert launched == [True]
    assert response.json()['status'] == 'opening'


def test_bridge_start_failure_is_visible(tmp_path, monkeypatch):
    def fail():
        raise RuntimeError('Bridge non trovato')
    monkeypatch.setattr('backend.app.curation_server.launch_resolve_bridge_window', fail)
    client = TestClient(create_app(project_root=tmp_path / 'projects'))
    response = client.post('/api/curation/resolve-bridge/open-window')
    assert response.status_code == 409
    assert 'Bridge non trovato' in response.json()['detail']
