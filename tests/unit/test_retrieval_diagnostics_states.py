from backend.app.retrieval_diagnostics import image_diagnostic, video_diagnostic


def _versions():
    from backend.app.quality_video import QUALITY_VERSION as VIDEO
    from backend.app.retrieval_quality import VERSION as IMAGE
    return VIDEO, IMAGE


def test_missing_image_artifact_is_not_reported_as_provider_zero_hits():
    result = image_diagnostic({})
    assert result["code"] == "not_searched"
    assert result["counts"]["raw"] == 0
    assert result["counts"]["hd"] == 0
    assert result["counts"]["preview"] == 0


def test_missing_video_rows_are_not_reported_as_provider_zero_hits():
    result = video_diagnostic([], "youtube")
    assert result["code"] == "not_searched"
    assert result["counts"]["raw"] == 0
    assert result["counts"]["attempts"] == 0
    assert "hd" not in result["counts"]
    assert "preview" not in result["counts"]


def test_zero_provider_hits_requires_an_actual_search_attempt():
    video_version, _ = _versions()
    rows = [{"quality_version": video_version, "search_attempts": [{"provider": "YouTubeOnlineSourceAdapter", "query": "traveler comparing routes map", "hits": 0}], "candidates": [], "errors": []}]
    result = video_diagnostic(rows, "youtube")
    assert result["code"] == "zero_provider_hits"


def test_image_zero_provider_hits_requires_an_actual_search_attempt():
    _, image_version = _versions()
    row = {"quality_version": image_version, "status": "searched", "search_attempts": [{"provider": "PexelsPhotoSource", "query": "wilted basil plant", "hits": 0}], "counts": {"raw": 0, "hd": 0, "preview": 0, "rejected": 0, "duplicates": 0, "requests_failed": 0}, "candidates": []}
    result = image_diagnostic(row)
    assert result["code"] == "zero_provider_hits"


def test_stale_image_row_is_not_presented_as_current_search_result():
    row = {"quality_version": "retrieval-quality-8", "search_attempts": [{"provider": "PexelsPhotoSource", "query": "old query", "hits": 7}], "counts": {"raw": 7, "hd": 7, "preview": 7}, "candidates": []}
    assert image_diagnostic(row)["code"] == "not_searched"


def test_route_comparison_query_gets_searchable_retrieval_aliases():
    from backend.app.retrieval_quality import expand_queries
    variants = expand_queries(["traveler comparing routes map"], "video")
    assert variants[0] == "traveler comparing routes map"
    assert "travel planning map" in variants
    assert "route planning map" in variants


def test_transport_queries_get_provider_friendly_aliases():
    from backend.app.retrieval_quality import expand_queries
    plane = expand_queries(["passengers boarding airplane"], "video")
    ferry = expand_queries(["passengers boarding ferry"], "video")
    assert "people boarding plane" in plane
    assert "people boarding boat" in ferry


def test_search_relaxes_nonessential_travel_modifiers():
    from backend.app.retrieval_quality import expand_queries
    variants = expand_queries(["custom travel itinerary planning"], "image")
    assert "travel itinerary planning" in variants
    assert "travel planning map" in variants


def test_stock_query_rounds_become_simpler_and_change_each_time():
    from backend.app.retrieval_quality import provider_video_variants

    queries = ["person checking dry skin on foot", "candid hand rubbing foot callus"]
    target = "a person sits on a bed or sofa and looks down at the side of their foot near a small dry patch"
    first = provider_video_variants(queries, target, 1)
    second = provider_video_variants(queries, target, 2)
    assert first[0] == "dry skin foot"
    assert "person" not in first[0]
    assert second[0] != first[0]
    assert any("foot" in query for query in second)
    assert all("sits bed" not in query for query in second)


def test_later_stock_rounds_switch_to_the_shared_concrete_keyword():
    from backend.app.retrieval_quality import provider_video_variants

    queries = [
        "opening small bathroom door",
        "phone shot home bathroom sink",
        "walking into bathroom door",
    ]
    target = "a small residential bathroom entrance with a sink, mirror and towel"

    assert provider_video_variants(queries, target, 1)[0] == "bathroom door"
    assert provider_video_variants(queries, target, 3)[0] == "bathroom"
    assert provider_video_variants(queries, target, 4)[0] == "bathroom interior"


def test_keyword_fallback_comes_from_director_queries_not_verbose_target_props():
    from backend.app.retrieval_quality import provider_video_variants

    variants = provider_video_variants(
        ["opening small bathroom door"],
        "ordinary bathroom with sink, mirror, towel and no luxury hotel styling",
        3,
    )

    assert variants[0] == "bathroom"
    assert all("mirror" not in query and "towel" not in query for query in variants)


def test_later_stock_round_prefers_scene_location_over_repeated_prop():
    from backend.app.retrieval_quality import provider_video_variants

    variants = provider_video_variants(
        [
            "closing bathroom mirror cabinet",
            "hand shutting medicine cabinet door",
            "phone shot closing bathroom cabinet",
        ],
        "ordinary private bathroom with a mirror cabinet",
        3,
    )

    assert variants[0] == "bathroom"


def test_pexels_basic_query_can_surface_a_concrete_source_for_manual_review():
    from types import SimpleNamespace
    from backend.app.quality_video import _discovery_relevant

    intent = "person casually checking a dry patch on the side of a foot"
    foot = SimpleNamespace(provider="pexels", query="dry skin foot", title="close up video of a foot", description="")
    soap = SimpleNamespace(provider="pexels", query="dry skin foot", title="person holding a soap", description="")
    assert _discovery_relevant(foot, intent) is True
    assert _discovery_relevant(soap, intent) is False


def test_video_retrieval_version_changes_when_localization_contract_changes():
    from backend.app.quality_video import QUALITY_VERSION
    assert QUALITY_VERSION == "clip-quality-15-social"


def test_contextual_image_retrieval_version_is_current():
    from backend.app.retrieval_quality import VERSION
    assert VERSION == "retrieval-quality-10"


def test_stale_retrieval_artifacts_do_not_drive_current_diagnostics():
    from backend.app.retrieval_diagnostics import current_image_chunks, current_video_rows
    video_version, image_version = _versions()
    stale_video = [{"quality_version": "clip-quality-10", "parent_beat_id": "b1", "search_attempts": [{"hits": 9}]}]
    current_video = [{"quality_version": video_version, "parent_beat_id": "b1", "search_attempts": [{"hits": 1}]}]
    assert current_video_rows(stale_video) == []
    assert current_video_rows(current_video) == current_video
    stale_images = {"schema_version": "retrieval-quality-9", "chunks": {"b1": {"raw_count": 8}}}
    current_images = {"schema_version": image_version, "chunks": {"b1": {"raw_count": 1}}}
    assert current_image_chunks(stale_images) == {}
    assert current_image_chunks(current_images) == current_images["chunks"]


def test_manual_discovery_result_keeps_pexels_available_without_ranker():
    from backend.app.retrieval_diagnostics import video_diagnostic

    result = video_diagnostic([{
        "quality_version": _versions()[0],
        "search_attempts": [{"provider": "pexels", "query": "egypt ruins", "hits": 12}],
        "candidates": [],
        "discovery_sources": [{"id": "pexels:42", "source": "pexels", "title": "Egyptian ruins"}],
        "ranking_warning": "ranker unavailable",
        "rejected_candidates": [],
    }], "pexels")

    assert result["code"] == "available"
    assert result["counts"]["accepted"] == 1
