from __future__ import annotations

import json

from backend.app.asset_cache import AssetCache
from backend.app.online_assets import RemoteCandidate
from backend.app.online_sourcing import OnlineSourcingEngine
from backend.app.online_sourcing_cli import run_online_from_artifacts
from backend.app.qwen_stack import QwenMultimodalRanker


class FakeSource:
    async def search(self, query, *, orientation, min_duration, max_duration, limit):
        return [RemoteCandidate(
            provider="pexels",
            provider_id="42",
            query=query,
            source_page="https://www.pexels.com/video/42/",
            creator_name="Alice",
            creator_page="https://www.pexels.com/@alice",
            title="person working at computer",
            description="repetitive creative computer work",
            duration=8.0,
            width=1080,
            height=1920,
            orientation="portrait",
            preview_url="https://images.example/42.jpg",
            selected_rendition_url="https://cdn.example/42.mp4?temporary=1",
            rendition_width=1080,
            rendition_height=1920,
            rights_state="provider_stock_terms",
            provider_rank=0,
        )]


class FakeCache(AssetCache):
    async def _fetch_bytes(self, url):
        return b"fake-jpeg"


def test_online_dry_run_persists_plan_review_and_benchmark(tmp_path):
    transcript = {
        "source": "reel.mp4",
        "timeline_fps": 25,
        "timeline_start_frame": 0,
        "language": "it",
        "segments": [
            {"start": 0.0, "end": 2.0, "text": "Ciao, ti spiego il problema.", "words": []},
            {"start": 2.0, "end": 4.0, "text": "Passavo ore a fare tutto manualmente.", "words": []},
        ],
    }
    outline = {"beats": [
        {"id": "intro", "start_seconds": 0.0, "end_seconds": 2.0, "intent": "hook", "broll_queries": []},
        {"id": "manual", "start_seconds": 2.0, "end_seconds": 4.0, "intent": "manual repetitive work",
         "broll_queries": ["frustrated creative repetitive computer work"]},
    ]}
    transcript_path = tmp_path / "transcript.json"
    outline_path = tmp_path / "outline.json"
    transcript_path.write_text(json.dumps(transcript), encoding="utf-8")
    outline_path.write_text(json.dumps(outline), encoding="utf-8")

    cache = FakeCache(tmp_path / "cache")
    ranker = QwenMultimodalRanker(
        client_id="rambla",
        embed=lambda items: [[1.0, 0.0]] + [[0.86, 0.5] for _ in items[1:]],
        rerank=None,
    )
    engine = OnlineSourcingEngine(sources=[FakeSource()], cache=cache, ranker=ranker)
    output = tmp_path / "run"

    plan = run_online_from_artifacts(
        transcript_path,
        outline_path,
        output,
        client_id="rambla",
        source_frames=100,
        sourcing_engine=engine,
    )

    saved = json.loads((output / "edit-plan.json").read_text(encoding="utf-8"))
    benchmark = json.loads((output / "online-sourcing-benchmark.json").read_text(encoding="utf-8"))
    html = (output / "review.html").read_text(encoding="utf-8")

    assert plan["beats"][1]["action"] == "BROLL"
    assert saved["beats"][1]["selected_asset"]["source"] == "pexels"
    assert saved["beats"][1]["selected_asset"]["provider_id"] == "42"
    assert saved["beats"][1]["selected_asset"]["selected_full_download"] is False
    assert benchmark["sourced_beats"] == 1
    assert benchmark["candidate_count"] == 1
    assert benchmark["resolve_calls"] == 0
    assert "pexels:42" in html
    assert "Candidate review" in html
    serialized = (output / "edit-plan.json").read_text(encoding="utf-8") + html
    assert "cdn.example" not in serialized
    assert "temporary=1" not in serialized
