import asyncio


def test_envato_parser_extracts_clickable_stock_video_cards():
    from backend.app.envato_source import parse_envato_search_html

    html = """
    <a href="/elephant-eating-at-an-elephant-sanctuary-in-chiang-YAJZNPQ">
      <img src="https://assets.example/thumb.jpg"
           alt="Elephant eating at an Elephant sanctuary in Chiang Mai, Thailand">
    </a>
    <a href="/stock-video/elephant+eating"><img src="https://assets.example/search.jpg" alt="search"></a>
    """
    rows = parse_envato_search_html(html, limit=3)

    assert rows == [{
        "source_page": "https://elements.envato.com/elephant-eating-at-an-elephant-sanctuary-in-chiang-YAJZNPQ",
        "title": "Elephant eating at an Elephant sanctuary in Chiang Mai, Thailand",
        "preview_url": "https://assets.example/thumb.jpg",
        "alt": "Elephant eating at an Elephant sanctuary in Chiang Mai, Thailand",
    }]


def test_envato_source_returns_preview_only_search_candidates():
    from backend.app.envato_source import EnvatoSource

    async def discover(query, limit):
        assert query == "elephant sanctuary thailand"
        assert limit >= 3
        return [{
            "source_page": "https://elements.envato.com/elephant-eating-at-an-elephant-sanctuary-in-chiang-YAJZNPQ",
            "title": "Elephant eating at a sanctuary in Thailand",
            "preview_url": "https://assets.example/thumb.jpg",
        }]

    rows = asyncio.run(EnvatoSource(discover=discover).search(
        "elephant sanctuary thailand",
        orientation=None,
        min_duration=1,
        max_duration=240,
        limit=3,
    ))

    assert len(rows) == 1
    row = rows[0]
    assert row.provider == "envato"
    assert row.acquisition_mode == "manual_link"
    assert row.rights_state == "subscription_license_required"
    assert row.source_page.startswith("https://elements.envato.com/")


def test_envato_current_item_and_multiword_search_urls():
    from backend.app.envato_source import _clean_item_url, _search_url

    assert _clean_item_url(
        "https://elements.envato.com/thai-temple-bangkok-thailand-FAE79PS"
    ) == "https://elements.envato.com/thai-temple-bangkok-thailand-FAE79PS"
    assert _search_url("elephant sanctuary thailand").endswith(
        "/stock-video/elephant%2Bsanctuary%2Bthailand"
    )


def test_envato_source_background_search_is_profile_independent():
    import backend.app.envato_source as module

    source = module.EnvatoSource(discover=lambda *_args: [])
    assert source.profile_dir is None
    assert source._context is None
