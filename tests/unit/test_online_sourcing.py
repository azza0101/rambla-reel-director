from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.asset_cache import PreviewAsset
from backend.app.online_assets import ProviderError, RemoteCandidate
from backend.app.online_sourcing import OnlineSourcingEngine
from backend.app.qwen_stack import QwenMultimodalRanker


def _candidate(
    provider_id: str,
    *,
    rank: int,
    query: str,
    width: int = 1080,
    height: int = 1920,
) -> RemoteCandidate:
    orientation = "square" if width == height else "portrait" if height > width else "landscape"
    return RemoteCandidate(
        provider="pexels",
        provider_id=provider_id,
        query=query,
        source_page=f"https://www.pexels.com/video/{provider_id}/",
        creator_name="Alice",
        creator_page="https://www.pexels.com/@alice",
        title=f"Pexels video {provider_id}",
        description=f"candidate {provider_id}",
        duration=8.0,
        width=width,
        height=height,
        orientation=orientation,
        preview_url=f"https://images.pexels.com/{provider_id}.jpg",
        selected_rendition_url=f"https://cdn.pexels.com/{provider_id}.mp4",
        rendition_width=width,
        rendition_height=height,
        rights_state="provider_stock_terms",
        provider_rank=rank,
    )


class FakeSource:
    def __init__(self):
        self.calls = []
        self.orientations = []

    async def search(self, query, *, orientation, min_duration, max_duration, limit):
        self.calls.append(query)
        self.orientations.append(orientation)
        if query == "query one":
            return [
                _candidate("1", rank=0, query=query, width=1920, height=1080),
                _candidate("2", rank=1, query=query),
            ]
        return [_candidate("2", rank=0, query=query), _candidate("3", rank=1, query=query)]


class FailingSource:
    async def search(self, query, **kwargs):
        raise ProviderError("pexels", "timeout", "timeout")


class FakeCache:
    def __init__(self, root: Path):
        self.root = root
        self.calls = []

    async def materialize_preview(self, candidate):
        self.calls.append(candidate.provider_id)
        path = self.root / f"{candidate.provider_id}.jpg"
        path.write_bytes(candidate.provider_id.encode())
        return PreviewAsset(
            path=path,
            metadata_path=self.root / f"{candidate.provider_id}.json",
            sha256=candidate.provider_id * 8,
            cache_hit=False,
        )


@pytest.mark.asyncio
async def test_source_beat_dedupes_previews_and_qwen_ranks_local_paths(tmp_path):
    source = FakeSource()
    cache = FakeCache(tmp_path)
    seen_embed_inputs = []

    def embed(items):
        seen_embed_inputs.append(items)
        vectors = [[1.0, 0.0]]
        for item in items[1:]:
            name = Path(item).stem
            vectors.append({"1": [0.6, 0.8], "2": [0.9, 0.1], "3": [0.2, 0.98]}[name])
        return vectors

    ranker = QwenMultimodalRanker(client_id="rambla", embed=embed, rerank=None)
    engine = OnlineSourcingEngine(
        sources=[source],
        cache=cache,
        ranker=ranker,
        max_results_per_query=5,
        max_preview_candidates=5,
    )

    result = await engine.source_beat(
        beat_id="beat-1",
        client_id="rambla",
        queries=["query one", "query two"],
        min_duration=2,
        max_duration=15,
    )

    assert source.calls == ["query one", "query two"]
    assert source.orientations == [None, None]
    assert sorted(cache.calls) == ["1", "2", "3"]
    assert len(seen_embed_inputs) == 1
    assert seen_embed_inputs[0][0] == "query one"
    assert all(Path(path).is_file() for path in seen_embed_inputs[0][1:])
    assert [row["provider_id"] for row in result["candidates"]] == ["2", "1", "3"]
    assert result["candidates"][0]["source"] == "pexels"
    assert result["candidates"][0]["source_page"].startswith("https://www.pexels.com/video/")
    assert result["candidates"][0]["embedding_score"] == 0.9939
    assert result["candidates"][0]["selected_full_download"] is False
    assert result["candidates"][1]["orientation"] == "landscape"
    assert result["proposals"]["proposal_A"] is not None
    assert result["proposals"]["proposal_B"] is not None
    assert result["proposals"]["proposal_A"]["id"] != result["proposals"]["proposal_B"]["id"]
    assert "crop_score" in result["proposals"]["proposal_A"]
    assert "qwen_score" in result["proposals"]["proposal_A"]
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_provider_failure_degrades_to_empty_candidates(tmp_path):
    engine = OnlineSourcingEngine(
        sources=[FailingSource()],
        cache=FakeCache(tmp_path),
        ranker=QwenMultimodalRanker(client_id="rambla", embed=lambda items: [], rerank=None),
    )

    result = await engine.source_beat(
        beat_id="beat-1",
        client_id="rambla",
        queries=["query"],
        min_duration=2,
        max_duration=15,
    )

    assert result["candidates"] == []
    assert result["proposals"]["review_state"] == "NO_VISUAL_FOUND"
    assert result["errors"] == [{"provider": "pexels", "code": "timeout"}]


@pytest.mark.asyncio
async def test_query_count_is_bounded(tmp_path):
    engine = OnlineSourcingEngine(
        sources=[FakeSource()],
        cache=FakeCache(tmp_path),
        ranker=QwenMultimodalRanker(client_id="rambla", embed=lambda items: [[1.0, 0.0] for _ in items], rerank=None),
        max_queries=3,
    )

    with pytest.raises(ValueError, match="queries"):
        await engine.source_beat(
            beat_id="beat",
            client_id="rambla",
            queries=["a", "b", "c", "d"],
            min_duration=1,
            max_duration=10,
        )


@pytest.mark.asyncio
async def test_duplicate_queries_are_normalized_before_provider_search(tmp_path):
    source = FakeSource()
    engine = OnlineSourcingEngine(
        sources=[source],
        cache=FakeCache(tmp_path),
        ranker=QwenMultimodalRanker(
            client_id="rambla",
            embed=lambda items: [[1.0, 0.0] for _ in items],
            rerank=None,
        ),
        max_queries=3,
    )

    result = await engine.source_beat(
        beat_id="beat",
        client_id="rambla",
        queries=[" query one ", "QUERY ONE", "query two"],
        min_duration=1,
        max_duration=10,
    )

    assert source.calls == ["query one", "query two"]
    assert result["queries"] == ["query one", "query two"]


@pytest.mark.asyncio
async def test_provider_search_is_memoized_across_beats(tmp_path):
    source = FakeSource()
    engine = OnlineSourcingEngine(
        sources=[source],
        cache=FakeCache(tmp_path),
        ranker=QwenMultimodalRanker(
            client_id="rambla",
            embed=lambda items: [[1.0, 0.0] for _ in items],
            rerank=None,
        ),
    )

    for beat_id in ("beat-a", "beat-b"):
        await engine.source_beat(
            beat_id=beat_id,
            client_id="rambla",
            queries=["query one"],
            min_duration=1,
            max_duration=10,
        )

    assert source.calls == ["query one"]
