def test_variations_keep_subject_and_do_not_invent_places_or_wrong_viewpoint():
    from backend.app.social_variations import search_variants
    queries=['airport bus departing','shuttle bus driving','bus leaving terminal']
    rounds=[search_variants(queries,'bus pulling away at street level',i) for i in range(4)]
    assert len({tuple(r) for r in rounds})==4
    assert all('bus' in q and 'india' not in q and 'pov' not in q for r in rounds for q in r)
    assert any('pov' in q for q in search_variants(['bus window view'],'riding bus window view',3))

def test_variations_continue_after_third_round_without_clamping_to_last_query():
    from backend.app.social_variations import search_variants
    queries=['small passenger ferry crossing water','travelers boarding ferry']
    third=search_variants(queries,'small passenger ferry with luggage',3)
    fourth=search_variants(queries,'small passenger ferry with luggage',4)
    eleventh=search_variants(queries,'small passenger ferry with luggage',11)
    assert fourth != third
    assert eleventh != third
    assert all('ferry' in q for q in fourth + eleventh)

def test_merge_retains_twenty_four_social_alternatives():
    from backend.app.beat_research import merge_video_rows
    def row(start):return {'beat_id':'b','discovery_sources':[{'id':str(i),'source':'tiktok','source_page':f'https://tiktok.com/{i}'} for i in range(start,start+6)]}
    result=[]
    for start in (0,6,12,18):result=merge_video_rows(result,[row(start)],'b','append')
    assert len(result[0]['discovery_sources'])==24

def test_curation_surfaces_more_than_four_pages_of_accumulated_social_results():
    import json
    from backend.app.curation_artifacts import load_curation_run
    discoveries=[{
        'id':f'tt-{i}','provider_id':str(i),'source':'tiktok','source_page':f'https://tiktok.com/{i}',
        'title':f'Ferry {i}','orientation':'portrait','thumbnail_url':f'https://img/{i}.jpg'
    } for i in range(30)]
    files={
        'semantic-chunks.json':json.dumps([{'id':'beat','text':'ferry'}]),
        'online-candidates.json':json.dumps([{'beat_id':'beat:shot','parent_beat_id':'beat','discovery_sources':discoveries}]),
    }
    class MemoryPath:
        def __init__(self,name=''):self.name=name
        def __truediv__(self,name):return MemoryPath(name)
        def is_file(self):return self.name in files
        def read_text(self,encoding='utf-8'):return files[self.name]
    run=load_curation_run(MemoryPath())
    assert len([row for row in run.chunks[0].video_candidates if row.provider=='tiktok'])==30

def test_gallery_keeps_order_and_counts_only_successful_variations():
    import subprocess,shutil
    import pytest
    node=shutil.which('node')
    if not node:pytest.skip('Node not installed')
    subprocess.run([node,'tests/social_gallery_controller.cjs','backend/app/social_gallery.py'],check=True,capture_output=True)

def test_research_request_accepts_repeated_variations_and_per_shot_keywords():
    import pytest
    from pydantic import ValidationError
    from backend.app.curation_server import BeatResearchRequest
    r=BeatResearchRequest(mode='append',providers=['tiktok'],variation_round=37,query_overrides={'shot_02':'bus india pov'})
    assert r.query_overrides['shot_02']=='bus india pov'
    assert r.variation_round==37
    with pytest.raises(ValidationError):BeatResearchRequest(mode='append',variation_round=-1)

def test_append_excludes_known_candidates_before_shortlist():
    from backend.app.beat_research import existing_video_keys, unseen_video_candidates
    from types import SimpleNamespace as N
    rows=[{'parent_beat_id':'b','candidates':[{'provider':'tiktok','provider_id':'old'}], 'discovery_sources':[{'source':'tiktok','provider_id':'known'}]}, {'parent_beat_id':'other','candidates':[{'provider':'tiktok','provider_id':'new'}]}]
    keys=existing_video_keys(rows,'b')
    pool=[N(provider='tiktok',provider_id=i,source_page='') for i in ['old','known','new']]
    assert [c.provider_id for c in unseen_video_candidates(pool,keys)]==['new']
