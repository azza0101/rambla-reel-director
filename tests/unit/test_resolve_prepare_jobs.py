import asyncio
from backend.app.resolve_prepare_jobs import ResolvePrepareJobs


def test_progress_duplicate_click_and_result():
    async def scenario():
        jobs=ResolvePrepareJobs(); gate=asyncio.Event()
        async def runner(report):
            report(25,'Video 1/3'); await gate.wait(); report(80,'Pacchetto'); return {'package_id':'p'}
        first=jobs.start('project',runner)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert jobs.status(first['job_id'])['percent']==25
        assert jobs.start('project',runner)['job_id']==first['job_id']
        task=jobs.tasks[first['job_id']]; gate.set(); await task
        final=jobs.status(first['job_id']);assert final['status']=='ready' and final['package']['package_id']=='p'
    asyncio.run(scenario())


def test_failure_is_visible_and_retry_is_allowed():
    async def scenario():
        jobs=ResolvePrepareJobs()
        async def fail(report):raise ValueError('Pexels download failed')
        row=jobs.start('p',fail);await jobs.tasks[row['job_id']]
        assert jobs.status(row['job_id'])['message']=='Pexels download failed'
        retry=jobs.start('p',fail);assert retry['job_id']!=row['job_id'];await jobs.tasks[retry['job_id']]
    asyncio.run(scenario())

def test_media_progress_is_exposed_and_cleared_when_preparation_finishes():
    async def scenario():
        jobs=ResolvePrepareJobs(); gate=asyncio.Event()
        async def runner(report):
            report.media({'asset_id':'asset-1', 'title':'Video', 'received':5, 'total':10, 'phase':'download'})
            await gate.wait()
            report.media(None)
            return {'package_id':'p'}
        row=jobs.start('project',runner)
        await asyncio.sleep(0); await asyncio.sleep(0)
        media=jobs.status(row['job_id'])['media']
        assert media['received']==5 and media['total']==10
        task=jobs.tasks[row['job_id']];gate.set();await task
        assert jobs.status(row['job_id'])['media'] is None
    asyncio.run(scenario())
