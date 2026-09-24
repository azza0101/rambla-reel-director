import asyncio


def test_current_tiktok_grid_is_recognized_without_inbox_links():
    from backend.app.browser_profiles import _DumpDomPage
    html = '''<html><body>
    <div data-e2e="inbox-list-item"><a href="/@private/video/111">notification</a></div>
    <main id="grid-main"><div data-e2e="search_video-item-list">
    <div data-e2e="search_video-item"><a href="/@travel/video/222"><img src="https://example.org/wing.jpg">Airplane wing</a></div>
    </div></main></body></html>'''
    page = _DumpDomPage(html, 'https://www.tiktok.com/search/video?q=airplane')
    rows = asyncio.run(page.search_result_anchors('tiktok'))
    assert [row['href'] for row in rows] == ['https://www.tiktok.com/@travel/video/222']


def test_live_extractor_uses_description_instead_of_like_counter():
    import json
    import subprocess
    from backend.app.social_browser_source import _page_anchors

    class Page:
        async def eval_on_selector_all(self, selector, script):
            fixture = '''const image={alt:'Airplane wing over clouds',currentSrc:'https://example.org/wing.jpg'};
const card={innerText:'44.9K',querySelector:()=>image};
const anchor={href:'https://www.tiktok.com/@travel/video/222',closest:()=>card,getAttribute:()=>null};
'''
            result = subprocess.run(['node', '-e', fixture+'console.log(JSON.stringify(('+script+')([anchor])));'], capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
    rows = asyncio.run(_page_anchors(Page(), 'tiktok', search_only=True))
    assert rows[0]['text'] == 'Airplane wing over clouds'
    assert rows[0]['img'] == 'https://example.org/wing.jpg'
