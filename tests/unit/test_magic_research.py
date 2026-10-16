import asyncio
from tests.unit.test_cut_pass_routes import tmp_path


def test_research_is_bounded_resumable_and_provider_failures_are_independent(tmp_path):
    from backend.app.magic_research import research_beats
    from backend.app.magic_models import MagicOptions
    calls=[]
    async def research(beat,provider,query):
        calls.append((beat,provider,query))
        if provider=='youtube_shorts': raise RuntimeError('CAPTCHA: open https://youtube.com/watch?v=1')
        return {'status':'complete'}
    beats=[dict(id='b',text='tourist police Egypt',queries=['tourist police','officers','police'],places=['Egypt'])]
    options=MagicOptions(providers=['pexels','youtube_shorts'],queries_per_provider=2)
    first=asyncio.run(research_beats(beats,options,tmp_path,research,lambda *a:None))
    assert [p for _,p,_ in calls]==['pexels','pexels','youtube_shorts']
    assert first['partial'] and first['warnings']
    assert all('Egypt' in q for _,_,q in calls)
    asyncio.run(research_beats(beats,options,tmp_path,research,lambda *a:None))
    assert len(calls)==3  # no automatic CAPTCHA retries or repeated searches
