import asyncio
import pytest
from tests.unit.test_cut_pass_routes import tmp_path


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
