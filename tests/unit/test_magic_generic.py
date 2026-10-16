def test_generic_candidates_respect_place_and_cannot_replace_specific_subject():
    from backend.app.magic_product import generic_candidates
    items=[dict(provider_id='1',title='Egypt Nile landscape',description='',source_page='https://pexels.com/video/1'),
           dict(provider_id='2',title='Thailand city',description='',source_page='https://pexels.com/video/2')]
    beat=dict(id='b',text='Nile landscape in Egypt',places=['Egypt'])
    rows=generic_candidates(beat,items)
    assert [r['asset_id'] for r in rows]==['b--pexels:1']
    assert rows[0]['role']=='generic'
    assert generic_candidates({**beat,'text':'Egypt tourist police'},items)==[]
