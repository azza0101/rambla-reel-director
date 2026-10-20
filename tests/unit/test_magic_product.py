import asyncio
import json
from types import SimpleNamespace
from tests.unit.test_cut_pass_routes import tmp_path


def test_canonical_plan_uses_original_text_and_full_geography(tmp_path):
    from backend.app.magic_product import plan_beats
    plan={'global_topic':'Egypt travel','visual_beats':[dict(id='b',original_text='la polizia turistica in Egitto',
        core_meaning='security',action='BROLL',start=0,end=4,shots=[dict(video_queries=['police Egypt'],image_queries=['police Egypt'])])]}
    (tmp_path/'visual-plan.json').write_text(json.dumps(plan))
    beat=plan_beats(tmp_path)[0]
    assert beat['text']=='la polizia turistica in Egitto' and beat['places']==['Egypt']


def test_editorial_resume_repairs_saved_tiny_chunk_overlap_without_recutting(tmp_path):
    from backend.app.magic_product import normalize_semantic_chunk_boundaries
    run = tmp_path / 'run'; run.mkdir()
    chunks = [
        {'id': 'a', 'start': 10.0, 'end': 12.0, 'duration': 2.0, 'words': ['prima']},
        {'id': 'b', 'start': 11.9666667, 'end': 14.0, 'duration': 2.0333333, 'words': ['dopo']},
    ]
    (run / 'semantic-chunks.json').write_text(json.dumps(chunks), encoding='utf-8')

    assert normalize_semantic_chunk_boundaries(run) == 1
    repaired = json.loads((run / 'semantic-chunks.json').read_text(encoding='utf-8'))
    assert repaired[1]['start'] == 12.0
    assert repaired[1]['end'] == 14.0
    assert repaired[1]['duration'] == 2.0
    assert repaired[1]['words'] == ['dopo']
    original = json.loads((run / 'semantic-chunks.before-boundary-normalization.json').read_text(encoding='utf-8'))
    assert original[1]['start'] == 11.9666667


def test_production_selection_writes_normal_selection_and_active_image(tmp_path,monkeypatch):
    from backend.app.magic_product import MagicProductServices
    from backend.app.magic_models import MagicContext,MagicOptions
    from backend.app.magic_store import MagicStore
    from backend.app.curation import CurationCandidate
    import backend.app.native_cut_export as native
    import backend.app.curation_artifacts as artifacts
    import backend.app.editorial_import as editorial
    import backend.app.magic_product as module
    run=tmp_path/'child'/'run';run.mkdir(parents=True)
    (run/'visual-plan.json').write_text(json.dumps({'global_topic':'Egypt','visual_beats':[
        dict(id='b',original_text='Egypt sarcophagus',action='BROLL',start=0,end=5,shots=[])]}))
    image=run/'photo.jpg';image.write_bytes(b'image')
    candidate=CurationCandidate(asset_id='b--image:1',chunk_id='b',kind='image',provider='google_images',
        source_page='https://example.test/image',title='Egypt sarcophagus',description='',score=1,
        rights_state='review',orientation='landscape',local_asset_path=str(image))
    monkeypatch.setattr(native,'load_native_cut',lambda *a:dict(fps='30',duration_seconds=5))
    monkeypatch.setattr(artifacts,'load_curation_run',lambda *a:SimpleNamespace(candidate_index={candidate.asset_id:candidate}))
    monkeypatch.setattr(editorial,'active_retrieval_root',lambda *a:run)
    monkeypatch.setattr(module,'sample_candidate',lambda row,*a:{**row,'sampled_frames':[str(image)]})
    monkeypatch.setattr(module,'judge_batch',lambda rows,*a:{r['asset_id']:dict(verdict='verified',reason='correct image') for r in rows})
    async def prepare(*a): return []
    store=MagicStore(tmp_path)
    services=MagicProductServices(None,tmp_path,store,None,None,prepare,None,None,visual_client=lambda:object())
    context=MagicContext(source_project_id='source',output_project_id='child',run_id='run',source_signature='s',cut_revision='r')
    result=asyncio.run(services.select('child',run,context,MagicOptions(),lambda *a:None))
    assert result['selected']==1 and not result['partial']
    selected=json.loads((run/'selection-plan.json').read_text())
    assert selected['chunks']['b']['selected_assets'][0]['asset_id']==candidate.asset_id
    decision=json.loads((run/'magic-coverage.json').read_text())['decisions'][0]
    assert decision['enabled'] and decision['role']=='image_coverage'
    assert result['enabled_images']==1


def test_selection_orders_an_image_fallback_before_second_video_option(tmp_path):
    from backend.app.magic_product import visual_candidate_order
    candidates = [
        {'asset_id':'beat--video:1','chunk_id':'beat','kind':'video'},
        {'asset_id':'beat--video:2','chunk_id':'beat','kind':'video'},
        {'asset_id':'beat--image:1','chunk_id':'beat','kind':'image'},
    ]
    ordered = visual_candidate_order([{'id':'beat'}], candidates)
    assert [row['asset_id'] for row in ordered] == ['beat--video:1','beat--image:1','beat--video:2']


def test_magic_always_selects_compact_generic_topic_and_each_place():
    from backend.app.magic_product import automatic_generic_selection
    items = [
        {'provider_id':'sri-1','coverage_group':'places','place':'Sri Lanka'},
        {'provider_id':'sri-2','coverage_group':'places','place':'Sri Lanka'},
        {'provider_id':'italy-1','coverage_group':'places','place':'Italy'},
        {'provider_id':'topic-1','coverage_group':'topic'},
        {'provider_id':'topic-2','coverage_group':'topic'},
    ]
    assert automatic_generic_selection(items) == ['sri-1','italy-1','topic-1','topic-2']


def test_product_server_registers_real_magic_services(tmp_path):
    from backend.app.curation_server import create_app
    app=create_app(project_root=tmp_path)
    assert hasattr(app.state,'magic_runner')
    assert any(getattr(route,'path','').endswith('/{pid}/magic') for route in app.routes)


def test_explicit_passport_and_sri_lanka_are_never_lost_in_generic_director_queries(tmp_path):
    from backend.app.magic_product import plan_beats
    plan={'global_topic':'ethical travel','visual_beats':[
        dict(id='passport',original_text='Il passaporto non apre tutte le porte',
             action='BROLL',start=0,end=4,shots=[dict(video_queries=['travel'],image_queries=['travel photos'])]),
        dict(id='sri',original_text='Siamo arrivati in Sri Lanka',
             action='BROLL',start=4,end=8,shots=[dict(video_queries=['beautiful beach'],image_queries=['holiday'])]),
    ]}
    (tmp_path/'visual-plan.json').write_text(json.dumps(plan))
    passport,sri=plan_beats(tmp_path)
    assert 'passport' in passport['queries'][0] and 'passport' in passport['image_queries'][0]
    assert 'Sri Lanka' in sri['queries'][0] and 'Sri Lanka' in sri['image_queries'][0]


def test_specific_video_and_image_are_in_front_of_generic_video_during_visual_budget():
    from backend.app.magic_product import visual_candidate_order
    rows=[
        dict(asset_id='generic',chunk_id='b',kind='video',role='generic'),
        dict(asset_id='photo',chunk_id='b',kind='image'),
        dict(asset_id='video',chunk_id='b',kind='video',role='coverage'),
        dict(asset_id='extra',chunk_id='b',kind='video',role='coverage'),
    ]
    assert [r['asset_id'] for r in visual_candidate_order([{'id':'b'}],rows)] == [
        'video','photo','generic','extra']


def test_selection_retries_a_transient_visual_provider_failure(tmp_path,monkeypatch):
    """A temporary 503 must not turn every prepared candidate into uncertain."""
    from backend.app.magic_product import MagicProductServices
    from backend.app.magic_models import MagicContext, MagicOptions
    from backend.app.magic_store import MagicStore
    from backend.app.curation import CurationCandidate
    from backend.app.gemini_interactions import GeminiAPIError
    import backend.app.native_cut_export as native
    import backend.app.curation_artifacts as artifacts
    import backend.app.editorial_import as editorial
    import backend.app.magic_product as module

    run=tmp_path/'child'/'run';run.mkdir(parents=True)
    (run/'visual-plan.json').write_text(json.dumps({'global_topic':'Passport','visual_beats':[
        dict(id='b',original_text='passaporto',action='BROLL',start=0,end=5,shots=[])]}))
    image=run/'passport.jpg';image.write_bytes(b'image')
    candidate=CurationCandidate(asset_id='b--image:1',chunk_id='b',kind='image',provider='google_images',
        source_page='https://example.test/passport',title='passport close up',description='',score=1,
        rights_state='review',orientation='landscape',local_asset_path=str(image))
    monkeypatch.setattr(native,'load_native_cut',lambda *a:dict(fps='30',duration_seconds=5))
    monkeypatch.setattr(artifacts,'load_curation_run',lambda *a:SimpleNamespace(candidate_index={candidate.asset_id:candidate}))
    monkeypatch.setattr(editorial,'active_retrieval_root',lambda *a:run)
    monkeypatch.setattr(module,'sample_candidate',lambda row,*a:{**row,'sampled_frames':[str(image)]})
    calls=[]
    def judge(rows,*_):
        calls.append(rows)
        if len(calls)==1:
            raise GeminiAPIError('HTTP 503')
        return {r['asset_id']:dict(verdict='verified',reason='passport visible') for r in rows}
    monkeypatch.setattr(module,'judge_batch',judge)
    async def prepare(*a): return []
    services=MagicProductServices(None,tmp_path,MagicStore(tmp_path),None,None,prepare,None,None,visual_client=lambda:object())
    context=MagicContext(source_project_id='source',output_project_id='child',run_id='run',source_signature='s',cut_revision='r')
    result=asyncio.run(services.select('child',run,context,MagicOptions(),lambda *a:None))
    assert len(calls)==2
    assert result['selected']==1
    assert any('riprovata' in warning.lower() for warning in result['warnings'])


def test_selection_skips_a_media_preparation_timeout_instead_of_hanging(tmp_path,monkeypatch):
    from backend.app.magic_product import MagicProductServices
    from backend.app.magic_models import MagicContext, MagicOptions
    from backend.app.magic_store import MagicStore
    from backend.app.curation import CurationCandidate
    import backend.app.native_cut_export as native
    import backend.app.curation_artifacts as artifacts
    import backend.app.editorial_import as editorial

    run=tmp_path/'child'/'run';run.mkdir(parents=True)
    (run/'visual-plan.json').write_text(json.dumps({'global_topic':'Passport','visual_beats':[
        dict(id='b',original_text='passaporto',action='BROLL',start=0,end=5,shots=[])]}))
    image=run/'passport.jpg';image.write_bytes(b'image')
    candidate=CurationCandidate(asset_id='b--image:1',chunk_id='b',kind='image',provider='google_images',
        source_page='https://example.test/passport',title='passport close up',description='',score=1,
        rights_state='review',orientation='landscape',local_asset_path=str(image))
    monkeypatch.setattr(native,'load_native_cut',lambda *a:dict(fps='30',duration_seconds=5))
    monkeypatch.setattr(artifacts,'load_curation_run',lambda *a:SimpleNamespace(candidate_index={candidate.asset_id:candidate}))
    monkeypatch.setattr(editorial,'active_retrieval_root',lambda *a:run)
    async def never_finishes(*_):
        await asyncio.Event().wait()
    services=MagicProductServices(None,tmp_path,MagicStore(tmp_path),None,None,never_finishes,None,None,
        visual_client=lambda:object(),media_prepare_timeout_seconds=.001)
    context=MagicContext(source_project_id='source',output_project_id='child',run_id='run',source_signature='s',cut_revision='r')
    result=asyncio.run(services.select('child',run,context,MagicOptions(),lambda *a:None))
    assert result['selected']==0
    assert any('scaduta' in warning.lower() for warning in result['warnings'])



def test_magic_output_keeps_source_player_on_the_original_parent():
    from backend.app.magic_ui import JS
    assert "const sourcePid=cut?.cut_parent_project_id||pid" in JS
    assert "media/source-video/source" in JS


def test_incremental_selection_preserves_other_choices_and_certified_placements(tmp_path,monkeypatch):
    from backend.app.magic_product import MagicProductServices
    from backend.app.magic_models import MagicContext,MagicOptions
    import backend.app.native_cut_export as native
    import backend.app.curation_artifacts as artifacts
    import backend.app.editorial_import as editorial
    run=tmp_path/'child'/'run';run.mkdir(parents=True)
    plan={'global_topic':'Egypt','visual_beats':[dict(id=bid,original_text='Egypt travel',action='BROLL',start=0,end=4,shots=[]) for bid in ['kept','changed']]}
    (run/'visual-plan.json').write_text(json.dumps(plan))
    (run/'selection-plan.json').write_text(json.dumps({'chunks':{'kept':{'selected_assets':[{'asset_id':'kept--original'}]}}}))
    (run/'magic-coverage.json').write_text(json.dumps({'decisions':[{'beat_id':'kept','asset_id':'kept--original'}],'verdicts':{}}))
    monkeypatch.setattr(native,'load_native_cut',lambda *a:dict(fps='30',duration_seconds=5))
    monkeypatch.setattr(artifacts,'load_curation_run',lambda *a:SimpleNamespace(candidate_index={}))
    monkeypatch.setattr(editorial,'active_retrieval_root',lambda *a:run)
    services=MagicProductServices(None,tmp_path,None,None,None,None,None,None,visual_client=lambda:None)
    context=MagicContext(source_project_id='source',output_project_id='child',run_id='r',source_signature='s',cut_revision='c')
    result=asyncio.run(services.select('child',run,context,MagicOptions(max_visual_requests=0),lambda *a:None,beat_ids=['changed']))
    assert result['uncovered']==1
    assert json.loads((run/'selection-plan.json').read_text())['chunks']['kept']['selected_assets'][0]['asset_id']=='kept--original'
    assert json.loads((run/'magic-coverage.json').read_text())['decisions']==[{'beat_id':'kept','asset_id':'kept--original'}]
    asyncio.run(services.select('child',run,context,MagicOptions(max_visual_requests=0),lambda *a:None,beat_ids=['kept']))
    assert json.loads((run/'magic-coverage.json').read_text())['decisions']==[{'beat_id':'kept','asset_id':'kept--original'}]


def test_visual_client_keeps_configured_transport_fallback(monkeypatch):
    monkeypatch.delenv('RAMBLA_VISUAL_BACKEND',raising=False)
    from backend.app.magic_product import configured_visual_client
    from backend.app.gemini_interactions import DEFAULT_FALLBACK_MODELS
    monkeypatch.setenv('GEMINI_API_KEY','test-key-not-sent')
    client=configured_visual_client()
    assert client.fallback_models==DEFAULT_FALLBACK_MODELS
    assert client.max_retries_per_model==0


def test_coverage_upgrade_scope_includes_full_scenes_and_preserves_manual_choices():
    from backend.app.magic_product import coverage_upgrade_scope
    beats=[dict(id=k,start=0,end=d) for k,d in [('photo',3),('empty',3),('manual',3),('video',3),('tiny',.4)]]
    selections={k:{'selected_assets':[{'asset_id':a}]} for k,a in [('photo','p'),('manual','m'),('video','v')]}
    decisions=[dict(beat_id='photo',asset_id='p',role='image_coverage'),dict(beat_id='video',asset_id='v',role='coverage')]
    assert coverage_upgrade_scope(beats,selections,decisions)==['photo','empty']
