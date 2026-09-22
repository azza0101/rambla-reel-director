from backend.app.curation import CurationCandidate, build_candidate_shelf


def c(asset_id: str, kind: str, score: float, source: str) -> CurationCandidate:
    return CurationCandidate(
        asset_id=asset_id, chunk_id="chunk-1", kind=kind, provider="test",
        source_page=source, title=asset_id, description="", score=score,
        rights_state="review_required", orientation="landscape",
        source_start_seconds=10.0 if kind == "video" else None,
        source_end_seconds=12.5 if kind == "video" else None,
    )


def test_shelf_caps_and_orders():
    rows = [*(c(f"v{i}", "video", 1-i/10, f"https://v/{i}") for i in range(5)),
            *(c(f"i{i}", "image", 1-i/10, f"https://i/{i}") for i in range(6))]
    shelf = build_candidate_shelf(rows)
    assert [x.asset_id for x in shelf.video] == ["v0", "v1", "v2"]
    assert [x.asset_id for x in shelf.images] == ["i0", "i1", "i2", "i3"]


def test_shelf_dedupes_same_source_and_never_invents_fillers():
    shelf = build_candidate_shelf([
        c("a", "video", .9, "https://same"),
        c("b", "video", .8, "https://same"),
        c("c", "video", .7, "https://other"),
    ])
    assert [x.asset_id for x in shelf.video] == ["a", "c"]
    assert shelf.images == ()


def test_envato_discovery_candidate_survives_aggregate_video_shelf():
    row = CurationCandidate(
        asset_id="envato:abc",
        chunk_id="chunk-1",
        kind="video",
        provider="envato",
        source_page="https://elements.envato.com/example-ABCDEFG",
        title="Example Envato clip",
        description="Example Envato clip",
        score=.7,
        rights_state="subscription_license_required",
        orientation="landscape",
        preview_status="preview_pending",
        preview_url="https://assets.example/thumb.jpg",
        clip_verified=False,
    )
    shelf = build_candidate_shelf([row])
    assert [item.provider for item in shelf.video] == ["envato"]
    assert shelf.video[0].source_page == "https://elements.envato.com/example-ABCDEFG"
