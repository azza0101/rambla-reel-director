import asyncio


def test_extract_google_video_results_unwraps_targets_and_keeps_preview():
    from backend.app.web_video_source import extract_google_video_results

    rows = extract_google_video_results([
        {
            "href": "https://www.google.com/url?q=https%3A%2F%2Fnews.example%2Fvideo%2Fstory&sa=U",
            "text": "Breaking story eyewitness video",
            "img": "https://encrypted-tbn0.gstatic.com/images?q=tbn:one",
            "img_width": 320,
            "img_height": 180,
        },
        {
            "href": "https://www.youtube.com/shorts/abc123",
            "text": "vertical eyewitness clip",
            "img": "https://i.ytimg.com/vi/abc123/hqdefault.jpg",
            "img_width": 180,
            "img_height": 320,
        },
        {"href": "https://www.google.com/search?q=ignore", "text": "internal", "img": ""},
    ], limit=10)

    assert [row["source_page"] for row in rows] == [
        "https://news.example/video/story",
        "https://www.youtube.com/shorts/abc123",
    ]
    assert rows[0]["preview_url"].startswith("https://encrypted-tbn0.gstatic.com/")
    assert rows[1]["orientation"] == "portrait"


def test_google_video_source_returns_manual_capable_candidates():
    from backend.app.web_video_source import WebVideoSource

    async def discover(query, limit):
        assert query == "rome protest eyewitness"
        assert limit >= 3
        return [{
            "source_page": "https://news.example/video/42",
            "title": "Eyewitness phone video from Rome",
            "preview_url": "https://img.example/42.jpg",
            "orientation": "unknown",
        }]

    source = WebVideoSource(discover=discover)
    rows = asyncio.run(source.search(
        "rome protest eyewitness", orientation="portrait",
        min_duration=1, max_duration=300, limit=3,
    ))
    assert len(rows) == 1
    assert rows[0].provider == "web_video"
    assert rows[0].source_page == "https://news.example/video/42"
    assert rows[0].preview_url == "https://img.example/42.jpg"
    assert rows[0].acquisition_mode == "bounded_window"


def test_vertical_factory_can_add_web_video_source(monkeypatch):
    from backend.app.vertical_social import build_default_vertical_sources

    monkeypatch.setenv("RAMBLA_ENABLE_WEB_VIDEO", "1")
    sources = build_default_vertical_sources()
    assert [source.provider_name for source in sources][-1] == "web_video"


def test_curation_artifacts_expose_discovery_source_when_clip_download_failed(tmp_path, monkeypatch):
    import json
    import backend.app.curation_artifacts as artifacts

    run = tmp_path / "run"
    run.mkdir()
    (run / "semantic-chunks.json").write_text(json.dumps([
        {"id": "b1", "text": "news beat"}
    ]), encoding="utf-8")
    poster = run / "poster.jpg"
    poster.write_bytes(b"fake")
    (run / "online-candidates.json").write_text(json.dumps([{
        "parent_beat_id": "b1",
        "quality_version": "clip-quality-13",
        "candidates": [],
        "discovery_sources": [{
            "id": "web_video:story42",
            "source": "web_video",
            "source_page": "https://news.example/video/42",
            "description": "Eyewitness phone video",
            "score": 0.42,
            "rights_state": "review_required",
            "orientation": "unknown",
            "preview_path": str(poster),
            "poster_path": str(poster),
            "preview_status": "preview_pending",
            "quality_state": "source_found",
            "clip_verified": False,
        }],
    }]), encoding="utf-8")
    monkeypatch.setattr(artifacts, "probe_preview", lambda _path: {"playable": False})

    view = artifacts.load_curation_run(run)
    candidate = view.chunks[0].video_candidates[0]
    assert candidate.provider == "web_video"
    assert candidate.preview_status == "preview_pending"
    assert candidate.clip_verified is False
    assert candidate.source_page == "https://news.example/video/42"
