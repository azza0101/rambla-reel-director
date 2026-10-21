import time
from fastapi import FastAPI
from fastapi.testclient import TestClient
from tests.unit.test_cut_pass_routes import tmp_path


def test_routes_are_observable_without_resolve_or_cloud(tmp_path):
    from backend.app.magic_routes import install_magic_routes
    from backend.app.magic_runner import MagicRunner
    from backend.app.magic_store import MagicStore
    class Services:
        async def run_phase(self, *args): return {}
    app = FastAPI()
    runner = MagicRunner(MagicStore(tmp_path), Services(), lambda _: 'v1')
    install_magic_routes(app, runner, lambda _: object())
    with TestClient(app) as client:
        assert client.post('/api/curation/projects/p/magic', json={'max_cloud_requests':0}).status_code == 422
        response = client.post('/api/curation/projects/p/magic', json={})
        assert response.status_code == 200
        run_id = response.json()['run_id']
        for _ in range(30):
            state = client.get('/api/curation/magic/'+run_id).json()
            if state['status'] != 'running': break
            time.sleep(.01)
        assert state['status'] == 'ready'
        assert client.get('/api/curation/projects/p/magic/latest').json()['run_id'] == run_id
        assert client.get('/api/curation/magic/invalid').status_code == 409


def test_stale_running_status_reports_resume_after_restart(tmp_path):
    from backend.app.magic_routes import install_magic_routes
    from backend.app.magic_runner import MagicRunner
    from backend.app.magic_store import MagicStore
    from backend.app.magic_models import MagicOptions
    store = MagicStore(tmp_path)
    row = store.create_or_resume('p', 'v1', MagicOptions())
    store.transition(row['run_id'], status='running')
    app = FastAPI()
    install_magic_routes(app, MagicRunner(store, None, lambda _: 'v1'), lambda _: object())
    with TestClient(app) as client:
        state = client.get('/api/curation/magic/'+row['run_id']).json()
        assert state['status'] == 'waiting_input'
        assert 'riprendi' in state['message'].lower()


def test_retry_selection_keeps_cut_and_editorial_checkpoints(tmp_path):
    from backend.app.magic_runner import MagicRunner
    from backend.app.magic_store import MagicStore
    from backend.app.magic_models import MagicOptions

    store = MagicStore(tmp_path)
    row = store.create_or_resume('p', 'v1', MagicOptions())
    checkpoints = {name: {'input_signature': name, 'result': {}}
                   for name in ('cut', 'editorial', 'research', 'selection', 'preparation', 'delivery')}
    store.transition(row['run_id'], checkpoints=checkpoints, status='partial')
    runner = MagicRunner(store, None, lambda _: 'v1')
    runner._schedule = lambda value: value
    result = runner.retry_from(row['run_id'], 'selection')
    assert set(result['checkpoints']) == {'cut', 'editorial', 'research'}


def test_restart_creates_a_new_run_without_deleting_the_previous_one(tmp_path):
    from backend.app.magic_runner import MagicRunner
    from backend.app.magic_store import MagicStore
    from backend.app.magic_models import MagicOptions

    store = MagicStore(tmp_path)
    first = store.create_or_resume('p', 'v1', MagicOptions())
    store.transition(first['run_id'], status='failed')
    runner = MagicRunner(store, None, lambda _: 'v1')
    runner._schedule = lambda value: value

    restarted = runner.restart(first['run_id'])

    assert restarted['run_id'] != first['run_id']
    assert store.read(first['run_id'])['status'] == 'failed'
    assert restarted['status'] == 'queued'
