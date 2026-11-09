import asyncio


def test_app_search_parses_cards_in_site_order_and_keeps_item_url():
    from backend.app.envato_source import parse_app_search_html
    html = '''<a data-analytics-context-detail="search-results" data-analytics-item_title="Duman spring" href="/search/stock-video/ef3e0d6b-dd08-42ee-ad49-3d8a0b0c897e?term=livno"><img src="https://images.example/test.jpg"></a>'''
    rows = parse_app_search_html(html, limit=30)
    assert len(rows) == 1
    assert rows[0]['title'] == 'Duman spring'
    assert rows[0]['source_page'].startswith('https://app.envato.com/search/stock-video/ef3e0d6b')


def test_app_items_are_accepted_by_search():
    from backend.app.envato_source import EnvatoSource
    async def discover(query, limit):
        return [{'title': 'Duman', 'source_page': 'https://app.envato.com/search/stock-video/ef3e0d6b-dd08-42ee-ad49-3d8a0b0c897e', 'preview_url': 'https://images.example/test.jpg'}]
    source = EnvatoSource(discover=discover)
    rows = asyncio.run(source.search('livno', orientation=None, min_duration=2, max_duration=60, limit=30))
    assert len(rows) == 1
