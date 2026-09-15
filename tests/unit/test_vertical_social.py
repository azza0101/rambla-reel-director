import pytest


def test_duckduckgo_social_link_extraction_is_provider_scoped():
    from backend.app.vertical_social import extract_search_links

    html = '''
    <a class="result__a" href="https://www.tiktok.com/@alice/video/1234567890">TikTok result</a>
    <a class="result__a" href="https://www.instagram.com/reel/ABC123/">Instagram result</a>
    <a class="result__a" href="https://example.com/not-social">Other</a>
    '''
    assert extract_search_links(html, "tiktok", limit=5) == ["https://www.tiktok.com/@alice/video/1234567890"]
    assert extract_search_links(html, "instagram", limit=5) == ["https://www.instagram.com/reel/ABC123/"]


def test_vertical_metadata_normalization_accepts_only_portrait_public_video():
    from backend.app.vertical_social import normalize_social_metadata

    row = normalize_social_metadata(
        "tiktok",
        "https://www.tiktok.com/@alice/video/1234567890",
        "passengers boarding ferry",
        {
            "id": "1234567890",
            "title": "Boarding the ferry",
            "uploader": "alice",
            "duration": 18,
            "width": 1080,
            "height": 1920,
            "thumbnail": "https://img.example/thumb.jpg",
        },
        provider_rank=0,
    )
    assert row.provider == "tiktok"
    assert row.orientation == "portrait"
    assert row.acquisition_mode == "bounded_window"
    assert row.rights_state == "review_required"


def test_vertical_metadata_normalization_rejects_landscape():
    from backend.app.vertical_social import normalize_social_metadata

    with pytest.raises(ValueError, match="portrait"):
        normalize_social_metadata(
            "instagram",
            "https://www.instagram.com/reel/ABC123/",
            "local guide travelers",
            {"id": "ABC123", "duration": 12, "width": 1920, "height": 1080, "thumbnail": "https://img.example/a.jpg"},
            provider_rank=0,
        )


@pytest.mark.asyncio
async def test_youtube_adapter_can_emit_youtube_shorts_provider_and_filter_portrait():
    from backend.app.youtube_source import YouTubeOnlineSourceAdapter, YouTubeSource

    async def discover(query, limit):
        return [
            {"id": "portrait", "title": "Short", "duration": 32, "width": 1080, "height": 1920, "thumbnail": "https://img.example/p.jpg"},
            {"id": "landscape", "title": "Wide", "duration": 32, "width": 1920, "height": 1080, "thumbnail": "https://img.example/l.jpg"},
        ]

    adapter = YouTubeOnlineSourceAdapter(YouTubeSource(discover=discover), provider_name="youtube_shorts", portrait_only=True)
    rows = await adapter.search("boarding plane", orientation=None, min_duration=1, max_duration=240, limit=5)
    assert [row.provider for row in rows] == ["youtube_shorts"]
    assert rows[0].orientation == "portrait"
