from __future__ import annotations

import httpx
import pytest

from backend.app.online_assets import (
    PexelsSource,
    ProviderError,
    dedupe_candidates,
    filter_candidates,
)


def _payload() -> dict:
    return {
        "videos": [
            {
                "id": 42,
                "url": "https://www.pexels.com/video/42/?utm_source=test",
                "duration": 8,
                "width": 1080,
                "height": 1920,
                "user": {
                    "id": 7,
                    "name": "Alice",
                    "url": "https://www.pexels.com/@alice?ref=api",
                },
                "image": "https://images.pexels.com/videos/42/free-video-42.jpg?auto=compress",
                "video_files": [
                    {
                        "id": 1,
                        "width": 540,
                        "height": 960,
                        "quality": "sd",
                        "file_type": "video/mp4",
                        "link": "https://cdn.pexels.com/preview.mp4?token=temp",
                    },
                    {
                        "id": 2,
                        "width": 1080,
                        "height": 1920,
                        "quality": "hd",
                        "file_type": "video/mp4",
                        "link": "https://cdn.pexels.com/full.mp4?token=temp",
                    },
                ],
            }
        ]
    }


def _transport(payload: dict, *, status: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == "SECRET"
        return httpx.Response(status, json=payload, request=request)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_pexels_search_normalizes_vertical_video() -> None:
    source = PexelsSource(api_key="SECRET", transport=_transport(_payload()))

    rows = await source.search(
        "night computer work",
        orientation="portrait",
        min_duration=2,
        max_duration=20,
        limit=10,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row.provider == "pexels"
    assert row.provider_id == "42"
    assert row.query == "night computer work"
    assert row.source_page == "https://www.pexels.com/video/42/"
    assert row.creator_name == "Alice"
    assert row.creator_page == "https://www.pexels.com/@alice"
    assert row.duration == 8.0
    assert row.orientation == "portrait"
    assert row.preview_url.startswith("https://images.pexels.com/")
    assert row.selected_rendition_url.startswith("https://cdn.pexels.com/full.mp4")
    assert row.rendition_width == 1080
    assert row.rendition_height == 1920
    assert row.rights_state == "provider_stock_terms"
    assert row.provider_rank == 0
    assert "SECRET" not in repr(row)


@pytest.mark.asyncio
async def test_pexels_requires_explicit_key() -> None:
    source = PexelsSource(api_key=None)

    with pytest.raises(ProviderError) as exc:
        await source.search("anything", orientation="portrait", min_duration=1, max_duration=30, limit=5)

    assert exc.value.provider == "pexels"
    assert exc.value.code == "credential_required"


@pytest.mark.asyncio
async def test_pexels_maps_rate_limit_without_leaking_key() -> None:
    source = PexelsSource(api_key="SECRET", transport=_transport({"error": "slow down"}, status=429))

    with pytest.raises(ProviderError) as exc:
        await source.search("anything", orientation="portrait", min_duration=1, max_duration=30, limit=5)

    assert exc.value.code == "rate_limited"
    assert "SECRET" not in str(exc.value)


@pytest.mark.asyncio
async def test_pexels_maps_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("boom", request=request)

    source = PexelsSource(api_key="SECRET", transport=httpx.MockTransport(handler))

    with pytest.raises(ProviderError) as exc:
        await source.search("anything", orientation="portrait", min_duration=1, max_duration=30, limit=5)

    assert exc.value.code == "timeout"


@pytest.mark.asyncio
async def test_filter_and_dedupe_are_deterministic() -> None:
    source = PexelsSource(api_key="SECRET", transport=_transport(_payload()))
    rows = await source.search("anything", orientation="portrait", min_duration=1, max_duration=30, limit=5)
    row = rows[0]

    duplicate = [row, row]
    assert dedupe_candidates(duplicate) == [row]
    assert filter_candidates(
        duplicate,
        orientation="portrait",
        min_duration=2,
        max_duration=20,
    ) == [row]
    assert filter_candidates(
        duplicate,
        orientation="landscape",
        min_duration=2,
        max_duration=20,
    ) == []
    assert filter_candidates(
        duplicate,
        orientation="portrait",
        min_duration=9,
        max_duration=20,
    ) == []
