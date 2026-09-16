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
