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


def test_production_selection_writes_normal_selection_and_disabled_image(tmp_path,monkeypatch):
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
    assert not decision['enabled'] and decision['role']=='fallback_image'


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
