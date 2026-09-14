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
async def test_equivalent_queries_and_repeated_search_reuse_provider_result(tmp_path):
    source = FakeSource()
    engine = OnlineSourcingEngine(
        sources=[source], cache=FakeCache(tmp_path),
        ranker=QwenMultimodalRanker(client_id="rambla", embed=lambda items: [[1.0, 0.0] for _ in items], rerank=None),
    )
    for _ in range(2):
        await engine.source_beat(beat_id="beat", client_id="rambla",
                                 queries=["query one", " QUERY   ONE "],
                                 min_duration=1, max_duration=10)
    assert source.calls == ["query one"]


class EditorialSource:
    def __init__(self, source_class: str, ids: list[str], calls: list[str]):
        self.supported_source_classes = (source_class,)
        self.source_class = source_class
        self.ids = ids
        self.calls = calls

    async def search(self, query, *, orientation, min_duration, max_duration, limit):
        from dataclasses import replace

        self.calls.append(self.source_class)
        return [
            replace(
                _candidate(item, rank=index, query=query),
                provider="web" if self.source_class != "GENERIC_STOCK" else "pexels",
                source_class=self.source_class,
            )
            for index, item in enumerate(self.ids[:limit])
        ]


def _editorial_context():
    from backend.app.evidence_intent import plan_evidence_intent
    from backend.app.source_strategy import plan_source_strategy
    from backend.app.taste_profile import TasteProfile, build_taste_context

    taste = build_taste_context(TasteProfile(client_id="rambla", version=1, approved=True))
    intent = plan_evidence_intent({"transcript": 'Ha scritto "non venderemo i dati"', "intent": "show claim"}, "official post", "RECEIPT", taste)
    return taste, intent, plan_source_strategy(intent, "RECEIPT", taste)


def _editorial_ranker():
    return QwenMultimodalRanker(client_id="rambla", embed=lambda items: [[1.0, 0.0] for _ in items], rerank=None)


@pytest.mark.asyncio
async def test_editorial_sourcing_stops_before_stock_when_exact_ab_passes(tmp_path):
    calls = []
    taste, intent, strategy = _editorial_context()
    engine = OnlineSourcingEngine(
        sources=[
            EditorialSource("EXACT_RECEIPT", ["receipt-a", "receipt-b"], calls),
            EditorialSource("GENERIC_STOCK", ["stock"], calls),
        ],
        cache=FakeCache(tmp_path),
        ranker=_editorial_ranker(),
    )
    result = await engine.source_beat(
        beat_id="claim", client_id="rambla", queries=["claim"],
        min_duration=2, max_duration=15, taste=taste, visual_route="RECEIPT",
        evidence_intent=intent, source_strategy=strategy,
    )
    assert calls == ["EXACT_RECEIPT"]
    assert result["searched_source_classes"] == ["EXACT_RECEIPT"]
    assert result["proposals"]["proposal_A"]["source_class"] == "EXACT_RECEIPT"
    assert result["proposals"]["proposal_B"]["id"] != result["proposals"]["proposal_A"]["id"]
    assert result["source_strategy"]["classes"][0] == "EXACT_RECEIPT"


@pytest.mark.asyncio
async def test_editorial_sourcing_escalates_for_second_proposal_without_stock(tmp_path):
    calls = []
    taste, intent, strategy = _editorial_context()
    engine = OnlineSourcingEngine(
        sources=[
            EditorialSource("EXACT_RECEIPT", ["receipt-a"], calls),
            EditorialSource("EXACT_ENTITY_EVENT", ["event-b"], calls),
            EditorialSource("GENERIC_STOCK", ["stock"], calls),
        ],
        cache=FakeCache(tmp_path),
        ranker=_editorial_ranker(),
    )
    result = await engine.source_beat(
        beat_id="claim", client_id="rambla", queries=["claim"],
        min_duration=2, max_duration=15, taste=taste, visual_route="RECEIPT",
        evidence_intent=intent, source_strategy=strategy,
    )
    assert calls == ["EXACT_RECEIPT", "EXACT_ENTITY_EVENT"]
    assert result["proposals"]["review_state"] == "READY"
    assert result["source_class_search_rounds"] == 2


@pytest.mark.asyncio
async def test_editorial_sourcing_reports_quality_floor_and_never_calls_resolve(tmp_path):
    calls = []
    taste, intent, strategy = _editorial_context()

    class LowQualityRanker:
        def rank(self, query, assets):
            return [{**asset, "score": .9, "embedding_score": .9, "editorial_quality": .1} for asset in assets]

    engine = OnlineSourcingEngine(
        sources=[EditorialSource("EXACT_RECEIPT", ["bad"], calls)],
        cache=FakeCache(tmp_path),
        ranker=LowQualityRanker(),
    )
    result = await engine.source_beat(
        beat_id="claim", client_id="rambla", queries=["claim"],
        min_duration=2, max_duration=15, taste=taste, visual_route="RECEIPT",
        evidence_intent=intent, source_strategy=strategy,
    )
    assert result["proposals"]["review_state"] == "NO_BROLL_QUALITY_FLOOR"
    assert result["proposals"]["proposal_A"] is None
    assert result["rejected_candidates"]
    assert result["resolve_calls"] == 0


@pytest.mark.asyncio
async def test_editorial_sourcing_does_not_treat_thumbnail_as_final_window_evidence(tmp_path):
    from dataclasses import asdict
    from backend.app.youtube_source import YouTubeRemoteCandidate

    taste, intent, strategy = _editorial_context()

    class ThumbnailSource(EditorialSource):
        async def search(self, query, *, orientation, min_duration, max_duration, limit):
            rows = await super().search(query, orientation=orientation,
                                        min_duration=min_duration, max_duration=max_duration,
                                        limit=limit)
            return [YouTubeRemoteCandidate(**asdict(row), scene_evidence=(),
                                           acquisition_mode="bounded_window",
                                           source_duration=row.duration) for row in rows]

    engine = OnlineSourcingEngine(
        sources=[ThumbnailSource("EXACT_RECEIPT", ["thumbnail-only"], [])],
        cache=FakeCache(tmp_path), ranker=_editorial_ranker(),
    )
    result = await engine.source_beat(
        beat_id="claim", client_id="rambla", queries=["claim"],
        min_duration=2, max_duration=15, taste=taste, visual_route="RECEIPT",
        evidence_intent=intent, source_strategy=strategy,
    )
    assert result["proposals"]["proposal_A"] is None
    assert "semantic_relevance_below_floor" in result["rejected_candidates"][0]["rejection_reasons"]
