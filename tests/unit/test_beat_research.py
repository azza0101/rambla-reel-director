def _video_row(beat, slot, candidates):
    return {
        "parent_beat_id": beat,
        "coverage_slot_id": slot,
        "beat_id": slot,
        "quality_version": "clip-quality-12",
        "candidates": candidates,
        "search_attempts": [{"provider": "youtube", "query": slot, "hits": len(candidates)}],
        "errors": [],
    }


def _candidate(asset_id, provider="youtube"):
    provider_id = asset_id.split(":", 1)[-1]
    return {"id": asset_id, "provider": provider, "source": provider, "provider_id": provider_id, "source_url": f"https://example/{provider_id}"}


def test_replace_video_rows_changes_only_target_beat():
    from backend.app.beat_research import merge_video_rows

    old = [_video_row("beat-a", "beat-a:shot:1", [_candidate("youtube:old")]), _video_row("beat-b", "beat-b:shot:1", [_candidate("youtube:keep")])]
    fresh = [_video_row("beat-a", "beat-a:shot:1", [_candidate("youtube:new")])]
    merged = merge_video_rows(old, fresh, "beat-a", "replace")

    assert [row["candidates"][0]["id"] for row in merged] == ["youtube:new", "youtube:keep"]
    assert next(row for row in merged if row["parent_beat_id"] == "beat-b") == old[1]


def test_append_video_rows_keeps_existing_and_adds_unique_candidates_and_round():
    from backend.app.beat_research import merge_video_rows

    old = [_video_row("beat-a", "beat-a:shot:1", [_candidate("youtube:old")])]
    old[0]["research_round"] = 1
    fresh = [_video_row("beat-a", "beat-a:shot:1", [_candidate("youtube:old"), _candidate("tiktok:new", "tiktok")])]
    merged = merge_video_rows(old, fresh, "beat-a", "append")
    row = merged[0]

    assert [item["id"] for item in row["candidates"]] == ["youtube:old", "tiktok:new"]
    assert row["research_round"] == 2
    assert len(row["search_attempts"]) == 2


def test_append_images_keeps_old_selection_candidates_and_dedupes():
    from backend.app.beat_research import merge_image_artifact

    old = {"schema_version": "retrieval-quality-10", "chunks": {
        "beat-a": {"candidates": [_candidate("pexels:old", "pexels")], "search_attempts": [{"query": "old", "hits": 1}], "research_round": 1},
        "beat-b": {"candidates": [_candidate("pexels:keep", "pexels")]},
    }}
    fresh = {"schema_version": "retrieval-quality-10", "chunks": {
        "beat-a": {"candidates": [_candidate("pexels:old", "pexels"), _candidate("pexels:new", "pexels")], "search_attempts": [{"query": "new", "hits": 2}]}
    }}
    merged = merge_image_artifact(old, fresh, "beat-a", "append")

    assert [item["id"] for item in merged["chunks"]["beat-a"]["candidates"]] == ["pexels:old", "pexels:new"]
    assert merged["chunks"]["beat-a"]["research_round"] == 2
    assert merged["chunks"]["beat-b"] == old["chunks"]["beat-b"]


def test_seen_candidate_keys_use_provider_identity_or_source_url():
    from backend.app.beat_research import seen_candidate_keys

    rows = [_candidate("youtube:abc"), {"id": "x", "source": "tiktok", "source_url": "https://tiktok.com/@a/video/1"}]
    keys = seen_candidate_keys(rows)
    assert "youtube:abc" in keys
    assert "url:https://tiktok.com/@a/video/1" in keys
