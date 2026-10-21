import pytest
from backend.app.export_components import normalize_components,filter_selected_media


def test_selection_defaults_and_empty_selection():
    assert normalize_components(None,has_native_cut=True)['video'] is True
    assert normalize_components(None,has_native_cut=False)['video'] is False
    flags={k:False for k in ['video','subtitles','highlights','broll','social','generic']}
    with pytest.raises(ValueError):normalize_components(flags,has_native_cut=True)
    flags['video']=True
    assert sum(normalize_components(flags,has_native_cut=True).values())==1


def test_social_and_stock_filters_are_independent():
    rows=[{'provider':'pexels'},{'provider':'youtube_shorts'},{'provider':'tiktok'},{'provider':'google_images'}]
    assert filter_selected_media(rows,{'broll':True,'social':False})==[rows[0],rows[3]]
    assert filter_selected_media(rows,{'broll':False,'social':True})==[rows[1],rows[2]]


def test_video_only_preparation_has_no_editorial_or_template_dependency(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.curation_server import create_app
    from backend.app.curation_project import ProjectStore
    import backend.app.native_cut_export as native
    import time
    root = tmp_path / 'projects'
    project = ProjectStore(root, probe_runner=lambda _: {}).create('Native CUT')
    cut = {'fps': '30', 'width': 1080, 'height': 1920, 'duration_seconds': 1,
           'segments': [{'source_in_frame': 0, 'source_out_frame': 30,
                         'edited_in_frame': 0, 'edited_out_frame': 30}]}
    monkeypatch.setattr(native, 'load_native_cut', lambda *args: cut)
    import backend.app.resolve_textplus_timeline as timeline_helper
    applied = []
    monkeypatch.setattr(timeline_helper, 'run_resolve_helper', lambda payload: applied.append(payload) or {'status': 'created'})
    app = create_app(project_root=root, allowed_media_roots=[tmp_path], resolve_template_bundled_root=tmp_path/'empty-templates')
    with TestClient(app) as client:
        client.post('/api/curation/resolve-bridge/session', json={'bridge_session_id': 'test-native', 'bridge_version': 'v0071'})
        flags = normalize_components({'video': True})
        url = f'/api/curation/projects/{project.project_id}'
        assert client.put(url + '/export-options', json=flags).status_code == 200
        assert client.get(url + '/export-options').json()['components'] == flags
        response = client.post(url + '/resolve-preparation', json=flags)
        assert response.status_code == 200
        job = response.json()
        for _ in range(100):
            job = client.get('/api/curation/resolve-preparation/' + job['job_id']).json()
            if job['status'] != 'preparing': break
            time.sleep(.01)
        assert job['status'] == 'ready', job.get('message')
        assert job['package']['summary']['cut_count'] == 1
        assert job['package']['summary']['title_count'] == 0
        package_id = job['package']['package_id']
        pending = client.get('/api/curation/resolve-handoffs/pending', params={'resolve_project':'TEST', 'timeline_id':'unrelated', 'bridge_session_id':'test-native'}).json()
        assert pending['packages'][0]['package_id'] == package_id
        wrong_session = client.get('/api/curation/resolve-handoffs/pending', params={'resolve_project':'TEST', 'bridge_session_id':'old-session'}).json()
        assert not wrong_session['packages']
        response = client.post('/api/curation/resolve-handoffs/' + package_id + '/apply', json={
            'destination_mode':'active', 'current_project':'TEST', 'current_timeline_id':'untouched'})
        assert response.status_code == 200, response.json()
        for _ in range(100):
            state = client.get('/api/curation/resolve-handoffs/' + package_id).json()
            if state['status'] != 'applying': break
            time.sleep(.01)
        assert state['status'] == 'completed', state.get('error')
        assert applied[0]['destination_mode'] == 'new'
        assert not applied[0].get('titles')


from tests.unit.test_cut_pass_routes import tmp_path


def test_bridge_heartbeat_does_not_query_resolve_during_apply(tmp_path, monkeypatch):
    import threading
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    from backend.app.curation_server import create_app
    from backend.app.resolve_handoff import ResolveHandoffStore
    import backend.app.resolve_bridge as bridge
    import backend.app.resolve_textplus_timeline as helper
    calls = []
    timeline = SimpleNamespace(GetName=lambda: 'T', GetUniqueId=lambda: 'timeline-id')
    project = SimpleNamespace(GetName=lambda: 'TEST', GetCurrentTimeline=lambda: timeline)
    resolve = SimpleNamespace(GetProjectManager=lambda: SimpleNamespace(GetCurrentProject=lambda: project))
    monkeypatch.setattr(bridge, 'connect_resolve', lambda: calls.append('read') or resolve)
    monkeypatch.setattr(bridge, 'timeline_range', lambda _: (0, 30, 'timeline'))
    gate = threading.Event()
    def run(payload):
        gate.wait(2)
        return {}
    monkeypatch.setattr(helper, 'run_resolve_helper', run)
    root = tmp_path/'projects'
    app = create_app(project_root=root)
    project_root = root/'p'; project_root.mkdir(parents=True)
    store = ResolveHandoffStore(root)
    package = store.prepare(project_root, {'source_project_name': 'TEST'})
    try:
        with TestClient(app) as client:
            assert client.get('/api/curation/resolve-bridge/status').json()['connected']
            app.state.resolve_handoff_jobs.apply(project_root, package['package_id'], 'new', current_project='TEST', current_timeline_id='timeline-id')
            status = client.get('/api/curation/resolve-bridge/status').json()
            assert status['connected'] and status['operation_in_progress']
            assert calls == ['read']
    finally:
        gate.set()


def test_export_options_remain_readable_when_media_plan_needs_refresh(tmp_path, monkeypatch):
    import json
    from fastapi.testclient import TestClient
    from backend.app.curation_server import create_app
    from backend.app.curation_project import ProjectStore
    import backend.app.curation_artifacts as artifacts
    root=tmp_path/'projects'
    project=ProjectStore(root,probe_runner=lambda _:{}).create('Text preserved')
    run=root/project.project_id/'run';run.mkdir(exist_ok=True)
    (run/'semantic-chunks.json').write_text(json.dumps([{'id':'c1','start':0,'end':1,'text':'Ciao mondo'}]),'utf-8')
    def invalid(*args): raise ValueError('covered_chunk_ids must cover adjacent chunks')
    monkeypatch.setattr(artifacts,'load_curation_run',invalid)
    client=TestClient(create_app(project_root=root,allowed_media_roots=[tmp_path]))
    response=client.get(f'/api/curation/projects/{project.project_id}/export-options')
    assert response.status_code==200
    assert response.json()['counts']['subtitles']>0
    assert response.json()['media_warning']
