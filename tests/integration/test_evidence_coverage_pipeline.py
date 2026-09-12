from __future__ import annotations

import json
from pathlib import Path

from backend.app.acquisition import AcquiredArtifact
from backend.app.asset_cache import PreviewAsset
from backend.app.online_assets import RemoteCandidate
from backend.app.online_sourcing import OnlineSourcingEngine
from backend.app.online_sourcing_cli import run_online_from_artifacts
from backend.app.qwen_stack import QwenMultimodalRanker
from backend.app.youtube_source import YouTubeOnlineSourceAdapter, YouTubeSource


class FakeCache:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.window_calls = 0

    async def materialize_preview(self, candidate):
        path = self.root / f"{candidate.provider}-{candidate.provider_id}.jpg"
        path.write_bytes(f"preview-{candidate.provider}-{candidate.provider_id}".encode())
        return PreviewAsset(
            path=path,
            metadata_path=self.root / f"{candidate.provider}-{candidate.provider_id}.json",
            sha256=f"{candidate.provider}-{candidate.provider_id}",
            cache_hit=False,
        )

    async def materialize_acquired_window(
        self,
        *,
        provider,
        provider_id,
        source_page,
        source_start_seconds,
        source_end_seconds,
        rights_state,
        acquire,
        kind="video_window",
    ):
        self.window_calls += 1
        path = self.root / f"window-{provider}-{provider_id}.mp4"
        await acquire(path)
        return type(
            "CachedWindow",
            (),
            {"path": path, "metadata_path": path.with_suffix(".json"), "sha256": "windowhash", "cache_hit": False},
        )()


class FakeStockSource:
    async def search(self, query, *, orientation, min_duration, max_duration, limit):
        assert orientation is None
        return [
            RemoteCandidate(
                provider="pexels",
                provider_id="stock1",
                query=query,
                source_page="https://www.pexels.com/video/stock1/",
                creator_name="Stock Creator",
                creator_page="https://www.pexels.com/@stock",
                title="generic computer work",
                description="generic person working at a computer",
                duration=7.0,
                width=1080,
                height=1920,
                orientation="portrait",
                preview_url="https://images.pexels.com/stock1.jpg",
                selected_rendition_url="https://cdn.pexels.com/stock1.mp4",
                rendition_width=1080,
                rendition_height=1920,
                rights_state="provider_stock_terms",
                provider_rank=0,
            )
        ]


class FakeAcquisition:
    def __init__(self):
        self.requests = []

    def acquire(self, request, output_path):
        self.requests.append(request)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"only-the-short-youtube-window")
        return AcquiredArtifact(
            path=path,
            kind="video_window",
            source_start_seconds=request.start_seconds,
            source_end_seconds=request.end_seconds,
            sha256="fakehash",
            cache_hit=False,
        )


def test_long_video_evidence_beats_stock_and_only_short_window_is_acquired(tmp_path: Path) -> None:
    transcript = {
        "source": "reel.mp4",
        "timeline_fps": 25,
        "language": "it",
        "segments": [
            {"start": 0.0, "end": 6.0, "text": "Qui racconto il fatto preciso.", "words": []},
            {"start": 6.0, "end": 12.0, "text": "Poi torno a parlare in camera.", "words": []},
        ],
    }
    outline = {
        "beats": [
            {
                "id": "evidence",
                "start_seconds": 0.0,
                "end_seconds": 6.0,
                "intent": "show the exact named event",
                "broll_queries": ["exact named event interview"],
            },
            {
                "id": "speaker",
                "start_seconds": 6.0,
                "end_seconds": 12.0,
                "intent": "return to speaker",
                "broll_queries": [],
            },
        ]
    }
    transcript_path = tmp_path / "transcript.json"
    outline_path = tmp_path / "outline.json"
    transcript_path.write_text(json.dumps(transcript), encoding="utf-8")
    outline_path.write_text(json.dumps(outline), encoding="utf-8")

    async def discover(_query: str, _limit: int):
        return [
            {
                "id": "yt1",
                "title": "exact named event interview",
                "duration": 600.0,
                "channel": "Evidence Channel",
                "width": 1920,
                "height": 1080,
                "thumbnail": "https://i.ytimg.com/vi/yt1/hqdefault.jpg",
                "scene_evidence": [
                    {
                        "timestamp_seconds": 76.75,
                        "text": "exact named event appears here",
                        "metadata_score": 1.0,
                    }
                ],
            }
        ]

    youtube = YouTubeOnlineSourceAdapter(YouTubeSource(discover=discover))
    cache = FakeCache(tmp_path / "cache")

    def embed(items):
        vectors = [[1.0, 0.0]]
        for item in items[1:]:
            name = Path(item).name
            if name.startswith("youtube-"):
                vectors.append([1.0, 0.0])
            else:
                vectors.append([0.8, 0.6])
        return vectors

    engine = OnlineSourcingEngine(
        sources=[youtube, FakeStockSource()],
        cache=cache,
        ranker=QwenMultimodalRanker(client_id="rambla", embed=embed, rerank=None),
        max_results_per_query=5,
        max_preview_candidates=5,
        download_selected=False,
    )
    acquisition = FakeAcquisition()
    output = tmp_path / "run"

    plan = run_online_from_artifacts(
        transcript_path,
        outline_path,
        output,
        client_id="rambla",
        source_frames=300,
        sourcing_engine=engine,
        acquisition_adapter=acquisition,
    )

    assert len(plan["coverage_slots"]) == 1
    slot = plan["coverage_slots"][0]
    assert 2.5 <= slot["end_seconds"] - slot["start_seconds"] <= 4.5
    assert slot["proposal_A"]["source"] == "youtube"
    assert slot["proposal_B"]["source"] == "pexels"
    assert slot["proposal_A"]["source_start_seconds"] == 75.0
    assert slot["proposal_A"]["source_end_seconds"] == 78.5
    assert slot["proposal_A"]["acquired_path"].endswith(".mp4")
    assert slot["proposal_A"]["selected_full_download"] is True
    assert slot["proposal_A"]["rights_state"] == "review_required"
    assert slot["proposal_A"]["needs_tracking"] is True
    assert slot["proposal_B"]["needs_tracking"] is False
    assert plan["resolve_calls"] == 0
    assert len(acquisition.requests) == 1
    assert acquisition.requests[0].start_seconds == 75.0
    assert acquisition.requests[0].end_seconds == 78.5
    assert cache.window_calls == 1

    benchmark = json.loads((output / "online-sourcing-benchmark.json").read_text(encoding="utf-8"))
    assert benchmark["coverage_slot_count"] == 1
    assert benchmark["scene_localized_proposals"] >= 1
    assert benchmark["acquired_windows"] == 1
    assert benchmark["resolve_calls"] == 0

    html = (output / "review.html").read_text(encoding="utf-8")
    assert "youtube:yt1" in html
    assert "75.00–78.50s" in html
    assert "pexels:stock1" in html
