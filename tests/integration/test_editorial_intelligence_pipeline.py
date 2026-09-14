"""Offline editorial path from transcript chunk to inspectable review."""

from __future__ import annotations

import json
from dataclasses import replace

from backend.app.asset_cache import PreviewAsset
from backend.app.online_assets import RemoteCandidate
from backend.app.online_sourcing import OnlineSourcingEngine
from backend.app.online_sourcing_cli import run_online_from_artifacts
from backend.app.taste_profile import TasteProfile, build_taste_context


class ExactSource:
    supported_source_classes = ("EXACT_RECEIPT",)

    async def search(self, query, *, orientation, min_duration, max_duration, limit):
        ids = ["dead"] if "debole" in query else ["receipt-a", "receipt-b"]
        return [RemoteCandidate(
            provider="web", provider_id=item, query=query,
            source_page=f"https://example.test/{item}", creator_name="Original publisher",
            creator_page=None, title=item, description=query, duration=8,
            width=1080, height=1920, orientation="portrait",
            preview_url=f"https://example.test/{item}.jpg",
            selected_rendition_url=f"https://example.test/{item}.mp4",
            rendition_width=1080, rendition_height=1920,
            rights_state="review_required", provider_rank=index,
            source_class="EXACT_RECEIPT",
        ) for index, item in enumerate(ids[:limit])]


class StockSource:
    supported_source_classes = ("GENERIC_STOCK",)

    async def search(self, query, *, orientation, min_duration, max_duration, limit):
        return [replace((await ExactSource().search(query, orientation=orientation,
                 min_duration=min_duration, max_duration=max_duration, limit=1))[0],
                 provider="pexels", provider_id="stock", source_class="GENERIC_STOCK")]


class Cache:
    def __init__(self, root):
        self.root = root

    async def materialize_preview(self, candidate):
        path = self.root / f"{candidate.provider_id}.jpg"
        path.write_bytes(candidate.provider_id.encode())
        return PreviewAsset(path=path, metadata_path=path.with_suffix(".json"),
                            sha256=(candidate.provider_id * 8)[:64], cache_hit=False)


class Ranker:
    def rank(self, query, assets):
        return [{**asset, "score": .97 if asset["provider_id"] == "stock" else .9,
                 "embedding_score": .97 if asset["provider_id"] == "stock" else .9,
                 "editorial_quality": .1 if asset["provider_id"] == "dead" else .85}
                for asset in assets]


def test_editorial_pipeline_keeps_exact_ab_and_explicit_quality_floor(tmp_path):
    transcript = {"source": "fixture.mp4", "timeline_fps": 25, "language": "it", "segments": [
        {"start": 0.0, "end": 4.0, "text": 'OpenAI ha scritto "forte".', "words": []},
        {"start": 4.0, "end": 8.0, "text": 'OpenAI ha scritto "debole".', "words": []},
    ]}
    outline = {"beats": [
        {"id": "strong", "start_seconds": 0, "end_seconds": 4,
         "intent": "show original post", "broll_queries": ["forte original post"]},
        {"id": "weak", "start_seconds": 4, "end_seconds": 8,
         "intent": "show original post", "broll_queries": ["debole original post"]},
    ]}
    transcript_path = tmp_path / "transcript.json"
    outline_path = tmp_path / "outline.json"
    transcript_path.write_text(json.dumps(transcript), encoding="utf-8")
    outline_path.write_text(json.dumps(outline), encoding="utf-8")
    taste = build_taste_context(TasteProfile(client_id="rambla", version=1, approved=True))
    engine = OnlineSourcingEngine(sources=[ExactSource(), StockSource()], cache=Cache(tmp_path),
                                  ranker=Ranker())
    output = tmp_path / "run"
    plan = run_online_from_artifacts(transcript_path, outline_path, output,
                                     client_id="rambla", source_frames=200,
                                     sourcing_engine=engine, taste_context=taste)
    slots = {row["beat_id"]: row for row in plan["coverage_slots"]}
    assert slots["strong"]["review_state"] == "READY"
    assert slots["strong"]["proposal_A"]["source_class"] == "EXACT_RECEIPT"
    assert slots["strong"]["proposal_B"]["id"] != slots["strong"]["proposal_A"]["id"]
    assert len(slots["strong"]["proposal_A"]["score_components"]) == 8
    assert slots["weak"]["review_state"] == "NO_BROLL_QUALITY_FLOOR"
    assert slots["weak"]["proposal_A"] is None
    assert all(beat["id"] != "weak" or beat["selected_asset"] is None for beat in plan["beats"])
    assert plan["resolve_calls"] == 0
    html = (output / "review.html").read_text(encoding="utf-8")
    assert "NO_BROLL_QUALITY_FLOOR" in html
    assert "editorial_quality_below_floor" in html
