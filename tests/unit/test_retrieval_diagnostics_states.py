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
    assert result["counts"]["hd"] == 0
    assert result["counts"]["preview"] == 0


def test_zero_provider_hits_requires_an_actual_search_attempt():
    rows = [{"search_attempts": [{"provider": "YouTubeOnlineSourceAdapter", "query": "traveler comparing routes map", "hits": 0}], "candidates": [], "errors": []}]
    result = video_diagnostic(rows, "youtube")
    assert result["code"] == "zero_provider_hits"


def test_image_zero_provider_hits_requires_an_actual_search_attempt():
    row = {"status": "searched", "search_attempts": [{"provider": "PexelsPhotoSource", "query": "wilted basil plant", "hits": 0}], "counts": {"raw": 0, "hd": 0, "preview": 0, "rejected": 0, "duplicates": 0, "requests_failed": 0}, "candidates": []}
    result = image_diagnostic(row)
    assert result["code"] == "zero_provider_hits"
