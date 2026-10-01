from backend.app.stock_export_media import preserve_selected_generics


def test_refresh_keeps_selected_generic_videos_even_when_search_results_change():
    old = {'selected':['7'], 'items':[{'provider_id':'7','title':'chosen'}, {'provider_id':'8'}]}
    assert preserve_selected_generics(old, [{'provider_id':'9'}]) == [
        {'provider_id':'7','title':'chosen'}, {'provider_id':'9'}]


def test_refresh_does_not_duplicate_a_selected_search_result():
    old = {'selected':['7'], 'items':[{'provider_id':'7','media_path':'download.mp4'}]}
    rows=preserve_selected_generics(old,[{'provider_id':'7'}, {'provider_id':'9'}])
    assert len(rows)==2 and rows[0]['media_path']=='download.mp4'
