from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.asset_cache import PreviewAsset
from backend.app.online_assets import RemoteCandidate
from backend.app.online_sourcing import OnlineSourcingEngine
from backend.app.taste_profile import TasteProfile, build_taste_context


class OneSource:
    async def search(self, query, *, orientation, min_duration, max_duration, limit):
        return [
            RemoteCandidate(
                provider="youtube",
                provider_id="receipt-1",
                query=query,
                source_page="https://youtube.com/watch?v=receipt-1",
                creator_name="OpenAI",
                creator_page="https://youtube.com/@OpenAI",
                title="Original launch post coverage",
                description="the original receipt for the launch",
                duration=30.0,
                width=1920,
                height=1080,
                orientation="landscape",
                preview_url="https://example.test/receipt.jpg",
                selected_rendition_url="https://example.test/receipt.mp4",
                rendition_width=1920,
                rendition_height=1080,
                rights_state="review_required",
                provider_rank=0,
            ),
            RemoteCandidate(
                provider="pexels",
                provider_id="stock-1",
                query=query,
                source_page="https://pexels.com/video/stock-1",
                creator_name="Stock",
                creator_page="https://pexels.com/@stock",
                title="Generic phone footage",
                description="generic phone footage",
                duration=10.0,
                width=1080,
                height=1920,
                orientation="portrait",
                preview_url="https://example.test/stock.jpg",
                selected_rendition_url="https://example.test/stock.mp4",
                rendition_width=1080,
                rendition_height=1920,
                rights_state="provider_stock_terms",
                provider_rank=1,
            ),
        ]


class PreviewCache:
    def __init__(self, root: Path):
        self.root = root

    async def materialize_preview(self, candidate):
        path = self.root / f"{candidate.provider_id}.jpg"
        path.write_bytes(candidate.provider_id.encode("utf-8"))
        return PreviewAsset(
            path=path,
            metadata_path=self.root / f"{candidate.provider_id}.json",
            sha256=(candidate.provider_id * 8)[:64],
            cache_hit=False,
        )


class FixedRanker:
    def rank(self, query, assets):
        output = []
        for asset in assets:
            row = dict(asset)
            if asset["id"].startswith("youtube:"):
                row.update(
                    score=0.88,
                    embedding_score=0.88,
                    route="RECEIPT",
                    source_registry_key="youtube:OpenAI",
                    providers={"embedding": "fake-qwen", "reranker": None},
                )
            else:
                row.update(
                    score=0.90,
                    embedding_score=0.90,
                    route="STOCK",
                    providers={"embedding": "fake-qwen", "reranker": None},
                )
            output.append(row)
        return sorted(output, key=lambda row: -row["score"])


def _taste():
    return build_taste_context(
        TasteProfile(
            client_id="client-a",
            version=4,
            approved=True,
            route_weights={"RECEIPT": 0.9, "STOCK": 0.1},
            guardrails={"memes": False},
            trusted_sources={"tech": ("youtube:OpenAI",)},
            default_proposal_count=2,
        ),
        topic="tech",
    )


@pytest.mark.asyncio
async def test_online_sourcing_threads_taste_route_and_profile_snapshot(tmp_path) -> None:
    taste = _taste()
    engine = OnlineSourcingEngine(
        sources=[OneSource()],
        cache=PreviewCache(tmp_path),
        ranker=FixedRanker(),
    )

    result = await engine.source_beat(
        beat_id="beat-1",
        client_id="client-a",
        queries=["original post about launch"],
        min_duration=0,
        max_duration=60,
        taste=taste,
        visual_route="RECEIPT",
    )

    assert result["visual_route"] == "RECEIPT"
    assert result["taste_profile_version"] == taste.profile_version
    assert result["taste_profile_hash"] == taste.profile_hash
    assert result["proposals"]["minimum_proposals"] == 2
    assert result["proposals"]["proposal_A"]["id"] == "youtube:receipt-1"
    assert "taste_score" in result["proposals"]["proposal_A"]


@pytest.mark.asyncio
async def test_empty_sourcing_still_preserves_taste_snapshot(tmp_path) -> None:
    taste = _taste()

    class EmptySource:
        async def search(self, query, **kwargs):
            return []

    engine = OnlineSourcingEngine(
        sources=[EmptySource()],
        cache=PreviewCache(tmp_path),
        ranker=FixedRanker(),
    )
    result = await engine.source_beat(
        beat_id="beat-1",
        client_id="client-a",
        queries=["nothing"],
        min_duration=0,
        max_duration=60,
        taste=taste,
        visual_route="RECEIPT",
    )

    assert result["candidates"] == []
    assert result["visual_route"] == "RECEIPT"
    assert result["taste_profile_hash"] == taste.profile_hash
