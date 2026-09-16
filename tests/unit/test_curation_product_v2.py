from backend.app.curation import CurationCandidate, build_candidate_shelf


def _candidate(asset_id, provider, score, *, kind="video", orientation="portrait"):
    return CurationCandidate(
        asset_id=asset_id,
        chunk_id="beat-1",
        kind=kind,
        provider=provider,
        source_page=f"https://example.test/{asset_id}",
        title=asset_id,
        description="",
        score=score,
        rights_state="review_required",
        orientation=orientation,
        preview_status="ready" if kind == "video" else "ready",
        clip_verified=kind == "video",
    )


def test_curation_shelf_preserves_vertical_social_before_general_youtube():
    shelf = build_candidate_shelf([
        _candidate("yt-high", "youtube", .95, orientation="landscape"),
        _candidate("tt", "tiktok", .82),
        _candidate("short", "youtube_shorts", .80),
        _candidate("ig", "instagram", .79),
        _candidate("stock", "pexels", .90, orientation="landscape"),
    ])

    assert [row.provider for row in shelf.vertical_social] == ["tiktok", "youtube_shorts", "instagram"]
    assert [row.provider for row in shelf.general_social] == ["youtube"]
    assert [row.provider for row in shelf.stock] == ["pexels"]
    assert [row.provider for row in shelf.video[:3]] == ["tiktok", "youtube_shorts", "instagram"]


def test_curation_page_exposes_real_project_file_and_vertical_social_controls():
    from backend.app.curation_ui import render_curation_page

    html = render_curation_page("test")
    assert "OPEN PROJECT FILE" in html
    assert "SAVE PROJECT FILE" in html
    assert "project.rambla.json" in html
    assert "SOCIAL / SHORTS / REELS" in html
    assert "youtube_shorts" in html
    assert "tiktok" in html
    assert "instagram" in html


def test_curation_page_project_file_loads_by_project_id_without_analyze():
    from backend.app.curation_ui import render_curation_page

    html = render_curation_page("test")
    assert "schema_version==='rambla-project-1'" in html
    assert "await api(`/projects/${payload.project_id}`)" in html
    assert "Project file loaded" in html
