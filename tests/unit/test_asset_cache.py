from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.asset_cache import AssetCache, public_provenance
from backend.app.online_assets import RemoteCandidate


def candidate_fixture() -> RemoteCandidate:
    return RemoteCandidate(
        provider="pexels",
        provider_id="42",
        query="night computer work",
        source_page="https://www.pexels.com/video/42/",
        creator_name="Alice",
        creator_page="https://www.pexels.com/@alice",
        title="Pexels video 42",
        description="night computer work",
        duration=8.0,
        width=1080,
        height=1920,
        orientation="portrait",
        preview_url="https://images.pexels.com/videos/42/frame.jpg?token=temporary",
        selected_rendition_url="https://cdn.pexels.com/full.mp4?token=secret-temporary",
        rendition_width=1080,
        rendition_height=1920,
        rights_state="provider_stock_terms",
        provider_rank=0,
    )


@pytest.mark.asyncio
async def test_preview_cache_hits_without_second_download(tmp_path) -> None:
    cache = AssetCache(tmp_path)
    candidate = candidate_fixture()
    calls = 0

    async def fetch(url: str) -> bytes:
        nonlocal calls
        calls += 1
        assert url == candidate.preview_url
        return b"jpeg-bytes"

    first = await cache.materialize_preview(candidate, fetch=fetch)
    second = await cache.materialize_preview(candidate, fetch=fetch)

    assert first.path == second.path
    assert first.sha256 == second.sha256
    assert first.path.exists()
    assert first.path.suffix == ".jpg"
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert calls == 1


@pytest.mark.asyncio
async def test_preview_cache_writes_public_sidecar_without_transient_urls(tmp_path) -> None:
    cache = AssetCache(tmp_path)
    candidate = candidate_fixture()

    preview = await cache.materialize_preview(candidate, fetch=lambda _: _bytes(b"image"))
    metadata = json.loads(preview.metadata_path.read_text(encoding="utf-8"))
    serialized = json.dumps(metadata)

    assert metadata["provider"] == "pexels"
    assert metadata["provider_id"] == "42"
    assert metadata["source_page"] == "https://www.pexels.com/video/42/"
    assert metadata["creator"]["name"] == "Alice"
    assert metadata["preview_sha256"] == preview.sha256
    assert "cdn.pexels.com" not in serialized
    assert "token=" not in serialized
    assert "Authorization" not in serialized


@pytest.mark.asyncio
async def test_selected_media_downloads_once_and_persists_public_provenance(tmp_path) -> None:
    cache = AssetCache(tmp_path)
    candidate = candidate_fixture()
    calls = 0

    async def fetch(url: str) -> bytes:
        nonlocal calls
        calls += 1
        assert url == candidate.selected_rendition_url
        return b"fake-mp4-content"

    first = await cache.materialize_selected(candidate, fetch=fetch)
    second = await cache.materialize_selected(candidate, fetch=fetch)
    metadata = json.loads(first.metadata_path.read_text(encoding="utf-8"))
    serialized = json.dumps(metadata)

    assert first.path.suffix == ".mp4"
    assert first.path.read_bytes() == b"fake-mp4-content"
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert calls == 1
    assert metadata["provider"] == "pexels"
    assert metadata["local_file"] == first.path.name
    assert metadata["content_sha256"] == first.sha256
    assert metadata["rendition"] == {"width": 1080, "height": 1920}
    assert "cdn.pexels.com" not in serialized
    assert "token=" not in serialized


@pytest.mark.asyncio
async def test_bounded_window_cache_acquires_once_and_keeps_source_timestamp(tmp_path) -> None:
    cache = AssetCache(tmp_path)
    calls = 0

    async def acquire(output_path: Path) -> None:
        nonlocal calls
        calls += 1
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"short-window")

    first = await cache.materialize_acquired_window(
        provider="youtube",
        provider_id="abc123",
        source_page="https://www.youtube.com/watch?v=abc123&token=DO_NOT_KEEP",
        source_start_seconds=75.0,
        source_end_seconds=78.5,
        rights_state="review_required",
        acquire=acquire,
        kind="video_window",
    )
    second = await cache.materialize_acquired_window(
        provider="youtube",
        provider_id="abc123",
        source_page="https://www.youtube.com/watch?v=abc123&token=DO_NOT_KEEP",
        source_start_seconds=75.0,
        source_end_seconds=78.5,
        rights_state="review_required",
        acquire=acquire,
        kind="video_window",
    )
    metadata = json.loads(first.metadata_path.read_text(encoding="utf-8"))
    serialized = json.dumps(metadata)

    assert first.path.suffix == ".mp4"
    assert first.path.read_bytes() == b"short-window"
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert calls == 1
    assert metadata["provider"] == "youtube"
    assert metadata["provider_id"] == "abc123"
    assert metadata["source_page"] == "https://www.youtube.com/watch?v=abc123"
    assert metadata["source_start_seconds"] == 75.0
    assert metadata["source_end_seconds"] == 78.5
    assert metadata["rights_state"] == "review_required"
    assert "DO_NOT_KEEP" not in serialized
    assert "token=" not in serialized


def test_public_provenance_contains_no_download_url() -> None:
    candidate = candidate_fixture()
    row = public_provenance(candidate)
    serialized = json.dumps(row)

    assert row["source_page"] == "https://www.pexels.com/video/42/"
    assert row["creator"]["profile_page"] == "https://www.pexels.com/@alice"
    assert row["rights_state"] == "provider_stock_terms"
    assert "selected_rendition_url" not in row
    assert "preview_url" not in row
    assert "token=" not in serialized


async def _bytes(value: bytes) -> bytes:
    return value
