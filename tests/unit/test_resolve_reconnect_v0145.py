from fastapi.testclient import TestClient

from backend.app.curation_server import create_app
from backend.app.resolve_handoff import ResolveHandoffStore


def test_reconnect_reports_offline_and_reoffers_same_package(monkeypatch, tmp_path):
    root = tmp_path / 'projects'; project = root / 'p1'; project.mkdir(parents=True)
    store = ResolveHandoffStore(root)
    package = store.prepare(project, {'project_id':'p1','source_project_name':'Test',
                                      'source_timeline_id':'tl','bridge_session_id':'old'})
    client = TestClient(create_app(project_root=root))
    url = '/api/curation/resolve-handoffs/' + package['package_id'] + '/reconnect'
    assert 'Bridge offline' in client.post(url).json()['detail']
    client.post('/api/curation/resolve-bridge/session', json={'bridge_session_id':'new'})
    class Timeline:
        def GetName(self): return 'Edit'
        def GetUniqueId(self): return 'tl'
        def GetStartFrame(self): return 0
        def GetEndFrame(self): return 100
    class Project:
        def GetName(self): return 'Test'
        def GetCurrentTimeline(self): return Timeline()
    class Manager:
        def GetCurrentProject(self): return Project()
    class Resolve:
        def GetProjectManager(self): return Manager()
    monkeypatch.setattr('backend.app.resolve_bridge.connect_resolve', lambda: Resolve())
    monkeypatch.setattr('backend.app.resolve_bridge.timeline_range', lambda _: (0, 99, 'timeline'))
    response = client.post(url)
    assert response.status_code == 200, response.text
    assert response.json()['package_id'] == package['package_id']
    assert response.json()['bridge_session_id'] == 'new'
    rows = client.get('/api/curation/resolve-handoffs/pending', params={'resolve_project':'Test','bridge_session_id':'new'}).json()['packages']
    assert [row['package_id'] for row in rows] == [package['package_id']]
    assert store.read(project, package['package_id'])['status'] == 'pending'
    diag = client.get('/api/curation/resolve-handoffs/' + package['package_id'] + '/diagnostics').json()
    assert diag['package_bridge_session_id'] == 'new'
    assert diag['resolve_project'] == 'Test' and diag['resolve']['timeline_id'] == 'tl'


def test_reconnect_control_displays_failure_and_diagnostics():
    from backend.app.timeline_export_ui import PANEL, JS
    assert 'RICOLLEGA BRIDGE' in PANEL
    assert '/reconnect' in JS and 'Collegamento non riuscito' in JS
    assert 'loadResolveDebugV39' in JS
