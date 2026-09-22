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
    assert len(rows)<=6
    assert any('wilting basil' in q for q in rows)
    assert all('basil' in q and any(w in q for w in ('wilt','droop','dying')) for q in rows)
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


def test_borderline_matching_candidate_requires_review():
    from backend.app.retrieval_quality import QualityRanker
    class Ranker:
        def rank(self,q,rows):return [dict(r,embedding_score=.51 if 'wilted' in q else .40) for r in rows]
    row=QualityRanker(Ranker()).rank('wilted basil plant',[{'id':'weak','description':'wilted basil plant'}])[0]
    assert row['quality_state']=='needs_review'


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
    assert len(result['candidates'])==int(playable)
    row=(result['candidates'] if playable else result['discovery_sources'])[0]
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
    from contextlib import contextmanager
    @contextmanager
    def bridge(url):
        downloads.append(url);yield "http://127.0.0.1:12345/media"
    monkeypatch.setattr(module,"range_media",bridge)
    module._youtube_url.cache_clear()
    def run(cmd,**kw):commands.append(cmd);return NS(stdout=json.dumps({'url':'https://media.example/video-only'}))
    monkeypatch.setattr(module.subprocess,'run',run)
    monkeypatch.setattr(module,'download_preview_proxy',lambda url,folder,identity:downloads.append(url) or folder/'proxy.mp4',raising=False)
    monkeypatch.setattr(module,'materialize_clip',lambda source,folder,identity,**kw:cuts.append((source,kw)) or {'preview_path':'clip.mp4','preview_duration':3.5,'source_start_seconds':kw.get('start_seconds',0),'source_end_seconds':kw.get('start_seconds',0)+3.5})
    clip=module._youtube_clip('https://youtube.com/watch?v=id',tmp_path,'youtube:id',7)
    assert downloads==['https://media.example/video-only']
    assert cuts[0][0]=='http://127.0.0.1:12345/media' and cuts[0][1]['start_seconds']==7
    assert cuts[0][1]['streaming'] is True
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


def test_video_discovery_rejects_single_generic_noun_match():
    from types import SimpleNamespace as NS
    from backend.app.quality_video import _discovery_relevant

    good = NS(
        provider="youtube_shorts",
        query="small passenger ferry with luggage",
        title="Passengers board island ferry carrying luggage",
        description="Travelers boarding a ferry with bags",
        orientation="portrait",
        source_authenticity=.94,
        provider_rank=0,
    )
    bad = NS(
        provider="youtube_shorts",
        query="small passenger ferry with luggage",
        title="Huge wave shatters ferry window during storm",
        description="Storm damages ferry window in Germany",
        orientation="portrait",
        source_authenticity=.94,
        provider_rank=1,
    )

    intent = "Small passenger ferry crossing water with travelers holding luggage"
    assert _discovery_relevant(good, intent) is True
    assert _discovery_relevant(bad, intent) is False


def test_video_discovery_pool_reserves_normal_youtube_among_vertical_results():
    from types import SimpleNamespace as NS
    from backend.app.quality_video import _balanced_discovery_pool

    def row(provider, pid, title, rank=0):
        return NS(
            provider=provider,
            provider_id=pid,
            query="airport shuttle bus departing",
            title=title,
            description=title,
            orientation="portrait" if provider != "youtube" else "landscape",
            source_authenticity=.94,
            provider_rank=rank,
        )

    pool = [
        row("youtube_shorts", "s1", "Airport shuttle bus departing terminal"),
        row("youtube_shorts", "s2", "Airport shuttle bus at terminal", 1),
        row("tiktok", "t1", "Airport shuttle bus departing", 0),
        row("instagram", "i1", "Airport shuttle bus departure", 0),
        row("youtube", "y1", "Airport shuttle bus departing with luggage", 0),
    ]

    selected = _balanced_discovery_pool(pool, "Airport shuttle bus departing with luggage", limit=4)
    providers = [item.provider for item in selected]
    assert "youtube" in providers
    assert len(set(providers)) >= 3


def test_imported_queries_do_not_append_broad_contextual_topic_fallbacks():
    from backend.app.editorial_relevance import build_retrieval_spec

    beat = {
        "core_meaning": "Accept compromises and reduce harm",
        "subtext": "Sustainable travel is imperfect",
        "original_text": "Significa capire su quali cose è possibile accettare il compromesso.",
        "avoid": [],
    }
    shot = {
        "shot_id": "s1",
        "description": "Traveler boarding a local bus with a backpack",
        "image_queries": ["traveler boarding local bus"],
        "video_queries": ["traveler boarding local bus"],
    }

    spec = build_retrieval_spec(beat, shot, "video")
    assert spec["queries"] == ["traveler boarding local bus"]
    assert "greenwashing tourism" not in spec["queries"]
    assert spec["visual_target"] == "Traveler boarding a local bus with a backpack"


def test_quality_ranker_uses_concrete_visual_target_not_full_editorial_argument():
    from backend.app.editorial_relevance import INTENT_PREFIX
    from backend.app.retrieval_quality import QualityRanker

    seen = []

    class Visual:
        def rank(self, query, rows):
            seen.append(query)
            return [dict(row, embedding_score=.75) for row in rows]

    intent = INTENT_PREFIX + json.dumps({
        "positive": "Abstract argument about sustainability and compromise",
        "visual_target": "traveler boarding local bus with backpack",
        "context": "long abstract spoken context",
        "negatives": [],
        "generic_shot_demoted": False,
        "shot_id": "s1",
    })
    rows = QualityRanker(Visual()).rank(intent, [{
        "id": "x",
        "description": "traveler boarding local bus with backpack",
        "query": "traveler boarding local bus",
        "kind": "video",
    }])

    assert seen[0] == "traveler boarding local bus with backpack"
    assert rows[0]["visual_target"] == "traveler boarding local bus with backpack"
    assert rows[0]["editorial_positive"] == "Abstract argument about sustainability and compromise"


def test_storyboard_sampling_is_bounded_and_spans_video():
    from backend.app.quality_video import _storyboard_sample_indices

    rows = _storyboard_sample_indices(500, 10)
    assert len(rows) == 10
    assert rows == sorted(set(rows))
    assert rows[0] > 0
    assert rows[-1] < 499
    assert rows[-1] - rows[0] > 350


def test_storyboard_locator_rejects_talking_head_and_prefers_clean_visual_match():
    from backend.app.quality_video import _choose_storyboard_starts

    samples = [
        {"index": 10, "timestamp": 20.0},
        {"index": 20, "timestamp": 40.0},
        {"index": 30, "timestamp": 60.0},
    ]
    positive = {"10": .72, "20": .66, "30": .62}
    talking = {"10": .30, "20": .70, "30": .28}
    text = {"10": .25, "20": .22, "30": .68}

    starts = _choose_storyboard_starts(
        samples, positive, talking, text, duration=90.0, limit=2
    )

    assert starts == [18.8]


def test_stale_query_is_rejected_against_concrete_visual_target():
    from backend.app.quality_video import _query_matches_target, _query_from_target

    target = "A local language map pin or hand pointing at a small-town sign in a market alley."
    assert _query_matches_target("free range chickens garden", target) is False
    assert _query_matches_target("hand pointing at town sign", target) is True
    repaired = _query_from_target(target)
    assert "map" in repaired and "sign" in repaired


@pytest.mark.asyncio
async def test_valid_storyboard_with_no_matching_scene_returns_empty_not_fallback(tmp_path, monkeypatch):
    from types import SimpleNamespace as NS
    from backend.app import quality_video as module

    monkeypatch.setattr(
        module,
        "_youtube_storyboard_frames",
        lambda *_args, **_kwargs: [
            {"path": str(tmp_path / "a.jpg"), "timestamp": 10.0, "index": 1},
            {"path": str(tmp_path / "b.jpg"), "timestamp": 20.0, "index": 2},
        ],
    )

    class Visual:
        def rank(self, _query, rows):
            return [{**row, "embedding_score": .20} for row in rows]

    engine = NS(ranker=NS(visual=Visual()))
    candidate = NS(
        provider="youtube",
        duration=120,
        query="elephant sanctuary entrance",
        source_page="https://youtube.com/watch?v=x",
    )

    result = await module._storyboard_starts(
        engine, candidate, "elephant sanctuary entrance",
        tmp_path, "youtube:x", "client", lambda *_args, **_kwargs: None,
    )
    assert result == []
