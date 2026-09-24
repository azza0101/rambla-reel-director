import pytest

from backend.app.curation import CurationCandidate, build_candidate_shelf


@pytest.mark.parametrize('provider', ['tiktok', 'instagram', 'youtube_shorts'])
def test_six_social_results_are_kept_and_shots_covered_before_alternatives(provider):
    rows = [CurationCandidate(str(i),'beat','video',provider,f'https://example.com/{provider}/{i}',
            'Wing over clouds','',1-i/100,'review_required','portrait',shot_id='first' if i<6 else 'second') for i in range(8)]
    shelf = build_candidate_shelf(rows, social_limit=6)
    assert len(shelf.vertical_social) == 6
    assert {r.shot_id for r in shelf.vertical_social} == {'first','second'}
