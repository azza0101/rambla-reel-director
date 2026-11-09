import json


def test_custom_selections_allow_more_than_twelve_and_preserve_existing(tmp_path):
    from fastapi.testclient import TestClient
    from backend.app.curation_project import ProjectStore
    from backend.app.curation_server import create_app
    root = tmp_path / 'projects'
    project = ProjectStore(root, probe_runner=lambda _: {}).create('Test')
    run = root / project.project_id / 'run'
    run.mkdir(exist_ok=True)
    ids = [f'envato:{i}' for i in range(15)]
    (run / 'generic-coverage.json').write_text(json.dumps({'items': [{'provider_id': i} for i in ids], 'selected': ids[:12]}))
    with TestClient(create_app(project_root=root)) as client:
        result = client.put(f'/api/curation/projects/{project.project_id}/generic-coverage/selection', json={'provider_ids': ids})
    assert result.status_code == 200
    assert result.json()['selected'] == ids
