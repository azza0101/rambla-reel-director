def test_variations_keep_subject_and_do_not_invent_places_or_wrong_viewpoint():
    from backend.app.social_variations import search_variants
    queries=['airport bus departing','shuttle bus driving','bus leaving terminal']
    rounds=[search_variants(queries,'bus pulling away at street level',i) for i in range(4)]
    assert len({tuple(r) for r in rounds})==4
    assert all('bus' in q and 'india' not in q and 'pov' not in q for r in rounds for q in r)
    assert any('pov' in q for q in search_variants(['bus window view'],'riding bus window view',3))

def test_merge_retains_twenty_four_social_alternatives():
    from backend.app.beat_research import merge_video_rows
    def row(start):return {'beat_id':'b','discovery_sources':[{'id':str(i),'source':'tiktok','source_page':f'https://tiktok.com/{i}'} for i in range(start,start+6)]}
    result=[]
    for start in (0,6,12,18):result=merge_video_rows(result,[row(start)],'b','append')
    assert len(result[0]['discovery_sources'])==24

def test_gallery_keeps_order_and_counts_only_successful_variations():
    import subprocess,shutil
    import pytest
    node=shutil.which('node')
    if not node:pytest.skip('Node not installed')
    subprocess.run([node,'tests/social_gallery_controller.cjs','backend/app/social_gallery.py'],check=True,capture_output=True)

def test_research_request_bounds_variations_and_accepts_per_shot_keywords():
    import pytest
    from pydantic import ValidationError
    from backend.app.curation_server import BeatResearchRequest
    r=BeatResearchRequest(mode='append',providers=['tiktok'],variation_round=3,query_overrides={'shot_02':'bus india pov'})
    assert r.query_overrides['shot_02']=='bus india pov'
    with pytest.raises(ValidationError):BeatResearchRequest(mode='append',variation_round=4)

def test_append_excludes_known_candidates_before_shortlist():
    from backend.app.beat_research import existing_video_keys, unseen_video_candidates
    from types import SimpleNamespace as N
    rows=[{'parent_beat_id':'b','candidates':[{'provider':'tiktok','provider_id':'old'}], 'discovery_sources':[{'source':'tiktok','provider_id':'known'}]}, {'parent_beat_id':'other','candidates':[{'provider':'tiktok','provider_id':'new'}]}]
    keys=existing_video_keys(rows,'b')
    pool=[N(provider='tiktok',provider_id=i,source_page='') for i in ['old','known','new']]
    assert [c.provider_id for c in unseen_video_candidates(pool,keys)]==['new']
