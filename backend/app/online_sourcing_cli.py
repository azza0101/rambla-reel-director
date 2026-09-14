"""End-to-end evidence sourcing dry run with zero Resolve mutation."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import inspect
import json
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol

from .acquisition import AcquisitionRequest
from .asset_cache import AssetCache
from .coverage import plan_coverage_slots
from .director_engine import FasterWhisperArtifact, build_edit_plan
from .director_preview import render_report
from .online_assets import PexelsSource
from .online_sourcing import OnlineSourcingEngine
from .qwen_stack import LocalQwenEmbedder, QwenConfig, QwenMultimodalRanker


class AcquisitionPort(Protocol):
    def acquire(self, request: AcquisitionRequest, output_path: Path) -> Any: ...


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _rehash_plan(plan: dict[str, Any]) -> None:
    snapshot = dict(plan)
    snapshot.pop("content_hash", None)
    canonical = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    plan["content_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def _source_outline(
    outline: dict[str, Any],
    engine: OnlineSourcingEngine,
    *,
    client_id: str,
) -> tuple[
    dict[str, list[dict[str, Any]]],
    list[dict[str, Any]],
    dict[str, list[dict[str, Any]]],
]:
    """Source each short coverage slot, preserving beat-level compatibility."""

    slots = plan_coverage_slots(outline["beats"])
    if not slots:
        return {}, [], {}

    tasks = []
    for slot in slots:
        duration = slot.duration_seconds
        tasks.append(
            engine.source_beat(
                beat_id=slot.id,
                client_id=client_id,
                queries=list(slot.queries)[: engine.max_queries],
                min_duration=max(1.0, min(duration, 3.0)),
                # Long-video evidence (interviews, social/repertory) must remain
                # eligible even though the editorial insert itself is only 3–4 s.
                max_duration=4 * 60 * 60,
                orientation=None,
            )
        )
    results = await asyncio.gather(*tasks)

    coverage_by_beat: dict[str, list[dict[str, Any]]] = {}
    candidate_by_beat_and_id: dict[str, dict[str, dict[str, Any]]] = {}
    annotated_results: list[dict[str, Any]] = []

    for slot, result in zip(slots, results):
        proposals = result.get("proposals") or {}
        row = asdict(slot)
        row.update(
            {
                "proposal_A": proposals.get("proposal_A"),
                "proposal_B": proposals.get("proposal_B"),
                "proposal_C": proposals.get("proposal_C"),
                "selected_proposal_id": (
                    proposals.get("proposal_A", {}).get("id")
                    if isinstance(proposals.get("proposal_A"), dict)
                    else None
                ),
                "review_state": proposals.get("review_state", "NO_VISUAL_FOUND"),
                "sourcing_errors": result.get("errors", []),
            }
        )
        coverage_by_beat.setdefault(slot.beat_id, []).append(row)

        bucket = candidate_by_beat_and_id.setdefault(slot.beat_id, {})
        for candidate in result.get("candidates", []):
            candidate_id = str(candidate.get("id") or "")
            if not candidate_id:
                continue
            current = bucket.get(candidate_id)
            if current is None or float(candidate.get("score", 0.0)) > float(current.get("score", 0.0)):
                bucket[candidate_id] = candidate

        annotated = dict(result)
        annotated["coverage_slot_id"] = slot.id
        annotated["parent_beat_id"] = slot.beat_id
        annotated["coverage_start_seconds"] = slot.start_seconds
        annotated["coverage_end_seconds"] = slot.end_seconds
        annotated_results.append(annotated)

    candidate_map = {
        beat_id: sorted(rows.values(), key=lambda item: (-float(item.get("score", 0.0)), str(item.get("id", ""))))
        for beat_id, rows in candidate_by_beat_and_id.items()
    }
    return candidate_map, annotated_results, coverage_by_beat


async def _acquire_bounded_proposals(
    sourcing_results: list[dict[str, Any]],
    engine: OnlineSourcingEngine,
    acquisition_adapter: AcquisitionPort,
    *,
    acquire_alternates: bool,
) -> int:
    """Materialize only selected localized long-video windows.

    Proposal A is acquired by default. Proposal B is fetched only when the
    caller explicitly requests alternate media, keeping bandwidth proportional
    to editorial need rather than source duration.
    """

    cache = engine.cache
    if not hasattr(cache, "materialize_acquired_window"):
        raise ValueError("sourcing cache does not support bounded evidence windows")
    keys = ("proposal_A", "proposal_B") if acquire_alternates else ("proposal_A",)
    acquired = 0

    for result in sourcing_results:
        proposals = result.get("proposals") or {}
        for key in keys:
            proposal = proposals.get(key)
            if not isinstance(proposal, dict):
                continue
            if proposal.get("acquisition_mode") != "bounded_window":
                continue
            start = proposal.get("source_start_seconds")
            end = proposal.get("source_end_seconds")
            source_page = proposal.get("source_page")
            if not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or not source_page:
                continue
            request = AcquisitionRequest(
                source_url=str(source_page),
                start_seconds=float(start),
                end_seconds=float(end),
                margin_seconds=2.0,
                mode="video_window",
            )

            async def acquire_to(path: Path, req: AcquisitionRequest = request) -> None:
                produced = acquisition_adapter.acquire(req, path)
                if inspect.isawaitable(produced):
                    await produced

            cached = await cache.materialize_acquired_window(  # type: ignore[attr-defined]
                provider=str(proposal.get("source") or "online"),
                provider_id=str(proposal.get("provider_id") or proposal.get("id") or "unknown"),
                source_page=str(source_page),
                source_start_seconds=float(start),
                source_end_seconds=float(end),
                rights_state=str(proposal.get("rights_state") or "review_required"),
                acquire=acquire_to,
                kind="video_window",
            )
            proposal.update(
                {
                    "acquired_path": str(cached.path),
                    "path": str(cached.path),
                    "kind": "video",
                    "content_sha256": cached.sha256,
                    "selected_full_download": True,
                    "acquisition_cache_hit": bool(cached.cache_hit),
                }
            )
            acquired += 1
    return acquired


def _count_scene_localized(sourcing_results: list[dict[str, Any]]) -> int:
    return sum(
        int(
            isinstance(result.get("proposals", {}).get(key), dict)
            and isinstance(result["proposals"][key].get("source_start_seconds"), (int, float))
            and isinstance(result["proposals"][key].get("source_end_seconds"), (int, float))
        )
        for result in sourcing_results
        for key in ("proposal_A", "proposal_B", "proposal_C")
    )


def _downloaded_bytes(sourcing_results: list[dict[str, Any]]) -> int:
    total = 0
    for result in sourcing_results:
        for key in ("proposal_A", "proposal_B", "proposal_C"):
            proposal = result.get("proposals", {}).get(key)
            if not isinstance(proposal, dict) or not proposal.get("acquired_path"):
                continue
            try:
                total += Path(str(proposal["acquired_path"])).stat().st_size
            except OSError:
                continue
    return total


def run_online_from_artifacts(
    transcript_path: Path,
    outline_path: Path,
    output_dir: Path,
    *,
    client_id: str,
    source_frames: int,
    sourcing_engine: OnlineSourcingEngine,
    acquisition_adapter: AcquisitionPort | None = None,
    acquire_alternates: bool = False,
) -> dict[str, Any]:
    if not client_id:
        raise ValueError("client_id is required")
    if source_frames <= 0:
        raise ValueError("source_frames must be positive")
    started = time.perf_counter()
    transcript = FasterWhisperArtifact(transcript_path).load()
    outline = json.loads(outline_path.read_text(encoding="utf-8"))
    normalized = dict(transcript)
    normalized["segments"] = [
        dict(segment, text=" ".join(str(segment["text"]).split()))
        for segment in transcript["segments"]
    ]

    sourcing_started = time.perf_counter()
    candidate_map, sourcing_results, coverage_map = asyncio.run(
        _source_outline(outline, sourcing_engine, client_id=client_id)
    )
    sourcing_seconds = time.perf_counter() - sourcing_started

    acquisition_seconds = 0.0
    acquired_windows = 0
    if acquisition_adapter is not None:
        acquisition_started = time.perf_counter()
        acquired_windows = asyncio.run(
            _acquire_bounded_proposals(
                sourcing_results,
                sourcing_engine,
                acquisition_adapter,
                acquire_alternates=acquire_alternates,
            )
        )
        acquisition_seconds = time.perf_counter() - acquisition_started

    plan_started = time.perf_counter()
    plan = build_edit_plan(
        normalized,
        outline,
        [],
        client_id=client_id,
        source_frames=source_frames,
        candidate_assets_by_beat=candidate_map,
        coverage_slots_by_beat=coverage_map,
    )
    # Analyze is explicitly Resolve-independent. Persist that invariant in the
    # review artifact so the integration gate can prove no timeline operation occurred.
    plan["resolve_calls"] = 0
    _rehash_plan(plan)
    plan_seconds = time.perf_counter() - plan_started

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "transcript-raw.json", transcript)
    _write_json(output_dir / "transcript-normalized.json", normalized)
    _write_json(output_dir / "semantic-beats.json", outline)
    _write_json(output_dir / "online-candidates.json", sourcing_results)
    _write_json(output_dir / "edit-plan.json", plan)
    (output_dir / "review.html").write_text(render_report(plan), encoding="utf-8")

    proposal_count = sum(
        int(isinstance(result.get("proposals", {}).get(key), dict))
        for result in sourcing_results
        for key in ("proposal_A", "proposal_B", "proposal_C")
    )
    downloaded_selected = sum(
        int(
            isinstance(result.get("proposals", {}).get("proposal_A"), dict)
            and bool(result["proposals"]["proposal_A"].get("selected_full_download"))
        )
        for result in sourcing_results
    )
    benchmark = {
        "schema_version": "online-sourcing-benchmark-2",
        "sourced_beats": len({row.get("parent_beat_id") for row in sourcing_results}),
        "coverage_slot_count": len(sourcing_results),
        "candidate_count": sum(len(row["candidates"]) for row in sourcing_results),
        "eligible_candidate_count": sum(int(row.get("eligible_candidate_count", len(row.get("candidates", [])))) for row in sourcing_results),
        "rejected_candidate_count": sum(int(row.get("rejected_candidate_count", 0)) for row in sourcing_results),
        "quality_floor_no_broll_count": sum(int(row.get("quality_floor_state") == "NO_BROLL_QUALITY_FLOOR") for row in sourcing_results),
        "source_class_search_rounds": sum(int(row.get("source_class_search_rounds", 0)) for row in sourcing_results),
        "generic_stock_selected_count": sum(int(row.get("generic_stock_selected_count", 0)) for row in sourcing_results),
        "distinct_proposal_source_count": sum(int(row.get("distinct_proposal_source_count", len({str(row.get("proposals", {}).get(key, {}).get("source")) for key in ("proposal_A", "proposal_B") if isinstance(row.get("proposals", {}).get(key), dict)}))) for row in sourcing_results),
        "proposal_count": proposal_count,
        "scene_localized_proposals": _count_scene_localized(sourcing_results),
        "acquired_windows": acquired_windows,
        "downloaded_bytes": _downloaded_bytes(sourcing_results),
        "preview_cache_hits": sum(int(row.get("preview_cache_hits", 0)) for row in sourcing_results),
        "selected_cache_hits": sum(int(bool(row.get("selected_cache_hit", False))) for row in sourcing_results),
        "downloaded_selected": downloaded_selected,
        "provider_errors": sum(len(row.get("errors", [])) for row in sourcing_results),
        "sourcing_seconds": round(sourcing_seconds, 4),
        "acquisition_seconds": round(acquisition_seconds, 4),
        "plan_seconds": round(plan_seconds, 4),
        "total_seconds": round(time.perf_counter() - started, 4),
        "resolve_calls": 0,
    }
    _write_json(output_dir / "online-sourcing-benchmark.json", benchmark)
    return plan


def _real_engine(
    *,
    client_id: str,
    pexels_api_key: str,
    model_root: Path,
    embedding_code_root: Path | None,
    cache_root: Path,
    max_candidates: int,
) -> OnlineSourcingEngine:
    config = QwenConfig(model_root=model_root, embedding_code_root=embedding_code_root)
    embedder = LocalQwenEmbedder(config)
    ranker = QwenMultimodalRanker(client_id=client_id, embed=embedder, rerank=None)
    return OnlineSourcingEngine(
        sources=[PexelsSource(pexels_api_key)],
        cache=AssetCache(cache_root),
        ranker=ranker,
        max_results_per_query=max_candidates,
        max_preview_candidates=max_candidates,
        download_selected=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search online evidence per short coverage slot, Qwen-rank previews and write a Resolve-independent review plan"
    )
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
    engine = _real_engine(
        client_id=args.client_id,
        pexels_api_key=key,
        model_root=args.model_root,
        embedding_code_root=args.embedding_code_root,
        cache_root=args.output_dir / "asset-cache",
        max_candidates=args.max_candidates,
    )
    plan = run_online_from_artifacts(
        args.transcript,
        args.outline,
        args.output_dir,
        client_id=args.client_id,
        source_frames=args.source_frames,
        sourcing_engine=engine,
    )
    benchmark = json.loads(
        (args.output_dir / "online-sourcing-benchmark.json").read_text(encoding="utf-8")
    )
    print(
        json.dumps(
            {
                "plan_hash": plan["content_hash"],
                "beats": len(plan["beats"]),
                "coverage_slots": benchmark["coverage_slot_count"],
                "proposal_count": benchmark["proposal_count"],
                "candidate_count": benchmark["candidate_count"],
                "downloaded_selected": benchmark["downloaded_selected"],
                "total_seconds": benchmark["total_seconds"],
                "review": str(args.output_dir / "review.html"),
            }
        )
    )


if __name__ == "__main__":
    main()
