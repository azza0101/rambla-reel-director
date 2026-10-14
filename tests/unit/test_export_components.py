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
