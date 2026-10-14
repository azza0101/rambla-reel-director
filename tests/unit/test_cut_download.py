import json
import time
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from tests.unit.test_cut_pass_routes import tmp_path
from backend.app.cut_pass_routes import install_cut_routes
from backend.app.cut_pass import build_cut_plan
from tests.unit.test_cut_pass import transcript


def test_download_uses_full_render_and_rejects_stale_revision(tmp_path, monkeypatch):
    import backend.app.cut_pass_routes as module
    monkeypatch.setattr(module, 'verify_cut_render', lambda *args: None)
    folder = tmp_path / 'p' / 'cut'
    folder.mkdir(parents=True)
    raw = transcript([(0, 1, 'frase mantenuta')])
    plan = build_cut_plan(raw, duration=2, fps=30, signature='s', groups=[])
    plan['revision'] = 'r1'
    (folder / 'plan.json').write_text(json.dumps(plan))
    (folder / 'transcript-original.json').write_text(json.dumps(raw))
    (folder / 'clean-r1.mp4').write_bytes(b'full-resolution')
    (folder / 'preview-r1.mp4').write_bytes(b'proxy')
    project = SimpleNamespace(source_video=SimpleNamespace(path=str(tmp_path/'original.mp4'), has_audio=True), analysis_signature='s')
    store = SimpleNamespace(load=lambda pid: project)
    app = FastAPI()
    install_cut_routes(app, store, tmp_path, lambda pid: project, lambda _: None)
    with TestClient(app) as client:
        assert client.get('/api/curation/projects/p/cut/download/r1').content == b'full-resolution'
        assert client.get('/api/curation/projects/p/cut/download/old').status_code == 409
        response = client.post('/api/curation/projects/p/cut/download')
        assert response.status_code == 200
        for _ in range(100):
            state = client.get('/api/curation/projects/p/cut').json()
            if state['job']['status'] != 'running': break
            time.sleep(.01)
        assert state['job']['status'] == 'succeeded', state
        assert state['job']['result']['download_url'].endswith('/download/r1')


def test_failed_render_never_leaves_a_downloadable_partial_file(tmp_path, monkeypatch):
    import subprocess
    from pathlib import Path
    import pytest
    import backend.app.cut_pass_routes as module
    plan = build_cut_plan(transcript([(0, 1, 'test')]), duration=2, fps=30, signature='s', groups=[])
    target = tmp_path / 'clean.mp4'
    def fail(command, **kwargs):
        Path(command[-1]).write_bytes(b'partial')
        raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(module.subprocess, 'run', fail)
    with pytest.raises(subprocess.CalledProcessError):
        module.render_cut(tmp_path / 'original.mp4', target, plan)
    assert not target.exists()
    assert not list(tmp_path.glob('*.partial.mp4'))
