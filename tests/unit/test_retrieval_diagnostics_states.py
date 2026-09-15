from backend.app.retrieval_diagnostics import image_diagnostic, video_diagnostic


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
    rows = [{"search_attempts": [{"provider": "YouTubeOnlineSourceAdapter", "query": "traveler comparing routes map", "hits": 0}], "candidates": [], "errors": []}]
    result = video_diagnostic(rows, "youtube")
    assert result["code"] == "zero_provider_hits"


def test_image_zero_provider_hits_requires_an_actual_search_attempt():
    row = {"status": "searched", "search_attempts": [{"provider": "PexelsPhotoSource", "query": "wilted basil plant", "hits": 0}], "counts": {"raw": 0, "hd": 0, "preview": 0, "rejected": 0, "duplicates": 0, "requests_failed": 0}, "candidates": []}
    result = image_diagnostic(row)
    assert result["code"] == "zero_provider_hits"


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


def test_video_retrieval_version_changes_when_localization_contract_changes():
    from backend.app.quality_video import QUALITY_VERSION

    assert QUALITY_VERSION == "clip-quality-9"


def test_stale_retrieval_artifacts_do_not_drive_current_diagnostics():
    from backend.app.retrieval_diagnostics import current_image_chunks, current_video_rows

    stale_video = [{"quality_version": "clip-quality-8", "parent_beat_id": "b1", "search_attempts": [{"hits": 9}]}]
    current_video = [{"quality_version": "clip-quality-9", "parent_beat_id": "b1", "search_attempts": [{"hits": 1}]}]
    assert current_video_rows(stale_video) == []
    assert current_video_rows(current_video) == current_video

    stale_images = {"schema_version": "retrieval-quality-8", "chunks": {"b1": {"raw_count": 8}}}
    current_images = {"schema_version": "retrieval-quality-9", "chunks": {"b1": {"raw_count": 1}}}
    assert current_image_chunks(stale_images) == {}
    assert current_image_chunks(current_images) == current_images["chunks"]
