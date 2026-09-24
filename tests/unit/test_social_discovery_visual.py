import asyncio
from types import SimpleNamespace as NS

def test_social_discovery_removes_overlay_and_visual_duplicate(monkeypatch,tmp_path):
    from backend.app import quality_video as q
    class Cache:
        async def materialize_preview(self,c): return NS(path=tmp_path/c.provider_id,cache_hit=True)
    class Ranker:
        def rank(self,intent,rows):
            assert all(r['client_id']=='client' for r in rows)
            return [dict(r,score=.9 if r['id']=='tiktok:text' else .7, quality_reasons=['superimposed text evidence'] if r['id']=='tiktok:text' else []) for r in rows]
    monkeypatch.setattr(q,'perceptual_hash',lambda p:'0000000000000000' if p.name in {'a','b'} else 'ffffffffffffffff')
    rows=[NS(provider='tiktok',provider_id=i,title='airplane window',description='',query='airplane window',creator_name=i) for i in ['text','a','b']]
    engine=NS(cache=Cache(),ranker=Ranker())
    output={'rejected_candidates':[],'errors':[]}
    result=asyncio.run(q._rank_social_discovery(engine,rows,'airplane window',output,{},client_id='client'))
    assert [r.provider_id for r in result]==['a']
    assert len(output['rejected_candidates'])==2

def test_weak_thumbnail_gets_bounded_clip_review_not_final_rejection(monkeypatch,tmp_path):
    from backend.app import quality_video as q
    class Cache:
        async def materialize_preview(self,c):return NS(path=tmp_path/c.provider_id,cache_hit=True)
    class Ranker:
        def rank(self,intent,rows):
            return [dict(r,score=.29,embedding_score=.39,quality_state='rejected',quality_reasons=(['visual evidence below relevance floor','below relevance floor'] if not r['id'].endswith('bad') else ['actual frame matches talking-head vlog more than requested action'])) for r in rows]
    monkeypatch.setattr(q,'perceptual_hash',lambda p: (_ for _ in ()).throw(ValueError()))
    pool=[NS(provider='tiktok',provider_id=str(i),title='hotel room',description='',query='hotel room',creator_name=str(i),source_page='https://www.tiktok.com/@a/video/'+str(i)) for i in ['1','2','3','bad']]
    out={'errors':[],'rejected_candidates':[]}
    selected=asyncio.run(q._rank_social_discovery(NS(cache=Cache(),ranker=Ranker()),pool,'hotel room',out,{},client_id='c'))
    assert [r.provider_id for r in selected]==['1','2']
    assert len(out['thumbnail_review_candidates'])==2
    assert all(r['embedding_score']==.39 for r in out['social_thumbnail_ranking'])
