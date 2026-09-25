import asyncio,json
from types import SimpleNamespace as NS
import pytest
from backend.app import quality_video as q

@pytest.mark.parametrize('provider',['tiktok','instagram','youtube_shorts'])
def test_social_default_never_downloads_or_invokes_visual_ranker(monkeypatch,tmp_path,provider):
    from backend.app import funnel_runtime
    monkeypatch.delenv('RAMBLA_SOCIAL_SEARCH_OPTIONS',raising=False)
    source=NS(provider_name=provider)
    candidate=NS(provider=provider,provider_id='1',title='airplane window',description='airplane wing window',query='airplane window',source_page='https://example.com/1',preview_url='https://example.com/poster.jpg',width=720,height=1280,orientation='portrait',rights_state='unknown',creator_name='a')
    async def discover(engine,queries,expanded,*args):return {(id(source),query):([candidate],None,{}) for query in expanded}
    async def forbidden(*a,**kw):raise AssertionError('visual inference/download called')
    monkeypatch.setattr(funnel_runtime,'discover_shot',discover)
    monkeypatch.setattr(q,'_rank_social_discovery',forbidden)
    engine=NS(ranker=NS(),sources=[source],query_intents={},cache=NS(root=tmp_path,materialize_preview=forbidden))
    result=asyncio.run(q.source_video_beat(engine,beat_id='beat_1',client_id='c',queries=['airplane window'],min_duration=0,max_duration=60,orientation='portrait'))
    assert result['candidates']==[]
    assert len(result['discovery_sources'])==1
    assert not result['discovery_sources'][0].get('clip_verified')
    assert result['timings']['qwen_seconds']==0
    monkeypatch.setenv('RAMBLA_SOCIAL_SEARCH_OPTIONS',json.dumps({'visual_verify':True}))
    with pytest.raises(AssertionError,match='visual inference'):
        asyncio.run(q.source_video_beat(engine,beat_id='beat_1',client_id='c',queries=['airplane window'],min_duration=0,max_duration=60,orientation='portrait'))


def test_clean_only_target_beat(tmp_path):
    from backend.app.project_maintenance import clean_beat_media
    root=tmp_path/'editorial'/'plan';root.mkdir(parents=True)
    def save(name,data):(root/name).write_text(json.dumps(data),encoding='utf-8')
    save('online-candidates.json',[{'beat_id':'beat_1:shot:s1'},{'parent_beat_id':'beat_2','candidates':[{'id':'safe'}]}])
    save('image-candidates.json',{'chunks':{'beat_1':{'candidates':[1]},'beat_2':{'candidates':[2]}}})
    save('selection-plan.json',{'chunks':{'beat_1':{'selected_assets':[1]},'beat_2':{'selected_assets':[2]}}})
    save('imported-plan.json',{'keep':True})
    before=(root/'imported-plan.json').read_bytes()
    clean_beat_media(tmp_path,root,'beat_1')
    assert len(json.loads((root/'online-candidates.json').read_text()))==1
    assert json.loads((root/'image-candidates.json').read_text())['chunks']=={'beat_2':{'candidates':[2]}}
    assert json.loads((root/'selection-plan.json').read_text())['chunks']=={'beat_1':{'selected_assets':[]},'beat_2':{'selected_assets':[2]}}
    assert (root/'imported-plan.json').read_bytes()==before
