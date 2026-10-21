import asyncio
import pytest
from tests.unit.test_cut_pass_routes import tmp_path


def test_explicit_resend_only_repeats_delivery_and_preserves_budget(tmp_path):
    from backend.app.magic_runner import MagicRunner
    from backend.app.magic_store import MagicStore
    from backend.app.magic_models import MagicOptions
    calls=[]
    class Services:
        async def run_phase(self,phase,*args):
            calls.append(phase)
            return {'received':True} if phase=='delivery' else {}
    async def run():
        runner=MagicRunner(MagicStore(tmp_path),Services(),lambda _: 's')
        row=runner.start('p',MagicOptions());await runner.tasks[row['run_id']]
        journal=runner.store._path(row['run_id']).with_name('delivery.json')
        journal.write_text('{"package_id":"old"}')
        runner.resend(row['run_id']);await runner.tasks[row['run_id']]
        assert calls.count('delivery')==2
        assert calls.count('cut')==calls.count('preparation')==1
        assert not journal.exists()
        assert list(journal.parent.glob('delivery-history-*.json'))
        assert runner.store.read(row['run_id'])['calls']=={}
    asyncio.run(run())


def test_phases_complete_once_and_resume_reuses_checkpoints(tmp_path):
    from backend.app.magic_runner import MagicRunner, PHASES
    from backend.app.magic_store import MagicStore
    from backend.app.magic_models import MagicOptions
    calls = []
    class Services:
        async def run_phase(self, phase, context, options, report):
            calls.append(phase)
            report(1, 1, phase)
            if phase == 'cut': return {'output_project_id':'child','cut_revision':'r1'}
            return {'ready':True}
    async def run():
        runner = MagicRunner(MagicStore(tmp_path), Services(), lambda _: 'signature')
        state = runner.start('project', MagicOptions())
        await runner.tasks[state['run_id']]
        final = runner.store.read(state['run_id'])
        assert final['status'] == 'ready' and final['percent'] == 100
        assert final['output_project_id'] == 'child'
        assert calls == list(PHASES)
        assert runner.start('project', MagicOptions())['run_id'] == state['run_id']
        assert calls == list(PHASES)
    asyncio.run(run())


def test_workflow_revision_does_not_reuse_a_completed_legacy_run(tmp_path):
    from backend.app.magic_store import MagicStore
    from backend.app.magic_models import MagicOptions
    store = MagicStore(tmp_path)
    old = store.create_or_resume('project', 'signature', MagicOptions())
    old['options'].pop('workflow_revision')
    old['status'] = 'ready'
    store.transition(old['run_id'], options=old['options'], status='ready')
    fresh = store.create_or_resume('project', 'signature', MagicOptions())
    assert fresh['run_id'] != old['run_id']
    assert fresh['options']['workflow_revision'] == 'magic-v2'


def test_partial_warnings_survive_and_offline_delivery_can_resume(tmp_path):
    from backend.app.magic_runner import MagicRunner
    from backend.app.magic_store import MagicStore
    from backend.app.magic_models import MagicOptions
    calls=[]; online=[False]
    class Services:
        async def run_phase(self, phase, context, options, report):
            calls.append(phase)
            if phase=='research': return {'partial':True,'warnings':['one provider unavailable']}
            if phase=='delivery': return {'awaiting_bridge':not online[0], 'received':online[0]}
            return {}
    async def run():
        runner=MagicRunner(MagicStore(tmp_path),Services(),lambda _: 's')
        row=runner.start('p',MagicOptions());await runner.tasks[row['run_id']]
        final=runner.store.read(row['run_id'])
        assert final['status']=='partial' and final['warnings']==['one provider unavailable']
        assert 'bridge' in final['message'].lower()
        online[0]=True;runner.resume(row['run_id']);await runner.tasks[row['run_id']]
        assert calls.count('delivery')==2 and calls.count('research')==1
        assert runner.store.read(row['run_id'])['checkpoints']['delivery']['result']['received']
    asyncio.run(run())


def test_cancel_stops_next_phase_and_source_change_prevents_checkpoint(tmp_path):
    from backend.app.magic_runner import MagicRunner
    from backend.app.magic_store import MagicStore
    from backend.app.magic_models import MagicOptions
    async def run():
        release = asyncio.Event()
        calls = []
        signature = ['v1']
        class Services:
            async def run_phase(self, phase, context, options, report):
                calls.append(phase)
                await release.wait()
                return {}
        runner = MagicRunner(MagicStore(tmp_path), Services(), lambda _: signature[0])
        row = runner.start('project', MagicOptions())
        await asyncio.sleep(.01)
        runner.cancel(row['run_id']); release.set()
        await runner.tasks[row['run_id']]
        assert runner.store.read(row['run_id'])['status'] == 'cancelled'
        assert calls == ['cut']
        release.clear(); calls.clear()
        row = runner.start('other', MagicOptions())
        await asyncio.sleep(.01)
        signature[0] = 'v2'; release.set()
        await runner.tasks[row['run_id']]
        final = runner.store.read(row['run_id'])
        assert final['status'] == 'failed' and not final['checkpoints']
    asyncio.run(run())


def test_magic_failure_reports_diagnostics_without_changing_failure_state(tmp_path):
    from backend.app.magic_runner import MagicRunner
    from backend.app.magic_store import MagicStore
    from backend.app.magic_models import MagicOptions
    seen=[]
    class Services:
        async def run_phase(self,phase,*args):
            raise RuntimeError('private raw error')
    async def run():
        def capture(exc,**meta):seen.append((type(exc).__name__,meta))
        runner=MagicRunner(MagicStore(tmp_path),Services(),lambda _: 's',on_error=capture)
        row=runner.start('p',MagicOptions());await runner.tasks[row['run_id']]
        assert runner.store.read(row['run_id'])['status']=='failed'
        assert seen==[('RuntimeError',{'component':'magic','phase':'cut'})]
    asyncio.run(run())
