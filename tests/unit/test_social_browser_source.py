import asyncio


def test_extract_social_result_links_canonicalizes_and_dedupes():
    from backend.app.social_browser_source import extract_social_result_links

    tiktok = extract_social_result_links("tiktok", [
        {"href": "https://www.tiktok.com/@alice/video/123456?is_from_webapp=1", "text": "first"},
        {"href": "https://www.tiktok.com/@alice/video/123456", "text": "duplicate"},
        {"href": "https://www.tiktok.com/@alice", "text": "profile"},
    ])
    assert [row["source_page"] for row in tiktok] == ["https://www.tiktok.com/@alice/video/123456"]
    assert tiktok[0]["provider_id"] == "123456"

    instagram = extract_social_result_links("instagram", [
        {"href": "https://www.instagram.com/reel/ABC_123/?igsh=tracking", "text": "reel caption"},
        {"href": "https://www.instagram.com/p/PHOTO/", "text": "photo"},
    ])
    assert instagram[0]["source_page"] == "https://www.instagram.com/reel/ABC_123/"
    assert instagram[0]["provider_id"] == "ABC_123"


def test_browser_social_source_uses_profile_and_returns_portrait_candidates(tmp_path):
    from backend.app.social_browser_source import BrowserSocialSource

    class Page:
        url = "https://www.tiktok.com/search/video?q=elephants"
        calls = 0
        async def eval_on_selector_all(self, selector, _script):
            assert selector == "a[href]"
            self.calls += 1
            return [{
                "href": "https://www.tiktok.com/@wildlife/video/777",
                "text": "elephant sanctuary thailand",
                "aria": "",
                "img": "https://img.example/777.jpg",
            }]
        async def evaluate(self, _script):
            return None
        async def wait_for_timeout(self, _milliseconds):
            return None

    class Manager:
        def __init__(self): self.calls = []
        async def run_in_profile(self, provider, callback, *, start_url=None):
            self.calls.append((provider, start_url))
            return await callback(Page(), object())

    manager = Manager()
    source = BrowserSocialSource("tiktok", manager)
    rows = asyncio.run(source.search(
        "elephant sanctuary thailand", orientation="portrait",
        min_duration=1, max_duration=300, limit=3,
    ))

    assert manager.calls and manager.calls[0][0] == "tiktok"
    assert "search/video" in manager.calls[0][1]
    assert len(rows) == 1
    assert rows[0].provider == "tiktok"
    assert rows[0].provider_id == "777"
    assert rows[0].orientation == "portrait"
    assert rows[0].preview_url == "https://img.example/777.jpg"


def test_browser_social_source_falls_back_when_browser_fails():
    from backend.app.social_browser_source import BrowserSocialSource
    from backend.app.vertical_social import VerticalRemoteCandidate

    class Manager:
        async def run_in_profile(self, *_args, **_kwargs):
            raise RuntimeError("login wall")

    class Fallback:
        provider_name = "tiktok"
        async def search(self, query, **_kwargs):
            return [VerticalRemoteCandidate(
                provider="tiktok", provider_id="fallback", query=query,
                source_page="https://www.tiktok.com/@x/video/fallback",
                creator_name="x", creator_page=None, title="fallback", description="fallback",
                duration=8, width=1080, height=1920, orientation="portrait",
                preview_url="https://img.example/fallback.jpg",
                selected_rendition_url="https://www.tiktok.com/@x/video/fallback",
                rendition_width=1080, rendition_height=1920,
                rights_state="review_required", provider_rank=0,
            )]

    source = BrowserSocialSource("tiktok", Manager(), fallback=Fallback())
    rows = asyncio.run(source.search("news event", orientation=None, min_duration=1, max_duration=300, limit=3))
    assert [row.provider_id for row in rows] == ["fallback"]
    assert source.last_attempt["fallback_used"] is True
    assert source.last_attempt["browser_error"] == "RuntimeError"


def test_vertical_factory_upgrades_tiktok_instagram_to_browser_sources(monkeypatch, tmp_path):
    from backend.app.social_browser_source import BrowserSocialSource
    from backend.app.vertical_social import build_default_vertical_sources

    monkeypatch.setenv("RAMBLA_ENABLE_SOCIAL_BROWSER", "1")
    monkeypatch.setenv("RAMBLA_BROWSER_PROFILE_ROOT", str(tmp_path / "profiles"))
    sources = build_default_vertical_sources()
    assert [source.provider_name for source in sources] == ["youtube_shorts", "tiktok", "instagram"]
    assert isinstance(sources[1], BrowserSocialSource)
    assert isinstance(sources[2], BrowserSocialSource)
    assert sources[1].fallback.provider_name == "tiktok"
    assert sources[2].fallback.provider_name == "instagram"


def test_real_engine_youtube_adapter_actually_searches_vertical_sources(monkeypatch, tmp_path):
    import backend.app.online_sourcing_cli as cli
    from backend.app.vertical_social import VerticalRemoteCandidate

    monkeypatch.setattr(cli, "create_retrieval_ranker", lambda *_args, **_kwargs: object())
    monkeypatch.setenv("RAMBLA_ENABLE_VERTICAL_SOCIAL", "1")
    engine = cli._real_engine(
        client_id="test", pexels_api_key=None, model_root=tmp_path,
        embedding_code_root=None, cache_root=tmp_path / "cache", max_candidates=4,
    )
    adapter = engine.sources[0]

    async def no_youtube(*_args, **_kwargs):
        return []
    adapter.source.search = no_youtube

    class FakeVertical:
        provider_name = "tiktok"
        last_attempt = {"provider": "tiktok", "hits": 1}
        async def search(self, query, **_kwargs):
            return [VerticalRemoteCandidate(
                provider="tiktok", provider_id="vertical", query=query,
                source_page="https://www.tiktok.com/@x/video/vertical",
                creator_name="x", creator_page=None, title="vertical", description="vertical",
                duration=8, width=1080, height=1920, orientation="portrait",
                preview_url="https://img.example/vertical.jpg",
                selected_rendition_url="https://www.tiktok.com/@x/video/vertical",
                rendition_width=1080, rendition_height=1920,
                rights_state="review_required", provider_rank=0,
            )]
    adapter.vertical_sources = [FakeVertical()]
    rows = asyncio.run(adapter.search(
        "event", orientation=None, min_duration=1, max_duration=300, limit=3,
    ))
    assert [row.provider for row in rows] == ["tiktok"]


def test_real_engine_provider_filter_builds_social_only_adapter(monkeypatch, tmp_path):
    import backend.app.online_sourcing_cli as cli

    monkeypatch.setattr(cli, "create_retrieval_ranker", lambda *_args, **_kwargs: object())
    engine = cli._real_engine(
        client_id="test",
        pexels_api_key="pexels-key",
        model_root=tmp_path,
        embedding_code_root=None,
        cache_root=tmp_path / "cache",
        max_candidates=4,
        providers={"tiktok", "instagram"},
    )

    assert len(engine.sources) == 1
    adapter = engine.sources[0]
    assert adapter.include_base_youtube is False
    assert [source.provider_name for source in adapter.vertical_sources] == ["tiktok", "instagram"]
