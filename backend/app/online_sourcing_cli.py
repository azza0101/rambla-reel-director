"""End-to-end online sourcing dry run with zero Resolve mutation."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

from .asset_cache import AssetCache
from .director_engine import FasterWhisperArtifact, build_edit_plan
from .director_preview import render_report
from .online_assets import PexelsSource
from .online_sourcing import OnlineSourcingEngine
from .qwen_stack import LocalQwenEmbedder, QwenConfig, QwenMultimodalRanker


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


async def _source_outline(outline: dict[str, Any], engine: OnlineSourcingEngine, *, client_id: str):
    tasks, beat_ids = [], []
    for beat in outline["beats"]:
        queries = [str(v).strip() for v in beat.get("broll_queries", []) if str(v).strip()]
        if not queries:
            continue
        duration = max(0.1, float(beat["end_seconds"]) - float(beat["start_seconds"]))
        beat_ids.append(beat["id"])
        tasks.append(engine.source_beat(
            beat_id=beat["id"], client_id=client_id, queries=queries[:engine.max_queries],
            min_duration=max(1.0, min(duration * 0.5, 3.0)),
            max_duration=max(15.0, min(duration * 4.0, 90.0)), orientation="portrait"))
    if not tasks:
        return {}, []
    results = await asyncio.gather(*tasks)
    return {beat_id: result["candidates"] for beat_id, result in zip(beat_ids, results)}, results


def run_online_from_artifacts(transcript_path: Path, outline_path: Path, output_dir: Path, *,
                              client_id: str, source_frames: int,
                              sourcing_engine: OnlineSourcingEngine) -> dict[str, Any]:
    if not client_id:
        raise ValueError("client_id is required")
    if source_frames <= 0:
        raise ValueError("source_frames must be positive")
    started = time.perf_counter()
    transcript = FasterWhisperArtifact(transcript_path).load()
    outline = json.loads(outline_path.read_text(encoding="utf-8"))
    normalized = dict(transcript)
    normalized["segments"] = [dict(s, text=" ".join(str(s["text"]).split())) for s in transcript["segments"]]

    sourcing_started = time.perf_counter()
    candidate_map, sourcing_results = asyncio.run(_source_outline(outline, sourcing_engine, client_id=client_id))
    sourcing_seconds = time.perf_counter() - sourcing_started
    plan_started = time.perf_counter()
    plan = build_edit_plan(normalized, outline, [], client_id=client_id, source_frames=source_frames,
                           candidate_assets_by_beat=candidate_map)
    plan_seconds = time.perf_counter() - plan_started

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "transcript-raw.json", transcript)
    _write_json(output_dir / "transcript-normalized.json", normalized)
    _write_json(output_dir / "semantic-beats.json", outline)
    _write_json(output_dir / "online-candidates.json", sourcing_results)
    _write_json(output_dir / "edit-plan.json", plan)
    (output_dir / "review.html").write_text(render_report(plan), encoding="utf-8")
    benchmark = {
        "schema_version": "online-sourcing-benchmark-1",
        "sourced_beats": len(sourcing_results),
        "candidate_count": sum(len(row["candidates"]) for row in sourcing_results),
        "preview_cache_hits": sum(int(row.get("preview_cache_hits", 0)) for row in sourcing_results),
        "selected_cache_hits": sum(int(bool(row.get("selected_cache_hit", False))) for row in sourcing_results),
        "downloaded_selected": sum(int(bool(row.get("candidates") and row["candidates"][0].get("selected_full_download"))) for row in sourcing_results),
        "provider_errors": sum(len(row.get("errors", [])) for row in sourcing_results),
        "sourcing_seconds": round(sourcing_seconds, 4),
        "plan_seconds": round(plan_seconds, 4),
        "total_seconds": round(time.perf_counter() - started, 4),
        "resolve_calls": 0,
    }
    _write_json(output_dir / "online-sourcing-benchmark.json", benchmark)
    return plan


def _real_engine(*, client_id: str, pexels_api_key: str, model_root: Path,
                 embedding_code_root: Path | None, cache_root: Path,
                 max_candidates: int) -> OnlineSourcingEngine:
    config = QwenConfig(model_root=model_root, embedding_code_root=embedding_code_root)
    embedder = LocalQwenEmbedder(config)
    ranker = QwenMultimodalRanker(client_id=client_id, embed=embedder, rerank=None)
    return OnlineSourcingEngine(
        sources=[PexelsSource(pexels_api_key)], cache=AssetCache(cache_root), ranker=ranker,
        max_results_per_query=max_candidates, max_preview_candidates=max_candidates,
        download_selected=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Search Pexels, Qwen-rank previews and write a Resolve-independent RAMBLA review plan")
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--outline", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--source-frames", type=int, required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--embedding-code-root", type=Path)
    parser.add_argument("--pexels-key-env", default="PEXELS_API_KEY")
    parser.add_argument("--max-candidates", type=int, default=12)
    args = parser.parse_args()
    if args.max_candidates <= 0 or args.max_candidates > 40:
        raise SystemExit("--max-candidates must be between 1 and 40")
    key = os.environ.get(args.pexels_key_env)
    if not key:
        raise SystemExit(f"credential required: set {args.pexels_key_env}")
    engine = _real_engine(client_id=args.client_id, pexels_api_key=key,
                          model_root=args.model_root, embedding_code_root=args.embedding_code_root,
                          cache_root=args.output_dir / "asset-cache", max_candidates=args.max_candidates)
    plan = run_online_from_artifacts(args.transcript, args.outline, args.output_dir,
                                     client_id=args.client_id, source_frames=args.source_frames,
                                     sourcing_engine=engine)
    benchmark = json.loads((args.output_dir / "online-sourcing-benchmark.json").read_text(encoding="utf-8"))
    print(json.dumps({"plan_hash": plan["content_hash"], "beats": len(plan["beats"]),
                      "sourced_beats": benchmark["sourced_beats"],
                      "candidate_count": benchmark["candidate_count"],
                      "downloaded_selected": benchmark["downloaded_selected"],
                      "total_seconds": benchmark["total_seconds"],
                      "review": str(args.output_dir / "review.html")}))


if __name__ == "__main__":
    main()
