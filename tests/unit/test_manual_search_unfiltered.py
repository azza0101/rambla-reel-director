import asyncio
import json
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize('provider', ['youtube_shorts', 'tiktok', 'instagram', 'pexels', 'youtube', 'web_video'])
def test_manual_video_search_does_not_apply_editorial_verification(monkeypatch, provider):
    from backend.app.envato_source import EnvatoRemoteCandidate
    from backend.app import quality_video
    query='livno bosnia duman'
    c=EnvatoRemoteCandidate(provider=provider,provider_id='id1',query=query,
        source_page='https://example.com/video',creator_name=None,creator_page=None,
        title='A different title',description='A different title',duration=20,width=640,height=360,
        orientation='landscape',preview_url='https://example.com/image.jpg',
        selected_rendition_url='https://example.com/video',rendition_width=640,rendition_height=360,
        rights_state='review_required',provider_rank=0)
    sent=[]
    async def search(source,text,**kwargs): sent.append(text); return [c],None
    async def reject(*args, **kwargs): raise AssertionError('Manual search must not run editorial ranking')
    monkeypatch.setattr(quality_video,'_rank_social_discovery',reject)
    monkeypatch.setenv('RAMBLA_SOCIAL_SEARCH_OPTIONS',json.dumps({'query_overrides':{'*':query},'visual_verify':True}))
    engine=SimpleNamespace(sources=[SimpleNamespace(provider_name=provider)],query_intents={},
        _search_one=search,ranker=SimpleNamespace(),beat_context={})
    result=asyncio.run(quality_video.source_video_beat(engine,beat_id='b:shot:s1',client_id='test',
        queries=['old'],min_duration=1,max_duration=180,orientation=None,retrieval_intent='old'))
    assert sent==[query]
    assert any(row['provider_id']=='id1' for row in result['discovery_sources'])


def test_manual_images_bypass_editorial_ranking(monkeypatch, tmp_path):
    from backend.app import quality_images
    from backend.app.image_sources import RemoteImageCandidate
    query='livno bosnia duman'; sent=[]
    class Source:
        provider_name='wikimedia'
        async def search(self, text, *, limit):
            sent.append(text)
            return [RemoteImageCandidate('wikimedia','one',text,'https://example.com/1','Other title','',
                'https://example.com/1.jpg','https://example.com/full.jpg',1200,800,'landscape','review_required',0)]
    class Ranker:
        visual=None
        def rank(self, *args): raise AssertionError('Manual images should not be filtered by editorial ranking')
    async def fetch(url): return b'image'
    monkeypatch.setattr(quality_images,'image_quality',lambda path:{})
    monkeypatch.setattr(quality_images,'other_media_history',lambda *args:[])
    monkeypatch.setattr(quality_images,'provider_status',lambda:{})
    monkeypatch.setattr(quality_images,'build_retrieval_spec',lambda *args:{'queries':['original'],'positive':'other','negatives':[],'generic_shot_demoted':False})
    monkeypatch.setattr(quality_images,'encode_retrieval_intent',lambda *args:'original')
    monkeypatch.setenv('RAMBLA_SOCIAL_SEARCH_OPTIONS',json.dumps({'query_overrides':{'*':query}}))
    plan={'chunks':{'b':{'visual_action':'BROLL','shots':[{'shot_id':'s1','description':'old','image_queries':['original']}]}}}
    result=asyncio.run(quality_images.source_images([{'id':'b'}],tmp_path,plan,Ranker(),'test',sources=[Source()],fetcher=fetch))
    assert sent==[query]
    assert [r['provider_id'] for r in result['chunks']['b']['candidates']]==['one']
