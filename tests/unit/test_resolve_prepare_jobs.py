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

def test_cancel_keeps_completed_cache_and_allows_retry(tmp_path):
    async def scenario():
        jobs=ResolvePrepareJobs();assert hasattr(jobs,'cancel');ready=asyncio.Event(); new=tmp_path/'new.mp4';old=tmp_path/'old.mp4';old.write_bytes(b'old')
        async def runner(report):
            report.track_cache_file(new);report.track_cache_file(old)
            new.write_bytes(b'new');ready.set();await asyncio.Event().wait()
        row=jobs.start('p',runner);await ready.wait()
        result=await jobs.cancel(row['job_id'],keep_cached=True)
        assert result['status']=='cancelled' and new.is_file() and old.is_file()
        next_job=jobs.start('p',lambda report: asyncio.sleep(0,result={'package_id':'p'}))
        assert next_job['job_id']!=row['job_id'];await jobs.tasks[next_job['job_id']]
    asyncio.run(scenario())


def test_cancel_discards_only_new_cache_files(tmp_path):
    async def scenario():
        jobs=ResolvePrepareJobs();assert hasattr(jobs,'cancel');ready=asyncio.Event();new=tmp_path/'new.mp4';old=tmp_path/'old.mp4';old.write_bytes(b'old')
        async def runner(report):
            report.track_cache_file(new);report.track_cache_file(old)
            new.write_bytes(b'new');ready.set();await asyncio.Event().wait()
        row=jobs.start('p',runner);await ready.wait()
        result=await jobs.cancel(row['job_id'],keep_cached=False)
        assert result['status']=='cancelled' and not new.exists() and old.read_bytes()==b'old'
    asyncio.run(scenario())


def test_stop_control_has_safe_choices():
    from backend.app.timeline_export_ui import PANEL,JS
    assert 'STOP INVIO' in PANEL and 'MANTIENI I FILE' in PANEL and 'ELIMINA I NUOVI FILE' in PANEL
    assert '/cancel' in JS and 'keep_cached' in JS

def test_user_can_choose_retry_or_ignore_after_media_error():
    async def scenario():
        jobs=ResolvePrepareJobs()
        async def runner(report):
            choice=await report.issue({'asset_id':'asset-1','provider':'envato','message':'Non risponde'})
            return {'choice':choice}
        row=jobs.start('p',runner)
        for _ in range(20):
            await asyncio.sleep(0)
            if jobs.status(row['job_id'])['status']=='waiting_user':break
        assert jobs.status(row['job_id'])['issue']['asset_id']=='asset-1'
        jobs.decide(row['job_id'],'retry')
        task=jobs.tasks[row['job_id']];await task
        assert jobs.status(row['job_id'])['package']['choice']=='retry'
    asyncio.run(scenario())


def test_cancel_immediately_after_start_does_not_get_stuck():
    async def scenario():
        jobs=ResolvePrepareJobs()
        async def runner(report):await asyncio.Event().wait()
        row=jobs.start('p',runner)
        result=await jobs.cancel(row['job_id'],keep_cached=True)
        assert result['status']=='cancelled'
        assert not jobs.tasks
    asyncio.run(scenario())

def test_discard_envato_new_cache_keeps_prior_assets(tmp_path):
    import json
    async def scenario():
        jobs=ResolvePrepareJobs();ready=asyncio.Event();root=tmp_path/'envato-media'/'abc';root.mkdir(parents=True)
        old=root/'old.mp4';old.write_bytes(b'old');new=root/'original.mp4';registry=tmp_path/'envato-downloads.json'
        registry.write_text(json.dumps({'assets':{'old':{'media_path':str(old)}}}))
        async def runner(report):
            report.track_envato_cache(root,registry,'new')
            new.write_bytes(b'new');registry.write_text(json.dumps({'assets':{'old':{'media_path':str(old)},'new':{'media_path':str(new)}}}))
            ready.set();await asyncio.Event().wait()
        row=jobs.start('p',runner);await ready.wait()
        assert (await jobs.cancel(row['job_id'],keep_cached=False))['status']=='cancelled'
        assert old.is_file() and not new.exists()
        assert set(json.loads(registry.read_text())['assets'])=={'old'}
    asyncio.run(scenario())

def test_ignore_all_skips_following_problems_in_same_job():
    async def scenario():
        jobs=ResolvePrepareJobs()
        async def runner(report):
            first=await report.issue({'asset_id':'a'});second=await report.issue({'asset_id':'b'})
            return {'choices':[first,second]}
        row=jobs.start('p',runner)
        for _ in range(20):
            await asyncio.sleep(0)
            if jobs.status(row['job_id'])['status']=='waiting_user':break
        jobs.decide(row['job_id'],'ignore_all');task=jobs.tasks[row['job_id']];await task
        assert jobs.status(row['job_id'])['package']['choices']==['ignore','ignore']
    asyncio.run(scenario())
