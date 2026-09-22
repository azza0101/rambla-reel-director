import json
from pathlib import Path
import pytest
from tests.unit.test_editorial_import import fixture


def test_external_plan_survives_retrieval_invalidation(tmp_path):
    from backend.app.editorial_import import import_plan
    from backend.app.debug_run_cli import invalidate_stale_analysis_outputs,editorial_artifacts_match
    package,plan=fixture(tmp_path);import_plan(tmp_path,plan,package)
    before=(tmp_path/'visual-plan.json').read_bytes()
    assert editorial_artifacts_match(tmp_path,'source1')
    invalidate_stale_analysis_outputs(tmp_path,'source1')
    assert (tmp_path/'visual-plan.json').read_bytes()==before


@pytest.mark.parametrize('missing',[False,True])
def test_reuse_migration_requires_matching_source_and_guide(tmp_path,missing):
    from backend.app.curation_project import ProjectStore
    from backend.app.editorial_import import import_plan,load_import
    from backend.app.debug_run_cli import analysis_input_signature
    from backend.app.analysis_reuse import ensure_analysis_ready
    store=ProjectStore(tmp_path/'projects',probe_runner=lambda p:dict(duration=8,fps=25,width=1280,height=720,has_audio=False))
    project=store.create('reuse');source=tmp_path/'source.mp4';source.write_bytes(b'source')
    project=store.register_local_video(project.project_id,source)
    run=tmp_path/'projects'/project.project_id/'run';run.mkdir()
    package,plan=fixture(run)
    if missing:
        (run/'analysis-signature.json').unlink()
        from backend.app.editorial_import import transcript_package
        package=transcript_package(run,project.project_id,8)
    package['project_id']=project.project_id;plan.update(project_id=project.project_id,transcript_signature=package['transcript_signature'])
    import_plan(run,plan,package)
    (run/'run-input.json').write_text(json.dumps(analysis_input_signature(source,None)))
    before={p.name:p.read_bytes() for p in run.glob('*.json')}
    assert ensure_analysis_ready(run,project)
    assert load_import(run)==plan
    assert (run/'visual-plan.json').read_bytes()==before['visual-plan.json']
    assert (run/'semantic-chunks.json').read_bytes()==before['semantic-chunks.json']
    from fastapi.testclient import TestClient
    from backend.app.debug_server import create_app
    with TestClient(create_app(project_root=tmp_path/'projects',allowed_media_roots=[tmp_path])) as client:
        base=f'/api/curation/projects/{project.project_id}'
        payload=client.get(base+'/curation').json()
        assert payload['analysis_ready'] and payload['editorial_plan_ready']
        assert client.post(base+'/analyze').json()['status']=='reused'
        assert (run/'visual-plan.json').read_bytes()==before['visual-plan.json']
    source.write_bytes(b'changed source')
    assert not ensure_analysis_ready(run,project)


def test_temporal_sampling_covers_source_and_short_clips():
    from backend.app.quality_video import temporal_starts
    times=temporal_starts(120,'youtube')
    assert 1 <= len(times) <= 2
    assert all(0<=t<=116.5 for t in times)
    assert times == sorted(set(times))
    assert temporal_starts(3,'youtube')==[0.0]


def test_basil_expansion_preserves_subject_condition_drops_optional_location():
    from backend.app.retrieval_quality import expand_queries
    queries=expand_queries(['wilted basil balcony'],'image')
    assert queries[0]=='wilted basil balcony'
    assert 'wilted basil plant' in queries
    assert 'drooping basil plant' in queries


def test_borderline_visual_result_is_reviewable_not_missing_condition_rejected():
    from backend.app.retrieval_quality import QualityRanker
    class Visual:
        def rank(self,q,rows):return [dict(r,embedding_score=.54 if 'wilted' in q else .40) for r in rows]
    row=QualityRanker(Visual()).rank('wilted basil plant',[{'id':'b','title':'Basil plant','query':'wilted basil plant'}])[0]
    assert row['quality_state']=='needs_review'
    assert row['score']>=.42


def test_sequence_budget_preserves_all_shots_before_extra_alternatives():
    from backend.app.media_quality import balance_shots
    rows=[{'shot_id':s,'score':score} for s,score in [('plane',.9),('plane',.85),('bus',.8),('bus',.75),('ferry',.7)]]
    assert {r['shot_id'] for r in balance_shots(rows)[:4]}=={'plane','bus','ferry'}


def test_desktop_rail_is_scoped_scroll_with_mobile_fallback():
    from backend.app.curation_ui import render_curation_page
    page=render_curation_page()
    assert '.rail{position:sticky' in page
    assert '#phrases{overflow-y:auto' in page
    assert 'centerActiveBeat()' in page
    assert 'list.scrollTo(' in page and "scrollIntoView(" not in page


@pytest.mark.parametrize('counts,code',[
    ({'provider_configured':False},'provider_not_configured'),
    ({'requests_failed':1},'provider_request_failed'),
    ({},'zero_provider_hits'),
    ({'raw':8,'hd':0},'no_hd_candidates'),
    ({'raw':8,'hd':8,'preview_failed':8},'preview_download_failed'),
    ({'raw':8,'hd':8,'preview':8,'ranker_unavailable':True},'ranker_unavailable'),
    ({'raw':8,'hd':8,'preview':8,'duplicates':8},'duplicate_only'),
    ({'raw':8,'hd':8,'preview':8},'visually_rejected'),
    ({'raw':8,'clip_failed':2},'clip_localization_failed'),
])
def test_specific_empty_reasons(counts,code):
    from backend.app.retrieval_diagnostics import empty_reason
    assert empty_reason(counts)['code']==code


def test_fixed_media_bridge_forwards_ranges_without_exposing_target(monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace as NS
    from urllib.request import Request,urlopen
    import httpx
    from backend.app.range_media import range_media
    calls=[]
    @contextmanager
    def upstream(method,url,**kw):
        calls.append((url,kw['headers']))
        yield NS(status_code=206,headers={'Content-Length':'4','Content-Range':'bytes 100-103/200','Content-Type':'video/mp4'},raise_for_status=lambda:None,iter_bytes=lambda:iter([b'clip']))
    monkeypatch.setattr(httpx,'stream',upstream)
    with range_media('https://fixed.example/source') as url:
        assert 'fixed.example' not in url
        with urlopen(Request(url,headers={'Range':'bytes=100-103'})) as response:
            assert response.status==206 and response.read()==b'clip'
    assert calls==[('https://fixed.example/source',{'Range':'bytes=100-103'})]


@pytest.mark.parametrize('talking_head',[True,False])
def test_generic_title_is_not_rejection_but_actual_talking_head_is(talking_head):
    from backend.app.retrieval_quality import QualityRanker
    class Visual:
        def rank(self,q,rows):
            value=(.85 if talking_head else .2) if 'directly to camera' in q else .65
            return [dict(r,embedding_score=value) for r in rows]
    row=QualityRanker(Visual()).rank('passengers boarding airplane',[{'id':'v','kind':'video','title':'My travel vlog','query':'passengers boarding airplane'}])[0]
    assert (row['quality_state']=='rejected') is talking_head


def test_actual_simulation_frames_are_rejected_even_with_matching_subject():
    from backend.app.retrieval_quality import QualityRanker
    class Visual:
        def rank(self,q,rows):
            value=.85 if 'animated diagram' in q else .65
            return [dict(r,embedding_score=value) for r in rows]
    row=QualityRanker(Visual()).rank('passengers boarding airplane',[{'id':'v','kind':'video','title':'Boarding','query':'passengers boarding airplane'}])[0]
    assert row['quality_state']=='rejected'
    assert 'non-photographic frame evidence' in row['quality_reasons']


def test_boarding_requires_more_evidence_than_seated_passengers():
    from backend.app.retrieval_quality import QualityRanker
    class Visual:
        def rank(self,q,rows):
            value=.8 if 'sitting inside' in q else .6
            return [dict(r,embedding_score=value) for r in rows]
    row=QualityRanker(Visual()).rank('Passeggeri salgono su un aereo',[{'id':'v','kind':'video','query':'passengers boarding airplane'}])[0]
    assert row['quality_state']=='rejected'
    assert 'opposite action matches actual frames better' in row['quality_reasons']


def test_vehicle_or_empty_ramp_is_not_passenger_boarding():
    from backend.app.retrieval_quality import QualityRanker
    class Visual:
        def rank(self,q,rows):
            score=.85 if 'vehicles boarding' in q else .6
            return [dict(r,embedding_score=score) for r in rows]
    row=QualityRanker(Visual()).rank('passengers boarding ferry',[{'id':'f','kind':'video','query':'passengers boarding ferry'}])[0]
    assert row['quality_state']=='rejected'
