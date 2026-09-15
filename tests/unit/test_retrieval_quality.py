import json
import pytest


def test_project_credentials_are_loaded_without_overwriting_environment(tmp_path,monkeypatch):
    from backend.app.project_config import load_project_credentials, provider_status
    (tmp_path/'.env.local').write_text('PEXELS_API_KEY=test-local-secret\nUNRELATED=not-loaded\n',encoding='utf-8')
    monkeypatch.delenv('PEXELS_API_KEY',raising=False)
    load_project_credentials(tmp_path)
    assert provider_status()['pexels_configured'] is True
    assert 'test-local-secret' not in json.dumps(provider_status())
    monkeypatch.setenv('PEXELS_API_KEY','process-value')
    load_project_credentials(tmp_path)
    import os
    assert os.environ['PEXELS_API_KEY']=='process-value'
    assert os.environ.get('UNRELATED') is None


def test_expansion_preserves_required_subject_and_condition():
    from backend.app.retrieval_quality import expand_queries
    rows=expand_queries(['wilted basil plant in a small pot'],'image')
    assert len(rows)<=4
    assert any('wilting basil' in q for q in rows)
    assert all('basil' in q and any(w in q for w in ('wilt','droop')) for q in rows)
    assert all('travel' not in q for q in rows)


def test_ranker_rejects_generic_and_condition_mismatch_without_model():
    from backend.app.retrieval_quality import QualityRanker
    ranker=QualityRanker()
    rows=ranker.rank('wilted basil plant',[
        {'id':'good','description':'Wilting basil plant with drooping leaves'},
        {'id':'healthy','description':'Healthy fresh basil plant'},
        {'id':'vlog','description':'My amazing travel vlog in Italy'},
    ])
    by_id={r['id']:r for r in rows}
    assert by_id['good']['score'] > by_id['healthy']['score']
    assert by_id['healthy']['quality_state']=='rejected'
    assert by_id['vlog']['quality_state']=='rejected'
    assert by_id['good']['embedding_score'] is None


def test_visual_score_cannot_override_explicit_wrong_condition():
    from backend.app.retrieval_quality import QualityRanker
    class Ranker:
        def rank(self,q,rows):return [dict(r,score=.8,embedding_score=.8) for r in rows]
    row=QualityRanker(Ranker()).rank('wilted basil plant',[{'id':'bad','description':'Healthy green basil plant'}])[0]
    assert row['quality_state']=='rejected'


def test_matching_metadata_cannot_rescue_weak_visual_evidence():
    from backend.app.retrieval_quality import QualityRanker
    class Ranker:
        def rank(self,q,rows):return [dict(r,embedding_score=.51) for r in rows]
    row=QualityRanker(Ranker()).rank('wilted basil plant',[{'id':'weak','description':'wilted basil plant'}])[0]
    assert row['quality_state']=='rejected'


def test_separate_video_shelves_keep_three_each_and_pending_not_final():
    from backend.app.curation import CurationCandidate,build_candidate_shelf
    rows=[CurationCandidate(str(i),'b','video',p,f'https://example.com/{i}','title','text',.8,'review_required','landscape',preview_status='ready',source_start_seconds=3,source_end_seconds=6.5) for i,p in enumerate(['youtube']*3+['pexels']*3)]
    shelf=build_candidate_shelf(rows)
    assert len(shelf.social)==3 and len(shelf.stock)==3


def test_preview_hash_and_range_are_clip_specific(tmp_path,monkeypatch):
    from backend.app import video_preview
    calls=[]
    monkeypatch.setattr(video_preview,'download_preview_proxy',lambda source,directory,identity:directory/'local-proxy.mp4')
    def runner(command,**kwargs):
        calls.append(command)
        from pathlib import Path
        Path(command[-1]).write_bytes(b'media')
    monkeypatch.setattr(video_preview.subprocess,'run',runner)
    monkeypatch.setattr(video_preview,'probe_preview',lambda p:{'playable':bool(p and __import__('pathlib').Path(p).exists()),'duration':3.5,'mime':'video/mp4'})
    a=video_preview.materialize_clip('https://example.com/video.mp4',tmp_path,'id',start_seconds=2)
    b=video_preview.materialize_clip('https://example.com/video.mp4',tmp_path,'id',start_seconds=8)
    assert a['preview_path']!=b['preview_path']
    assert b['source_start_seconds']==8 and b['source_end_seconds']==11.5
    assert any('-ss' in c and '8' in c for c in calls)


@pytest.mark.asyncio
async def test_photo_primary_expands_before_fallback_and_never_uses_video_queries(tmp_path,monkeypatch):
    from backend.app import quality_images as module
    from backend.app.image_sources import RemoteImageCandidate
    from backend.app.retrieval_quality import QualityRanker
    calls=[]
    class Primary:
        async def search(self,q,limit):
            calls.append(('primary',q))
            if 'wilting' not in q:return []
            return [RemoteImageCandidate('pexels',str(i),q,f'https://example.com/{i}','Wilting basil plant with drooping leaves','',f'https://example.com/{i}.jpg','',1200,800,'landscape','review_required',i) for i in range(2)]
    class Fallback:
        async def search(self,q,limit):calls.append(('fallback',q));return []
    async def fetch(url):return b'image'
    monkeypatch.setattr(module,'image_quality',lambda p:{'content_sha256':p.name})
    plan={'chunks':{'b':{'visual_action':'BROLL','shots':[{'shot_id':'s','description':'Wilted basil plant','image_queries':['wilted basil plant'],'video_queries':['unrelated video query']}]}}}
    result=await module.source_images([{'id':'b'}],tmp_path,plan,QualityRanker(),'p',sources=[Primary(),Fallback()],fetcher=fetch)
    assert len(result['chunks']['b']['candidates'])==2
    assert all(provider=='primary' and 'video' not in q for provider,q in calls)
    assert result['chunks']['b']['search_attempts'][-1]['expanded']


def test_pending_video_cannot_be_selected(tmp_path):
    from backend.app.curation_selection import SelectionStore
    store=SelectionStore(tmp_path,{'v':{'chunk_id':'b','selectable':False}},['b'])
    with pytest.raises(ValueError,match='preview pending'):
        store.set_chunk_selection('b',['v'],no_broll=False)


def test_old_imported_retrieval_is_flagged_and_hidden(tmp_path):
    from tests.unit.test_editorial_import import fixture
    from backend.app.editorial_import import import_plan,retrieval_bundle
    from backend.app.curation_artifacts import load_curation_run
    package,plan=fixture(tmp_path);import_plan(tmp_path,plan,package)
    root,*_=retrieval_bundle(tmp_path)
    (root/'image-candidates.json').write_text(json.dumps({'chunks':{'vb-1':{'candidates':[{'id':'old'}]}}}),encoding='utf-8')
    result=load_curation_run(tmp_path)
    assert not result.candidate_index
    assert any('rerun' in e.lower() for e in result.errors)


def test_embedding_runtime_uses_bounded_local_inference(monkeypatch,tmp_path):
    import sys,types
    from backend.app import qwen_stack as module
    captured={}
    monkeypatch.setitem(sys.modules,'torch',types.SimpleNamespace(bfloat16='bf16',float32='fp32',cuda=types.SimpleNamespace(is_available=lambda:True)))
    monkeypatch.setattr(module.importlib,'import_module',lambda name:types.SimpleNamespace(Qwen3VLEmbedder=lambda **kw:captured.update(kw)))
    config=module.QwenConfig(model_root=tmp_path)
    module._load_official_qwen_vl_embedder(tmp_path,config)
    assert captured['dtype']=='bf16'
    assert captured['max_pixels']<=512*32*32
    assert captured['local_files_only'] is True


@pytest.mark.asyncio
@pytest.mark.parametrize('playable',[True,False])
async def test_video_ranks_clip_frames_against_own_shot_not_shared_query(tmp_path,monkeypatch,playable):
    from types import SimpleNamespace as NS
    from backend.app import quality_video as module
    ranked=[]
    own='Hands slicing tomatoes on a cutting board'
    candidate=NS(provider='pexels',provider_id='1',query='shared query',source_page='https://example.com/1',
        title=own,description=own,width=1280,height=720,orientation='landscape',rights_state='review_required',
        creator_name='Author',duration=8,preview_rendition_url='https://example.com/proxy.mp4',selected_rendition_url='',)
    async def search(*a,**kw):return [candidate],None
    async def poster(*a):return NS(path=tmp_path/'poster.jpg',cache_hit=False)
    def materialize(*a,**kw):
        if not playable:raise ValueError('unavailable')
        return {'preview_path':str(tmp_path/'clip.mp4'),'source_start_seconds':2.,'source_end_seconds':5.5}
    def rank(q,rows):
        ranked.append((q,rows))
        return [dict(r,score=.8,embedding_score=.8,quality_state='accepted') for r in rows]
    engine=NS(sources=[NS()],_search_one=search,query_intents={'shared query':'wrong other beat'},cache=NS(materialize_preview=poster),ranker=NS(rank=rank))
    monkeypatch.setattr(module,'materialize_clip',materialize)
    monkeypatch.setattr(module,'_frame_samples',lambda _:['frame-one.jpg','frame-two.jpg'])
    monkeypatch.setattr(module,'perceptual_hash',lambda _:'1234')
    result=await module.source_video_beat(engine,beat_id='b',client_id='p',queries=['shared query'],min_duration=1,max_duration=60,orientation=None,retrieval_intent=own)
    assert len(result['candidates'])==1
    row=result['candidates'][0]
    assert row['clip_verified'] is playable
    if playable:
        assert ranked[0][0]==own
        assert [r['keyframe_path'] for r in ranked[0][1]]==['frame-one.jpg','frame-two.jpg']
        assert row['source_start_seconds']==2
    else:
        assert not ranked
        assert row['preview_status']=='preview_pending'
        assert row['source_start_seconds'] is None


def test_youtube_uses_video_only_bounded_proxy_and_local_cut(tmp_path,monkeypatch):
    from types import SimpleNamespace as NS
    from backend.app import quality_video as module
    commands=[];downloads=[];cuts=[]
    def run(cmd,**kw):commands.append(cmd);return NS(stdout=json.dumps({'url':'https://media.example/video-only'}))
    monkeypatch.setattr(module.subprocess,'run',run)
    monkeypatch.setattr(module,'download_preview_proxy',lambda url,folder,identity:downloads.append(url) or folder/'proxy.mp4',raising=False)
    monkeypatch.setattr(module,'materialize_clip',lambda source,folder,identity,**kw:cuts.append((source,kw)) or {'preview_path':'clip.mp4','preview_duration':3.5,'source_start_seconds':kw.get('start_seconds',0),'source_end_seconds':kw.get('start_seconds',0)+3.5})
    clip=module._youtube_clip('https://youtube.com/watch?v=id',tmp_path,'youtube:id',7)
    assert downloads==['https://media.example/video-only']
    assert cuts[0][0].endswith('proxy.mp4') and cuts[0][1]['start_seconds']==7
    assert '--skip-download' in commands[0]
    assert 'bv*' in commands[0][commands[0].index('-f')+1]
    assert clip['source_end_seconds']==10.5


def test_proxy_has_wall_time_bound_and_removes_partial_file(tmp_path,monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace as NS
    from backend.app import video_preview as module
    import httpx
    @contextmanager
    def stream(*a,**kw):yield NS(headers={},raise_for_status=lambda:None,iter_bytes=lambda:iter([b'bytes']))
    monkeypatch.setattr(httpx,'stream',stream)
    ticks=iter([0,100])
    monkeypatch.setattr(module,'time',NS(monotonic=lambda:next(ticks)),raising=False)
    with pytest.raises(TimeoutError):module.download_preview_proxy('https://example.com/video',tmp_path,'id',max_seconds=30)
    assert not list(tmp_path.iterdir())
