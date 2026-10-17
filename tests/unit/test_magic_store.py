import pytest
from tests.unit.test_cut_pass_routes import tmp_path


def test_duplicate_start_reuses_run_and_signature_change_rejects_resume(tmp_path):
    from backend.app.magic_store import MagicStore
    from backend.app.magic_models import MagicOptions
    store = MagicStore(tmp_path)
    run = store.create_or_resume('project', 'source-v1', MagicOptions())
    assert store.create_or_resume('project', 'source-v1', MagicOptions())['run_id'] == run['run_id']
    store.checkpoint(run['run_id'], 'cut', {'output_project_id': 'child'}, 'phase-v1')
    assert MagicStore(tmp_path).read(run['run_id'])['checkpoints']['cut']['result']['output_project_id'] == 'child'
    with pytest.raises(ValueError, match='sorgente'):
        store.validate_source(run['run_id'], 'source-v2')


def test_crash_preserves_unknown_call_and_budget_counts_attempts(tmp_path):
    from backend.app.magic_store import MagicStore
    from backend.app.magic_models import MagicOptions
    store = MagicStore(tmp_path)
    run = store.create_or_resume('p', 'v1', MagicOptions(max_cloud_requests=2, max_visual_requests=1))
    call = store.begin_call(run['run_id'], 'asr', 'groq', 'input-v1')
    recovered = MagicStore(tmp_path)
    assert recovered.recover(run['run_id'])['status'] == 'waiting_input'
    assert recovered.read(run['run_id'])['calls'][call]['status'] == 'unknown'
    with pytest.raises(ValueError, match='incerto'):
        recovered.begin_call(run['run_id'], 'asr', 'groq', 'input-v1')
    recovered.finish_call(run['run_id'], call, result={'transcript': 'ready'})
    recovered.begin_call(run['run_id'], 'visual', 'gemini', 'visual-v1', visual=True)
    with pytest.raises(ValueError, match='budget'):
        recovered.begin_call(run['run_id'], 'editorial', 'groq', 'input-v2')


def test_explicitly_failed_provider_reply_does_not_consume_magic_budget(tmp_path):
    from backend.app.magic_store import MagicStore
    from backend.app.magic_models import MagicOptions
    store = MagicStore(tmp_path)
    run = store.create_or_resume('p', 'v1', MagicOptions(max_cloud_requests=1))
    failed = store.begin_call(run['run_id'], 'editorial', 'groq', 'bad-response')
    store.finish_call(run['run_id'], failed, result={'status_code':400}, error='HTTP 400')
    next_call = store.begin_call(run['run_id'], 'editorial', 'groq', 'usable-response')
    assert next_call


def test_output_project_reload_can_find_its_magic_run_without_reusing_it_as_source(tmp_path):
    from backend.app.magic_store import MagicStore
    from backend.app.magic_models import MagicOptions
    store=MagicStore(tmp_path)
    row=store.create_or_resume('source','signature',MagicOptions())
    store.transition(row['run_id'],output_project_id='child')
    assert store.latest_for_view('child')['run_id']==row['run_id']
    assert store.latest('child') is None


def test_options_reject_zero_limits_and_unknown_providers():
    from backend.app.magic_models import MagicOptions
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        MagicOptions(max_cloud_requests=0)
    with pytest.raises(ValidationError):
        MagicOptions(providers=['unknown'])
