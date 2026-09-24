from backend.app.vertical_social import _thumbnail

def test_portrait_thumbnail_preferred_over_landscape_cover():
    assert _thumbnail({'thumbnail':'https://x/wide.jpg','thumbnails':[
        {'url':'https://x/wide.jpg','width':1280,'height':720},
        {'url':'https://x/portrait.jpg','width':360,'height':640}]}) == 'https://x/portrait.jpg'
