from __future__ import annotations

import httpx
import pytest

from backend.app.online_assets import (
    PexelsSource,
    ProviderError,
    dedupe_candidates,
    filter_candidates,
)


def _portrait_video() -> dict:
    return {
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


def _landscape_video() -> dict:
    return {
        "id": 77,
        "url": "https://www.pexels.com/video/77/",
        "duration": 11,
        "width": 1920,
        "height": 1080,
        "user": {"name": "Bob", "url": "https://www.pexels.com/@bob"},
        "image": "https://images.pexels.com/videos/77/free-video-77.jpg",
        "video_files": [
            {
                "id": 3,
                "width": 1920,
                "height": 1080,
                "quality": "hd",
                "file_type": "video/mp4",
                "link": "https://cdn.pexels.com/landscape.mp4?token=temp",
            }
        ],
    }


def _payload(*, mixed: bool = False) -> dict:
    videos = [_portrait_video()]
    if mixed:
        videos.append(_landscape_video())
    return {"videos": videos}


def _transport(payload: dict, *, status: int = 200, assert_no_orientation: bool = False) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == "SECRET"
        if assert_no_orientation:
            assert "orientation" not in request.url.params
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
async def test_pexels_incremental_research_requests_a_new_provider_page(monkeypatch) -> None:
    monkeypatch.setenv("RAMBLA_SOCIAL_SEARCH_OPTIONS", '{"variation_round": 4}')

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["page"] == "5"
        return httpx.Response(200, json=_payload(), request=request)

    source = PexelsSource(api_key="SECRET", transport=httpx.MockTransport(handler))
    rows = await source.search("bathroom", orientation=None, min_duration=1, max_duration=20, limit=5)
    assert rows


@pytest.mark.asyncio
async def test_pexels_mixed_aspect_search_omits_orientation_filter() -> None:
    source = PexelsSource(
        api_key="SECRET",
        transport=_transport(_payload(mixed=True), assert_no_orientation=True),
    )

    rows = await source.search(
        "named person interview",
        orientation=None,
        min_duration=1,
        max_duration=20,
        limit=10,
    )

    assert [row.provider_id for row in rows] == ["42", "77"]
    assert {row.orientation for row in rows} == {"portrait", "landscape"}


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
        orientation=None,
        min_duration=2,
        max_duration=20,
    ) == [row]
    assert filter_candidates(
        duplicate,
        orientation="portrait",
        min_duration=9,
        max_duration=20,
    ) == []


@pytest.mark.asyncio
async def test_pexels_candidate_is_explicit_generic_stock() -> None:
    source = PexelsSource(api_key="SECRET", transport=_transport(_payload()))
    rows = await source.search("camera", orientation=None, min_duration=1, max_duration=20, limit=2)
    assert rows[0].source_class == "GENERIC_STOCK"
    assert rows[0].source_authenticity is None


def test_pexels_provider_identity_is_explicit_for_priority_routing() -> None:
    assert PexelsSource.provider_name == "pexels"
