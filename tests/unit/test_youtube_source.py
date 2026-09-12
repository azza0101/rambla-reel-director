from __future__ import annotations

import pytest

from backend.app.youtube_source import YouTubeSource, normalize_youtube_result


def _row() -> dict:
    return {
        "id": "abc123",
        "title": "Olimpia Peroni interview",
        "duration": 612.0,
        "channel": "Example Channel",
        "width": 1920,
        "height": 1080,
        "thumbnail": "https://i.ytimg.com/vi/abc123/hqdefault.jpg?token=temp",
        "scene_evidence": [
            {"timestamp_seconds": 75.0, "text": "named subject enters frame", "metadata_score": 0.9},
            {"timestamp_seconds": 80.0, "text": "close up interview", "metadata_score": 0.8},
        ],
    }


def test_normalize_youtube_result_keeps_public_watch_url_and_review_rights() -> None:
    candidate = normalize_youtube_result(_row(), query="Olimpia Peroni interview")

    assert candidate.video_id == "abc123"
    assert candidate.source_page == "https://www.youtube.com/watch?v=abc123"
    assert candidate.title == "Olimpia Peroni interview"
    assert candidate.creator_name == "Example Channel"
    assert candidate.duration == 612.0
    assert candidate.width == 1920
    assert candidate.height == 1080
    assert candidate.orientation == "landscape"
    assert candidate.rights_state == "review_required"
    assert len(candidate.scene_evidence) == 2
    assert candidate.scene_evidence[0].timestamp_seconds == 75.0
    assert "token=" not in candidate.thumbnail_url


def test_normalize_youtube_result_rejects_missing_video_id() -> None:
    row = _row()
    row["id"] = ""

    with pytest.raises(ValueError, match="video id"):
        normalize_youtube_result(row, query="x")


@pytest.mark.asyncio
async def test_youtube_source_uses_injected_discovery_and_duration_filter() -> None:
    calls = []

    async def discover(query: str, limit: int) -> list[dict]:
        calls.append((query, limit))
        long = _row()
        short = {**_row(), "id": "short", "duration": 20.0}
        return [long, short]

    source = YouTubeSource(discover=discover)
    rows = await source.search("named interview", min_duration=5, max_duration=60, limit=10)

    assert calls == [("named interview", 10)]
    assert [row.video_id for row in rows] == ["short"]


@pytest.mark.asyncio
async def test_youtube_source_does_not_require_portrait_orientation() -> None:
    async def discover(_query: str, _limit: int) -> list[dict]:
        landscape = _row()
        portrait = {**_row(), "id": "portrait", "width": 1080, "height": 1920}
        return [landscape, portrait]

    source = YouTubeSource(discover=discover)
    rows = await source.search("evidence", min_duration=1, max_duration=1000, limit=10)

    assert {row.orientation for row in rows} == {"portrait", "landscape"}
