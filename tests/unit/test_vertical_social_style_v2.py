def test_vertical_social_search_adds_phone_native_style_variants_without_losing_exact_query():
    from backend.app.vertical_social import social_search_phrases

    phrases = social_search_phrases("elephant sanctuary thailand")
    assert phrases[0] == "elephant sanctuary thailand"
    assert any("pov" in value.casefold() for value in phrases)
    assert any("iphone" in value.casefold() or "phone" in value.casefold() for value in phrases)
    assert len(phrases) <= 4


def test_vertical_social_candidates_are_marked_high_authenticity():
    from backend.app.vertical_social import normalize_social_metadata

    row = normalize_social_metadata(
        "instagram",
        "https://www.instagram.com/reel/ABC123/",
        "awkward silence people",
        {
            "id": "ABC123",
            "title": "quiet moment",
            "duration": 10,
            "width": 1080,
            "height": 1920,
            "thumbnail": "https://img.example/a.jpg",
        },
        provider_rank=0,
    )
    assert row.source_authenticity is not None
    assert row.source_authenticity >= .9


def test_vertical_social_final_gate_uses_real_clip_dimensions(monkeypatch):
    import backend.app.quality_video as quality

    monkeypatch.setattr(quality, "probe_preview", lambda _path: {
        "playable": True, "duration": 3.5, "mime": "video/mp4",
        "width": 360, "height": 640,
    })
    assert quality._verified_portrait_clip({"preview_path": "portrait.mp4"}) is True

    monkeypatch.setattr(quality, "probe_preview", lambda _path: {
        "playable": True, "duration": 3.5, "mime": "video/mp4",
        "width": 640, "height": 360,
    })
    assert quality._verified_portrait_clip({"preview_path": "landscape.mp4"}) is False


def test_mixed_video_providers_keep_a_budget_per_provider_before_curation_shelves():
    from backend.app.media_quality import diverse_candidates

    rows = [
        {"id": f"short-{i}", "kind": "video", "source": "youtube_shorts", "source_page": f"https://youtube.test/short/{i}"}
        for i in range(3)
    ] + [
        {"id": f"tik-{i}", "kind": "video", "source": "tiktok", "source_page": f"https://tiktok.test/video/{i}"}
        for i in range(3)
    ]
    selected, rejected = diverse_candidates(rows, [], limit=3)
    assert len(selected) == 6
    assert rejected == 0
    assert {row["source"] for row in selected} == {"youtube_shorts", "tiktok"}


def test_social_browser_error_is_promoted_to_visible_video_error():
    import asyncio
    from backend.app.quality_video import source_video_beat

    class Source:
        provider_name = "youtube"
        def drain_vertical_attempts(self):
            return [{
                "provider": "tiktok",
                "query": "ethical travel",
                "hits": 0,
                "browser_error": "ModuleNotFoundError",
                "fallback_used": True,
            }]

    class Ranker:
        warning = None

    class Engine:
        sources = [Source()]
        query_intents = {}
        ranker = Ranker()
        async def _search_one(self, source, query, **kwargs):
            return [], None

    result = asyncio.run(source_video_beat(
        Engine(),
        beat_id="beat-1",
        client_id="rambla",
        queries=["ethical travel"],
        min_duration=1,
        max_duration=15,
        orientation="portrait",
    ))
    assert any(
        row.get("provider") == "tiktok"
        and row.get("error_type") == "ModuleNotFoundError"
        for row in result["errors"]
    )
