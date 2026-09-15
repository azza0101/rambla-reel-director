import copy
import json
import pytest
from backend.app.editorial_import import transcript_package, validate_import, import_plan, retrieval_bundle


def fixture(tmp_path):
    chunks = [{'id':'c1','start':0.0,'end':3.0,'text':'Slice the tomatoes.'}, {'id':'c2','start':3.0,'end':6.0,'text':'Keep the pieces small.'}, {'id':'c3','start':6.0,'end':8.0,'text':'That is my advice.'}]
    (tmp_path/'semantic-chunks.json').write_text(json.dumps(chunks), encoding='utf-8')
    (tmp_path/'transcript-raw.json').write_text(json.dumps({'language':'en','segments':chunks}), encoding='utf-8')
    (tmp_path/'analysis-signature.json').write_text('{"analysis_signature":"source1"}', encoding='utf-8')
    package = transcript_package(tmp_path, 'project1', 8.0)
    plan = {'schema_version':'rambla-visual-plan-1','project_id':'project1','transcript_signature':package['transcript_signature'],'global_topic':'Preparing tomatoes','visual_beats':[
        {'id':'vb-1','start':0.0,'end':6.0,'covered_chunk_ids':['c1','c2'],'original_text':'Slice the tomatoes. Keep the pieces small.','action':'BROLL','editorial_function':'instruction','core_meaning':'Cut small tomato pieces','subtext':'','visual_mode':'single','shots':[{'shot_id':'s1','description':'Hands slicing tomatoes on a cutting board','image_queries':['sliced tomatoes cutting board'],'video_queries':['slicing tomatoes close up']}],'avoid':[]},
        {'id':'vb-2','start':6.0,'end':8.0,'covered_chunk_ids':['c3'],'original_text':'That is my advice.','action':'KEEP_TALKING_HEAD','editorial_function':'conclusion','core_meaning':'Personal advice','subtext':'','visual_mode':'single','shots':[],'avoid':[]}]}
    return package, plan


def test_export_import_groups_chunks_preserves_queries_and_isolates_versions(tmp_path):
    package, plan = fixture(tmp_path)
    assert package['full_transcript'] == 'Slice the tomatoes. Keep the pieces small. That is my advice.'
    assert package['chunks'][1]['start'] == 3.0
    import_plan(tmp_path, plan, package)
    root, chunks, internal, outline = retrieval_bundle(tmp_path)
    assert [c['id'] for c in chunks] == ['vb-1','vb-2']
    assert internal['chunks']['vb-1']['shots'] == plan['visual_beats'][0]['shots']
    assert outline['beats'][0]['broll_queries'] == ['slicing tomatoes close up']
    assert outline['beats'][1]['broll_queries'] == []
    assert root.is_relative_to(tmp_path/'editorial')
    changed = copy.deepcopy(plan); changed['visual_beats'][0]['shots'][0]['description'] += ' in a kitchen'
    import_plan(tmp_path, changed, package)
    assert retrieval_bundle(tmp_path)[0] != root


@pytest.mark.parametrize('change', ['project','signature','coverage','timing','text','action','shot','extra','continuity','boolean','empty_query'])
def test_strict_validation(tmp_path, change):
    package, plan = fixture(tmp_path)
    b = plan['visual_beats'][0]
    if change == 'project': plan['project_id'] = 'wrong'
    elif change == 'signature': plan['transcript_signature'] = 'wrong'
    elif change == 'coverage': b['covered_chunk_ids'] = ['c2','c1']
    elif change == 'timing': b['end'] = 5.0
    elif change == 'text': b['original_text'] = 'Invented text'
    elif change == 'action': b['action'] = 'KEEP_TALKING_HEAD'
    elif change == 'shot': b['shots'] *= 2
    elif change == 'extra': b['secret'] = 'extra'
    elif change == 'continuity': plan['visual_beats'][1]['action'] = 'CONTINUE_PREVIOUS_VISUAL'
    elif change == 'boolean': b['start'] = True
    elif change == 'empty_query': b['shots'][0]['image_queries'] = []
    with pytest.raises(ValueError): validate_import(plan, package)


def test_stale_transcript_fails_closed(tmp_path):
    package, plan = fixture(tmp_path); import_plan(tmp_path, plan, package)
    (tmp_path/'semantic-chunks.json').write_text('[]', encoding='utf-8')
    with pytest.raises(ValueError): retrieval_bundle(tmp_path)


def test_api_import_export_selection_and_source_gate_without_models(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app import debug_server as server
    calls=[]
    async def fake_run(state): calls.append(state.stage_type)
    monkeypatch.setattr(server,'_run',fake_run)
    client=TestClient(server.create_app(project_root=tmp_path/'projects',allowed_media_roots=[tmp_path],probe_runner=lambda _: {'duration':8.0,'fps':25,'width':1280,'height':720,'has_audio':False}))
    pid=client.post('/api/curation/projects',json={'name':'Import test'}).json()['project_id']
    base=f'/api/curation/projects/{pid}'
    source=tmp_path/'source.mp4';source.write_bytes(b'video')
    project=client.post(base+'/source/local',json={'path':str(source)}).json()
    run=tmp_path/'projects'/pid/'run';run.mkdir()
    package,plan=fixture(run)
    (run/'analysis-signature.json').write_text(json.dumps({'analysis_signature':project['analysis_signature']}),encoding='utf-8')
    assert client.post(base+'/source/videos').status_code==422
    exported=client.get(base+'/editorial-input'); assert exported.status_code==200
    package=exported.json(); plan.update(project_id=pid,transcript_signature=package['transcript_signature'])
    assert 'WHOLE reel' in package['instructions']
    bad=copy.deepcopy(plan);bad['visual_beats'][0]['start']=1
    assert client.post(base+'/editorial-plan',json=bad).status_code==422
    assert not (run/'visual-plan.json').exists()
    assert client.post(base+'/editorial-plan',json=plan).status_code==200
    payload=client.get(base+'/curation').json()
    assert payload['editorial_plan_ready']
    assert [c['id'] for c in payload['chunks']]==['vb-1','vb-2']
    assert payload['chunks'][0]['start']==0
    assert payload['chunks'][0]['end']==6
    assert payload['selection_plan']['chunks']['vb-2']['no_broll']
    assert client.put(base+'/curation/chunks/vb-1/selection',json={'asset_ids':[],'no_broll':True}).status_code==200
    assert client.get(base+'/curation').json()['selection_plan']['chunks']['vb-1']['no_broll']
    for stage in ('videos','images'):
        assert client.post(base+'/source/'+stage).status_code==200
        server.RUNS.clear()
    assert calls==['videos','images']
    assert payload['resolve_calls']==0
    # Changing source must not show or source assets from the prior transcript.
    other=tmp_path/'other.mp4';other.write_bytes(b'other video')
    client.post(base+'/source/local',json={'path':str(other)})
    assert client.get(base+'/curation').json()['chunks']==[]
    assert client.post(base+'/source/images').status_code==422


def test_provider_ranking_has_no_fabricated_qwen_score():
    from backend.app.retrieval_ranker import ProviderOrderRanker
    from backend.app.proposals import select_proposals
    rows=ProviderOrderRanker().rank('tomatoes',[{'id':'a','width':1920,'height':1080}])
    assert rows[0]['embedding_score'] is None
    result=select_proposals(rows,minimum=1)
    assert result['proposal_A']['qwen_score'] is None


def test_every_imported_shot_is_searched_without_generators(tmp_path):
    import asyncio
    from backend.app.online_sourcing_cli import _source_outline
    package,plan=fixture(tmp_path)
    beat=plan['visual_beats'][0];beat['visual_mode']='sequence'
    shot=copy.deepcopy(beat['shots'][0]);shot.update(shot_id='s2',description='Knife beside chopped tomatoes',video_queries=['knife chopped tomatoes'])
    beat['shots'].append(shot)
    import_plan(tmp_path,plan,package)
    root,chunks,internal,outline=retrieval_bundle(tmp_path)
    class Engine:
        sources=[];max_queries=8
        def __init__(self):self.calls=[]
        async def source_beat(self,**kwargs):
            self.calls.append(kwargs)
            return {'candidates':[],'queries':kwargs['queries']}
    engine=Engine()
    asyncio.run(_source_outline(outline,engine,client_id='p'))
    assert [c['queries'] for c in engine.calls]==[s['video_queries'] for s in beat['shots']]
    assert len(engine.calls)==2 # KEEP_TALKING_HEAD never searches


def test_editorial_controller_without_browser(tmp_path):
    import shutil
    import subprocess
    from pathlib import Path
    from backend.app.curation_ui import render_curation_page
    if not shutil.which('node'): pytest.skip('Node required for controller test')
    payload=tmp_path/'controller.json'
    payload.write_text(json.dumps({'script':render_curation_page().split('<script>')[1].split('</script>')[0]}),encoding='utf-8')
    subprocess.run(['node',str(Path(__file__).parents[1]/'editorial_controller_test.cjs'),str(payload)],check=True,capture_output=True,text=True)


def test_continuity_and_local_producer_contract(tmp_path):
    from backend.app.editorial_import import export_local_producer
    package,plan=fixture(tmp_path)
    b=plan['visual_beats'][1]; b.update(action='CONTINUE_PREVIOUS_VISUAL',continuation_from='vb-1')
    validate_import(plan,package)
    result={'status':'complete','visual_beats':[{'visual_beat_id':b['id'],'covered_chunk_ids':b['covered_chunk_ids'],'visual_action':b['action'],'editorial_meaning':b['core_meaning'],'shots':b['shots'],'avoid':b['avoid'],'continuity_from':b.get('continuation_from')} for b in plan['visual_beats']]}
    exported=export_local_producer(result,package)
    assert exported['visual_beats'][1]['continuation_from']=='vb-1'
    assert exported['visual_beats'][0]['shots']==plan['visual_beats'][0]['shots']


def test_provider_mode_does_not_instantiate_any_model(tmp_path,monkeypatch):
    from backend.app import qwen_stack
    from backend.app.online_sourcing_cli import _real_engine
    def forbidden(*a,**k): raise AssertionError('model instantiation forbidden')
    monkeypatch.setattr(qwen_stack.LocalQwenEmbedder,'__init__',forbidden)
    monkeypatch.setattr(qwen_stack.LocalQwenDirectorGenerator,'__init__',forbidden)
    monkeypatch.setenv('RAMBLA_RETRIEVAL_RANKING','provider')
    engine=_real_engine(client_id='p',pexels_api_key=None,model_root=tmp_path/'not-installed',embedding_code_root=None,cache_root=tmp_path/'cache',max_candidates=3)
    assert engine.ranker.__class__.__name__=='ProviderOrderRanker'


def test_duplicate_json_fields_rejected():
    from backend.app.editorial_import import parse_plan
    with pytest.raises(ValueError,match='duplicate JSON field'):
        parse_plan('{"project_id":"one","project_id":"two"}')


def test_cross_media_dedupe_preserves_same_beat_alternatives(tmp_path):
    from backend.app.media_quality import other_media_history,diverse_candidates
    row={'source_page':'https://example.com/1'}
    (tmp_path/'online-candidates.json').write_text(json.dumps([{'parent_beat_id':'vb-1','candidates':[row]}]),encoding='utf-8')
    assert other_media_history(tmp_path,'video','vb-1')==[]
    assert diverse_candidates([row],other_media_history(tmp_path,'video','vb-2'),limit=4)==([],1)


def test_shelf_retains_candidates_for_each_requested_shot():
    from backend.app.curation import CurationCandidate,build_candidate_shelf
    rows=[CurationCandidate(str(i),'vb','video','provider',f'https://example.com/{i}','title','description',1-i*.01,'review_required','landscape',shot_id=shot) for i,shot in enumerate(['s1','s1','s1','s2','s3'])]
    assert [r.shot_id for r in build_candidate_shelf(rows).video]==['s1','s2','s3']


def test_local_producer_cannot_overwrite_import(tmp_path):
    from backend.app.visual_planner import load_or_create_visual_plan
    package,plan=fixture(tmp_path);import_plan(tmp_path,plan,package)
    with pytest.raises(ValueError,match='separate experimental'):
        load_or_create_visual_plan(package['chunks'],{},tmp_path,generate=lambda _: pytest.fail('generation must not run'))
    assert json.loads((tmp_path/'visual-plan.json').read_text(encoding='utf-8'))==plan
