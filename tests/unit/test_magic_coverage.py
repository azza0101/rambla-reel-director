import pytest


def test_shortlist_deduplicates_sources_and_rejects_wrong_country():
    from backend.app.magic_coverage import shortlist_candidates
    rows = [
        dict(asset_id='a', source_page='https://x/1', title='Egypt tourist police', provider='pexels'),
        dict(asset_id='b', source_page='https://x/1', title='Egypt police', provider='youtube_shorts'),
        dict(asset_id='c', source_page='https://x/2', title='American police United States', provider='pexels'),
        dict(asset_id='d', source_page='https://x/3', title='Egypt street', provider='pexels'),
    ]
    assert [r['asset_id'] for r in shortlist_candidates(rows, 'tourist police Egypt', ['Egypt'], limit=6)] == ['a']


def test_shortlist_rejects_a_specific_unrelated_airport():
    from backend.app.magic_coverage import shortlist_candidates
    rows = [dict(asset_id='changi', source_page='https://x/changi',
                 title='Changi airport immigration area overview', provider='pexels')]
    assert shortlist_candidates(rows, 'airport immigration passport Italy', ['Italy'], limit=6) == []


def test_metadata_and_poster_alone_cannot_verify_video():
    from backend.app.magic_coverage import validated_verdicts
    rows = [dict(asset_id='a', kind='video', sampled_frames=['one.jpg'])]
    response = {'verdicts': [dict(asset_id='a', coherent=True, confidence=99, reason='good') ]}
    assert validated_verdicts(rows, response)['a']['verdict'] == 'uncertain'
    rows[0]['sampled_frames'] = ['one.jpg', 'two.jpg', 'three.jpg']
    assert validated_verdicts(rows, response)['a']['verdict'] == 'verified'
    assert validated_verdicts(rows, None)['a']['verdict'] == 'uncertain'


def test_unknown_duplicate_or_incomplete_judge_reply_is_rejected():
    from backend.app.magic_coverage import validated_verdicts
    rows = [dict(asset_id='a', kind='image', sampled_frames=['one.jpg'])]
    with pytest.raises(ValueError):
        validated_verdicts(rows, {'verdicts': [dict(asset_id='other', coherent=True, confidence=90, reason='x')]})
    with pytest.raises(ValueError):
        validated_verdicts(rows, {'verdicts': []})


def test_research_queries_are_bounded_and_contextual():
    from backend.app.magic_coverage import research_queries
    assert research_queries(['police', 'police', 'tourist police', 'officers'], ['Egypt'], limit=2) == ['police Egypt', 'tourist police Egypt']
