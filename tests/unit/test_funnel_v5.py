import asyncio
import json
from types import SimpleNamespace


def test_official_envato_mcp_response_is_discovery_only():
    from backend.app.envato_source import parse_mcp_result
    envelope = {'result': {'content': [{'type': 'text', 'text': json.dumps({'items': [
        {'title': 'Passenger ferry', 'item_url': 'https://elements.envato.com/passenger-ferry-ABC1234', 'cover_image': 'https://assets.example/ferry.jpg'}
    ]})}]}}
    rows = parse_mcp_result('event: message\ndata: ' + json.dumps(envelope) + '\n\n')
    assert rows[0]['source_page'].endswith('ABC1234')
    assert rows[0]['preview_url'].endswith('.jpg')


def test_proposals_only_verified_clips_and_review_state():
    from backend.app.quality_video import synchronize_proposals
    row = {'candidates': [{'id': 'yes', 'clip_verified': True}, {'id': 'no', 'clip_verified': False}]}
    synchronize_proposals(row)
    assert row['proposals']['proposal_A']['id'] == 'yes'
    assert row['proposals']['proposal_B'] is None
    assert row['proposals']['review_state'] == 'NEEDS_REVIEW'
    row['candidates'] = []
    synchronize_proposals(row)
    assert row['proposals']['review_state'] == 'NO_VISUAL_FOUND'


def test_persistent_cache_ttl_and_version():
    from pathlib import Path
    import uuid
    tmp_path = Path('.funnel-tests') / uuid.uuid4().hex
    from backend.app.funnel_cache import JsonCache
    cache = JsonCache(tmp_path, 'v1')
    cache.put('query', {'hits': 2})
    assert JsonCache(tmp_path, 'v1').get('query', 60) == {'hits': 2}
    assert cache.get('query', -1) is None
    assert JsonCache(tmp_path, 'v2').get('query', 60) is None


def test_stale_query_map_sign():
    from backend.app.quality_video import _query_matches_target, _query_from_target
    assert not _query_matches_target('chickens vegetable garden', 'map pin / town sign')
    assert _query_from_target('map pin / town sign') == 'map pin town sign'


def test_first_coverage_budget_is_one():
    from backend.app.quality_video import PRIMARY_CLIPS_PER_SHOT
    assert PRIMARY_CLIPS_PER_SHOT == 1


def test_envato_zero_has_explicit_diagnostic():
    from backend.app.envato_source import EnvatoSource
    source = EnvatoSource(discover=lambda *args: [])
    assert asyncio.run(source.search('ferry', orientation=None, min_duration=1, max_duration=60, limit=3)) == []
    assert source.last_attempt['raw_items'] == 0
    assert source.last_attempt['parsed_items'] == 0
    assert source.last_attempt['valid_items'] == 0
    assert source.last_attempt['parser']


def test_moving_target_rejects_stationary_result_before_download():
    from backend.app.quality_video import _discovery_relevant
    candidate=SimpleNamespace(provider='pexels',query='small ferry crossing water',
        title='A ferry is docked in the water with cars',description='A docked ferry')
    assert not _discovery_relevant(candidate,'A small passenger ferry cutting through water')


def test_diegetic_sign_is_not_generic_overlay():
    from backend.app.retrieval_quality import metadata_quality
    assert not metadata_quality('town sign beside road','a real town sign beside the road')[3]
    assert metadata_quality('bus departing','tutorial with text overlay')[3]


def test_repeated_shot_uses_cache_and_changed_intent_invalidates(tmp_path, monkeypatch):
    from backend.app import quality_video
    from backend.app.funnel_runtime import cached_source_video_beat
    calls=[]
    async def source(engine,**kwargs):
        calls.append(kwargs)
        return {'candidates':[], 'errors':[], 'search_attempts':[{'provider':'envato','hits':0}],
                'timings':{'total_seconds':1},'provider_counts':{'envato':{'requests':1}}}
    monkeypatch.setattr(quality_video,'source_video_beat',source)
    def engine():return SimpleNamespace(cache=SimpleNamespace(root=tmp_path),sources=[])
    async def run():
        await cached_source_video_beat(engine(),beat_id='b',retrieval_intent='bus')
        cached=await cached_source_video_beat(engine(),beat_id='b',retrieval_intent='bus')
        assert cached['cache_hit']
        assert cached['provider_counts']['envato']['requests']==0
        await cached_source_video_beat(engine(),beat_id='b',retrieval_intent='ferry')
    asyncio.run(run())
    assert len(calls)==2


def test_storyboard_no_match_never_downloads(tmp_path,monkeypatch):
    from backend.app import quality_video as m
    source=SimpleNamespace(provider_name='youtube')
    candidate=SimpleNamespace(provider='youtube',provider_id='x',query='bus departing',
        title='Bus departing',description='Bus departing',source_page='https://youtube.com/watch?v=x',
        orientation='landscape',provider_rank=0,width=1280,height=720,rights_state='review_required',
        creator_name=None,duration=120,preview_url='https://example.com/bus.jpg')
    async def search(*a,**kw):return [candidate],None
    async def poster(*a):return SimpleNamespace(path=tmp_path/'bus.jpg',cache_hit=False)
    async def no_match(*a,**kw):return []
    monkeypatch.setattr(m,'_storyboard_starts',no_match)
    monkeypatch.setattr(m,'_social_clip',lambda *a: (_ for _ in ()).throw(AssertionError('must not download')))
    engine=SimpleNamespace(sources=[source],cache=SimpleNamespace(materialize_preview=poster),
        _search_one=search,query_intents={},ranker=SimpleNamespace(warning=None))
    result=asyncio.run(m.source_video_beat(engine,beat_id='b',client_id='c',queries=['bus departing'],
        min_duration=1,max_duration=200,orientation=None))
    assert not result['candidates']
    assert result['provider_counts']['youtube']['clips_downloaded']==0
    assert 'storyboard' in result['rejected_candidates'][0]['quality_reasons'][0]


def test_three_shots_preserve_review_coverage_and_discovery_ids(monkeypatch):
    from backend.app.online_sourcing_cli import _source_outline
    from backend.app.quality_video import synchronize_proposals
    calls=[]
    class Engine:
        quality_mode=True
        max_queries=2
        sources=[]
        async def source_beat(self,**kw):
            calls.append(kw['beat_id'])
            row={'candidates':[{'id':kw['beat_id'],'score':.7,'clip_verified':True,
                  'source':'youtube','source_page':'https://example.com/'+kw['beat_id']}],
                 'discovery_sources':[{'id':'envato:'+kw['beat_id'],'source':'envato'}]}
            synchronize_proposals(row)
            return row
    beat={'id':'b','start_seconds':0,'end_seconds':12,'external_plan':True,
          'broll_queries':['bus'],'visual_plan':{'core_meaning':'travel','shots':[
          {'shot_id':str(i),'description':target,'video_queries':[target]} for i,target in enumerate(['plane','bus','ferry'])]}}
    _,results,coverage=asyncio.run(_source_outline({'beats':[beat]},Engine(),client_id='c'))
    assert len(calls)==3
    assert all(r['proposal_A'] and r['review_state']=='NEEDS_REVIEW' for r in coverage['b'])
    assert [r['discovery_sources'][0]['shot_id'] for r in results]==['0','1','2']


def test_envato_artifact_becomes_unselectable_ui_card(tmp_path):
    from backend.app.curation_artifacts import load_curation_run
    from backend.app.curation_ui_v2 import render_curation_page_v2
    (tmp_path/'semantic-chunks.json').write_text('[{"id":"b","text":"ferry"}]')
    (tmp_path/'online-candidates.json').write_text(json.dumps([{'parent_beat_id':'b','discovery_sources':[
        {'id':'envato:x','source':'envato','title':'Passenger ferry','shot_id':'s3',
         'source_page':'https://elements.envato.com/passenger-ferry-ABC1234',
         'preview_url':'https://example.com/ferry.jpg','quality_state':'source_found'}]}]))
    card=load_curation_run(tmp_path).chunks[0].video_candidates[0]
    assert card.provider=='envato' and card.shot_id=='s3'
    assert not card.clip_verified and card.local_asset_path is None
    html=render_curation_page_v2()
    assert 'envatoEmptyV5' in html and 'ENVATO ELEMENTS' in html
    assert "window.open(a.source_page,'_blank','noopener')" in html


def test_acquisition_stops_after_primary_for_each_of_three_shots(tmp_path,monkeypatch):
    from backend.app import quality_video as m
    downloads=[]
    async def search(source,query,**kw):
        rows=[SimpleNamespace(provider='youtube',provider_id=query+str(i),query=query,
            title=query,description=query,source_page='https://example.com/'+query+str(i),
            orientation='landscape',provider_rank=i,width=1280,height=720,
            rights_state='review_required',creator_name=None,duration=10,
            preview_url='https://example.com/thumb.jpg') for i in range(2)]
        return rows,None
    async def poster(*a):return SimpleNamespace(path=tmp_path/'poster.jpg',cache_hit=False)
    def clip(url,folder,identity,start,provider):
        downloads.append(identity)
        return {'preview_path':str(tmp_path/(identity+'.mp4')),'source_start_seconds':start,'source_end_seconds':start+3.5}
    monkeypatch.setattr(m,'_social_clip',clip)
    monkeypatch.setattr(m,'_frame_samples',lambda c:['one.jpg','two.jpg','three.jpg'])
    monkeypatch.setattr(m,'perceptual_hash',lambda p:None)
    ranker=SimpleNamespace(warning=None,rank=lambda intent,rows:[dict(r,score=.7,quality_state='accepted') for r in rows])
    engine=SimpleNamespace(sources=[SimpleNamespace(provider_name='youtube')],_search_one=search,
        cache=SimpleNamespace(materialize_preview=poster),ranker=ranker,query_intents={})
    async def run():
        return await asyncio.gather(*[m.source_video_beat(engine,beat_id=q,client_id='c',queries=[q],
            min_duration=1,max_duration=60,orientation=None) for q in ('plane','bus','ferry')])
    results=asyncio.run(run())
    assert len(downloads)==3
    assert all(len(r['candidates'])==1 and r['proposals']['proposal_A'] for r in results)
