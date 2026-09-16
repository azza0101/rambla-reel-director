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
