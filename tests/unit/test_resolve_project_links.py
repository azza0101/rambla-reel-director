from backend.app.resolve_project_links import choose_project


def test_explicit_link_wins_over_new_empty_capture():
    rows = [dict(project_id='empty', timeline_id='generated', reviewed=False, modified=20),
            dict(project_id='saved', timeline_id='source', reviewed=True, modified=10)]
    assert choose_project(rows, 'generated', {'generated': 'saved'}) == 'saved'


def test_reviewed_project_wins_over_new_empty_capture():
    rows = [dict(project_id='empty', timeline_id='source', reviewed=False, modified=20),
            dict(project_id='saved', timeline_id='source', reviewed=True, modified=10)]
    assert choose_project(rows, 'source', {}) == 'saved'


def test_unrelated_timeline_does_not_open_last_project():
    assert choose_project([dict(project_id='saved', timeline_id='other', reviewed=True, modified=1)], 'new', {}) == ''


def test_bridge_open_never_captures_audio():
    from tools.resolve_bridge.standalone_bridge import BridgeClient
    calls = []
    def request(path, method='GET', payload=None):
        calls.append(path)
        return {'project_id': 'saved', 'url': '/curation?project=saved'}
    assert BridgeClient(request_json=request).open_project()['project_id'] == 'saved'
    assert calls == ['/api/curation/resolve-bridge/open']


def test_bridge_ignores_newer_port_with_old_build(monkeypatch):
    import io, json
    import launch_local_v5
    from tools.resolve_bridge import standalone_bridge as bridge
    monkeypatch.setattr(launch_local_v5, 'source_build_token', lambda _: 'current')
    def open_url(url, timeout):
        if ':8812/' in url:
            return io.BytesIO(json.dumps({'status':'ok', 'build_token':'current'}).encode())
        if ':8819/' in url:
            return io.BytesIO(json.dumps({'status':'ok', 'build_token':'old'}).encode())
        raise OSError('offline')
    monkeypatch.setattr(bridge.urllib.request, 'urlopen', open_url)
    assert bridge.discover_base() == 'http://127.0.0.1:8812'


def test_open_saved_falls_back_without_linking_unrelated_timeline(tmp_path):
    from backend.app.resolve_project_links import saved_project_to_open, read
    from backend.app.atomic_io import write_json
    root=tmp_path/'projects'
    (root/'saved').mkdir(parents=True)
    write_json(root/'saved'/'project.json',{'project_id':'saved'})
    write_json(tmp_path/'last-open-project.json',{'project_id':'saved'})
    assert saved_project_to_open(root,'unrelated') == ('saved','last_saved')
    assert not (tmp_path/'resolve-project-links.json').exists()


def test_open_saved_prefers_current_timeline_link(tmp_path):
    from backend.app.resolve_project_links import saved_project_to_open
    from backend.app.atomic_io import write_json
    root=tmp_path/'projects'
    for pid in ('last','current'):
        (root/pid).mkdir(parents=True)
        write_json(root/pid/'project.json',{'project_id':pid})
    write_json(tmp_path/'last-open-project.json',{'project_id':'last'})
    write_json(tmp_path/'resolve-project-links.json',{'timeline':'current'})
    assert saved_project_to_open(root,'timeline') == ('current','timeline')

