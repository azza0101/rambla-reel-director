from pathlib import Path
from uuid import uuid4
import pytest
from backend.app.atomic_io import write_json
from backend.app.geographic_context import beat_places, anchor_queries, conflicting_place, places_in
from backend.app.editorial_import import transcript_package, import_plan, load_import, active_retrieval_root, read
from backend.app.transcript_intents import load_phrase_intents, save_phrase_intents
from backend.app.beat_split import split_preview, split_beat


def test_egyptian_police_queries_keep_geography_on_retries():
    from backend.app.retrieval_quality import provider_video_variants
    for round_no in range(5):
        variants=provider_video_variants(['American tourist police walking down street'], 'tourist police on street', round_no)
        queries=anchor_queries(variants,['Egypt'])
        assert queries and all('Egypt' in q and 'American' not in q for q in queries)
        assert all('interior' not in q for q in queries)
    assert conflicting_place('American police in New York',['Egypt'])
    assert not conflicting_place('Tourist police in Luxor',['Egypt'])


def test_geography_uses_current_then_recent_then_unambiguous_global():
    assert beat_places('Siamo in Thailandia','Egitto','Luxor') == ['Thailand']
    assert beat_places('polizia turistica','Viaggio in Egitto') == ['Egypt']
    assert beat_places('polizia turistica','Egitto e Thailandia') == []
    assert beat_places('strada','', 'Egitto poi Thailandia poi Egitto') == ['Egypt']
    assert places_in('Visitiamo Egitto e Thailandia') == ['Egypt','Thailand']


@pytest.fixture
def scene_run():
    run=Path('.runtime-temp')/('scene-test-'+uuid4().hex)
    run.mkdir(parents=True)
    words=[{'text':word,'start':i*.5,'end':(i+1)*.5} for i,word in enumerate('tourist police guard the temple entrance'.split())]
    chunks=[{'id':'c1','text':' '.join(w['text'] for w in words),'start':0.,'end':3.,'words':words}]
    write_json(run/'semantic-chunks.json',chunks)
    write_json(run/'transcript-raw.json',{'segments':chunks,'language':'en'})
    intents=load_phrase_intents(run)
    save_phrase_intents(run,{'c1':{'coverage':True}},intents['transcript_signature'])
    package=transcript_package(run,'test',3.)
    row=package['chunks'][0]
    beat={'id':'b1','start':0.,'end':3.,'covered_chunk_ids':[row['id']], 'original_text':chunks[0]['text'],
          'action':'BROLL','editorial_function':'show place','core_meaning':'tourist police','subtext':'', 'visual_mode':'single',
          'shots':[{'shot_id':'s1','description':'tourist police Egypt','video_queries':['tourist police Egypt'],'image_queries':['tourist police Egypt']}],'avoid':[]}
    plan={'schema_version':'rambla-visual-plan-1','project_id':'test','transcript_signature':package['transcript_signature'],'global_topic':'Egypt','visual_beats':[beat]}
    root=import_plan(run,plan,package)
    write_json(root/'curation.json',{'sentinel':'keep selections'})
    return run


def test_split_keeps_every_word_timing_and_existing_assets(scene_run):
    old_root=active_retrieval_root(scene_run)
    before=(old_root/'curation.json').read_bytes()
    preview=split_preview(scene_run,'b1')
    result=split_beat(scene_run,'b1',3,preview['revision'])
    plan=load_import(scene_run)
    left,right=plan['visual_beats']
    assert left['original_text']+' '+right['original_text']==preview['text']
    assert (left['start'],left['end'],right['start'],right['end'])==(0.,1.5,1.5,3.)
    assert left['id']=='b1' and right['id']!=left['id']
    assert active_retrieval_root(scene_run)==old_root
    assert (old_root/'curation.json').read_bytes()==before
    assert Path(result['backup']).is_dir()
    # A second split is still valid and does not discard the previous cut.
    split_beat(scene_run,right['id'],1,split_preview(scene_run,right['id'])['revision'])
    assert len(load_import(scene_run)['visual_beats'])==3


def test_stale_or_invalid_split_does_not_change_plan(scene_run):
    before=(scene_run/'visual-plan.json').read_bytes()
    with pytest.raises(ValueError):split_beat(scene_run,'b1',2,'stale')
    with pytest.raises(ValueError):split_beat(scene_run,'b1',6,split_preview(scene_run,'b1')['revision'])
    assert (scene_run/'visual-plan.json').read_bytes()==before


def test_page_renders_complete_numbered_workflow():
    from backend.app.curation_ui_v2 import render_curation_page_v2
    html=render_curation_page_v2('test')
    assert '<title>RMBL B ROLL</title>' in html
    assert 'id="socialConnectionsV5" open' not in html
    assert "filter:'broll'" in html
    assert '`r`n' not in html
    assert html.index('5 · Visual beats')<html.index('6 · Coperture generiche')<html.index('7 · Export timeline')
    assert 'installCompactSources()' in html and 'openSplitScene' in html
    assert 'Cerca immagini per questa frase' in html
    assert 'CERCA ALTRE IMMAGINI' in html


@pytest.mark.asyncio
async def test_manual_query_is_sent_exactly_without_old_shot_filter(monkeypatch):
    from types import SimpleNamespace as NS
    from backend.app.quality_video import source_video_beat
    import json
    sent=[]
    async def search(source,query,**kwargs):
        sent.append(query)
        return [],None
    engine=NS(sources=[NS(provider_name='pexels')],query_intents={},_search_one=search,ranker=NS(),
              beat_context={'b':{'places':['Egypt']}})
    monkeypatch.setenv('RAMBLA_SOCIAL_SEARCH_OPTIONS',json.dumps({'query_overrides':{'*':'Thailand beach'},'variation_round':4}))
    result=await source_video_beat(engine,beat_id='b:shot:s1',client_id='test',queries=['Egypt police'],min_duration=1,max_duration=180,orientation=None,retrieval_intent='tourist police Egypt')
    assert sent == ['Thailand beach']
    assert result['manual_query'] and not result['geographic_context']


def test_manual_image_query_replaces_generated_variants_for_the_active_shot():
    from backend.app.quality_images import image_queries_for_shot

    shot = {'shot_id': 'shot_02', 'image_queries': ['tourist police Egypt']}
    assert image_queries_for_shot(
        shot,
        ['tourist police Egypt', 'Egypt security presence'],
        {'query_overrides': {'shot_02': 'Minya police checkpoint'}},
    ) == (['Minya police checkpoint'], True)
    assert image_queries_for_shot(
        shot,
        ['tourist police Egypt'],
        {'query_overrides': {'*': 'Egypt jihad 1990 archive'}},
    ) == (['Egypt jihad 1990 archive'], True)


def test_additional_image_round_starts_from_a_different_automatic_query():
    from backend.app.quality_images import image_variants_for_search

    original = image_variants_for_search(['Egypt archive', 'Minya history'], False, {'variation_round': 0})
    next_round = image_variants_for_search(['Egypt archive', 'Minya history'], False, {'variation_round': 1})
    assert set(next_round) == set(original)
    assert next_round[0] != original[0]
    assert image_variants_for_search(['manual exact query'], True, {'variation_round': 8}) == ['manual exact query']


@pytest.mark.asyncio
async def test_manual_image_query_is_the_only_query_sent_to_photo_sources(tmp_path, monkeypatch):
    from types import SimpleNamespace as NS
    from backend.app.quality_images import source_images
    import json

    sent = []
    class Source:
        provider_name = 'test-photos'
        async def search(self, query, limit=12):
            sent.append(query)
            return []
    plan = {'chunks': {'beat-1': {
        'visual_action': 'BROLL', 'editorial_function': 'show evidence',
        'core_meaning': 'Egypt history', 'subtext': '', 'visual_mode': 'single', 'avoid': [],
        'shots': [{'shot_id': 'shot-1', 'description': 'Egypt archive',
                   'image_queries': ['generic Egypt street'], 'video_queries': []}],
    }}}
    monkeypatch.setenv('RAMBLA_SOCIAL_SEARCH_OPTIONS', json.dumps({
        'query_overrides': {'*': 'Egypt sarcophagus archive'}
    }))

    result = await source_images(
        [{'id': 'beat-1', 'text': 'Egypt history'}], tmp_path, plan,
        NS(visual=None, warning='ranker unavailable', rank=lambda _intent, rows: rows),
        'test', sources=[Source()],
    )

    assert sent == ['Egypt sarcophagus archive']
    assert result['chunks']['beat-1']['queries'] == ['Egypt sarcophagus archive']


def test_place_match_does_not_replace_the_requested_subject():
    from backend.app.geographic_context import missing_subject
    assert missing_subject('tourist police Egypt','tourists exploring pyramids of Giza')
    assert not missing_subject('tourist police Egypt','Egyptian police officers at temple')


def test_location_suggestions_are_grouped_and_keep_selected_media(scene_run, monkeypatch):
    from fastapi.testclient import TestClient
    from types import SimpleNamespace as NS
    from backend.app.curation_server import create_app
    from backend.app.curation_project import ProjectStore
    from backend.app.online_assets import PexelsSource
    root=scene_run/'projects'
    project=ProjectStore(root,probe_runner=lambda _: {}).create('Geography test')
    run=root/project.project_id/'run';run.mkdir(exist_ok=True)
    write_json(run/'transcript-raw.json',{'text':'Viaggio in Egitto e poi Thailandia'})
    write_json(run/'generic-coverage.json',{'items':[{'provider_id':'saved','title':'Chosen sarcophagus','local_path':'keep.mp4'}],'selected':['saved']})
    async def search(self,query,**kwargs):
        place=query.split()[0]
        return [NS(provider='pexels',provider_id=place,query=query,source_page='https://example.com/'+place,
                   title=place+' scenery',description=place,duration=5,width=1920,height=1080,
                   orientation='landscape',preview_url='',selected_rendition_url='',provider_rank=1)]
    monkeypatch.setattr(PexelsSource,'search',search)
    with TestClient(create_app(project_root=root)) as client:
        response=client.get(f'/api/curation/projects/{project.project_id}/generic-coverage?scope=places&refresh=true')
    assert response.status_code==200
    payload=response.json()
    assert {r['place'] for r in payload['items'] if r.get('place')}=={'Egypt','Thailand'}
    assert payload['selected']==['saved']
    assert next(r for r in payload['items'] if r['provider_id']=='saved')['local_path']=='keep.mp4'


@pytest.mark.asyncio
async def test_automatic_search_rejects_geographic_only_results(monkeypatch):
    from types import SimpleNamespace as NS
    from backend.app.quality_video import source_video_beat
    sent=[]
    async def search(source,query,**kwargs):
        sent.append(query)
        return [NS(provider='pexels',provider_id='1',query=query,source_page='https://example.com/1',title='Tourists at pyramids in Egypt',description='')],None
    engine=NS(sources=[NS(provider_name='pexels')],query_intents={},_search_one=search,ranker=NS(),beat_context={'b':{'places':['Egypt']}})
    monkeypatch.setenv('RAMBLA_SOCIAL_SEARCH_OPTIONS','{}')
    result=await source_video_beat(engine,beat_id='b:shot:s1',client_id='test',queries=['American tourist police'],min_duration=1,max_duration=180,orientation=None,retrieval_intent='tourist police')
    assert sent and all('Egypt' in q and 'American' not in q for q in sent)
    assert not result['candidates'] and not result.get('discovery_sources')
    assert result['rejected_candidates'][0]['quality_reasons']==['wrong geography or missing requested subject']
