"""End-to-end evidence sourcing dry run with zero Resolve mutation."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import inspect
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol

from .acquisition import AcquisitionRequest
from .asset_cache import AssetCache
from .coverage import plan_coverage_slots
from .editorial_import import retrieval_bundle
from .retrieval_ranker import create_retrieval_ranker
from .director_engine import FasterWhisperArtifact, build_edit_plan
from .director_preview import render_report
from .evidence_intent import plan_evidence_intent
from .online_assets import PexelsSource
from .online_sourcing import OnlineSourcingEngine
from .qwen_stack import LocalQwenEmbedder, QwenConfig, QwenMultimodalRanker
from .source_strategy import plan_source_strategy
from .taste_profile import TasteContext
from .visual_routing import plan_visual_route
from .visual_planner import merge_visual_diagnostics, persist_visual_plan
from .youtube_source import YouTubeOnlineSourceAdapter, YouTubeSource


class AcquisitionPort(Protocol):
    def acquire(self, request: AcquisitionRequest, output_path: Path) -> Any: ...


class _YtDlpLogger:
    """Drop only yt-dlp's known Python 3.10 lifecycle notice."""
    exact_notice = "Deprecated Feature: Support for Python version 3.10 has been deprecated. Please update to Python 3.11 or above"
    def debug(self, _message: str) -> None: pass
    def info(self, _message: str) -> None: pass
    def warning(self, message: str) -> None:
        if str(message).strip().rstrip(".") != self.exact_notice:
            print(message, file=sys.stderr, flush=True)
    def error(self, message: str) -> None:
        print(message, file=sys.stderr, flush=True)


def _is_python310_notice(message: str) -> bool:
    text = str(message).strip().rstrip(".")
    return text.removeprefix("Deprecated Feature: ") == "Support for Python version 3.10 has been deprecated. Please update to Python 3.11 or above"


def _write_json(path: Path, value: Any) -> None:
    from .atomic_io import write_json
    write_json(path, value)


def _rehash_plan(plan: dict[str, Any]) -> None:
    snapshot = dict(plan)
    snapshot.pop("content_hash", None)
    canonical = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    plan["content_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _discover_youtube(query: str, limit: int, *, ydl_factory: Any = None) -> list[dict[str, Any]]:
    if ydl_factory is None:
        from yt_dlp import YoutubeDL
        class RamblaYoutubeDL(YoutubeDL):
            def deprecated_feature(self, message: str) -> None:
                if not _is_python310_notice(message):
                    super().deprecated_feature(message)
        ydl_factory = RamblaYoutubeDL
    options = {"quiet": True, "no_warnings": True, "skip_download": True, "extract_flat": "in_playlist", "logger": _YtDlpLogger()}
    with ydl_factory(options) as ydl:
        payload = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
    output = []
    for entry in payload.get("entries", []) if isinstance(payload, dict) else []:
        if not isinstance(entry, dict):
            continue
        thumbnails = [row for row in entry.get("thumbnails", []) if isinstance(row, dict) and row.get("url")]
        thumbnail = max(thumbnails, key=lambda row: int(row.get("width") or 0) * int(row.get("height") or 0), default={})
        output.append({
            "id": entry.get("id"), "title": entry.get("title"),
            "channel": entry.get("channel") or entry.get("uploader"),
            "duration": entry.get("duration"), "thumbnail": thumbnail.get("url") or entry.get("thumbnail"),
            "width": int(entry.get("width") or thumbnail.get("width") or 1280),
            "height": int(entry.get("height") or thumbnail.get("height") or 720),
        })
    return output


async def _source_outline(
    outline: dict[str, Any],
    engine: OnlineSourcingEngine,
    *,
    client_id: str,
    transcript: dict[str, Any] | None = None,
    taste_context: TasteContext | None = None,
    event_callback: Any = None,
) -> tuple[
    dict[str, list[dict[str, Any]]],
    list[dict[str, Any]],
    dict[str, list[dict[str, Any]]],
]:
    """Source each short coverage slot, preserving beat-level compatibility."""

    slots = plan_coverage_slots(outline["beats"])
    if not slots:
        return {}, [], {}

    providers = [str(getattr(source, "provider_name", "") or type(source).__name__.replace("OnlineSourceAdapter", "").replace("Source", "")).casefold() for source in engine.sources]
    if event_callback:
        event_callback("coverage", 100.0, "Coverage slots planned", slots=len(slots), providers=providers)

    engine.event_callback=event_callback
    tasks = []
    completed_count = 0
    route_by_slot: dict[str, Any] = {}
    context_by_slot: dict[str, str] = {}
    for slot in slots:
        duration = slot.duration_seconds
        editorial: dict[str, Any] = {}
        # Imported/API-first plans already contain shot-level visual intent and
        # concrete provider queries. Do not replace those with a second strategy
        # inferred from broad raw-ASR segments, which can leak nouns from adjacent
        # speech into the wrong beat (for example an "eco label" query on a
        # transport beat).
        imported_editorial = slot.evidence_class == "imported_editorial_shot"
        if taste_context is not None and not imported_editorial:
            context = " ".join(
                str(segment.get("text") or "").strip()
                for segment in (transcript or {}).get("segments", [])
                if float(segment.get("start", 0)) < slot.end_seconds
                and float(segment.get("end", 0)) > slot.start_seconds
            )
            planning_slot = {"transcript": context, "intent": slot.visual_intent}
            route = plan_visual_route(planning_slot, context, taste_context)
            route_by_slot[slot.id] = route
            context_by_slot[slot.id] = context
            intent = plan_evidence_intent(planning_slot, context, route, taste_context)
            editorial = {
                "taste": taste_context, "visual_route": route.route,
                "evidence_intent": intent,
                "source_strategy": plan_source_strategy(intent, route, taste_context),
            }
        if getattr(engine,'quality_mode',False):
            editorial['retrieval_intent']=slot.visual_intent
        task = engine.source_beat(
                beat_id=slot.id,
                client_id=client_id,
                queries=list(slot.queries)[: engine.max_queries],
                min_duration=max(1.0, min(duration, 3.0)),
                # Long-video evidence (interviews, social/repertory) must remain
                # eligible even though the editorial insert itself is only 3–4 s.
                max_duration=4 * 60 * 60,
                orientation=None,
                **editorial,
            )
        async def source_with_progress(slot_value: Any = slot, task_value: Any = task) -> Any:
            nonlocal completed_count
            result = await task_value
            completed_count += 1
            completed = completed_count
            progress = 100.0 * completed / len(slots)
            candidates = list(result.get("candidates") or [])
            rejected = list(result.get("rejected_candidates") or [])
            queries = list(slot_value.queries)[: engine.max_queries]
            if event_callback:
                event_callback("online_search", progress, f"Slot {completed}/{len(slots)} searched", slot_id=slot_value.id, query=queries, providers=providers, raw=result.get('raw_result_count',len(candidates)+len(rejected)), accepted=sum(c.get('clip_verified',False) for c in candidates) if getattr(engine,'quality_mode',False) else len(candidates), preview_pending=sum(c.get('quality_state')=='source_found' for c in candidates), rejected=len(rejected), errors=result.get("errors", []))
                event_callback("qwen_final", progress, f"Slot {completed}/{len(slots)} retrieval ranked", slot_id=slot_value.id, ranked=[{"id": row.get("id"), "score": row.get("qwen_score", row.get("score"))} for row in candidates[:3]])
                event_callback("bounded_acquisition", progress, f"Slot {completed}/{len(slots)} previews materialized", slot_id=slot_value.id, previews=sum(bool(row.get("preview_path")) for row in candidates), cache_hits=result.get("preview_cache_hits", 0))
                event_callback("review", progress, f"Slot {completed}/{len(slots)} proposals ready", slot_id=slot_value.id, proposals=sum(isinstance((result.get("proposals") or {}).get(key), dict) for key in ("proposal_A", "proposal_B", "proposal_C")))
            return result
        tasks.append(source_with_progress())
    results = await asyncio.gather(*tasks)
    if any(beat.get('visual_plan') for beat in outline['beats']):
        from .media_quality import diverse_candidates
        history = []
        for slot, result in zip(slots, results):
            candidates = list(result.get('candidates') or [])
            relevant = [c for c in candidates if c.get('quality_state')=='source_found' or float(c.get('score',0)) >= .42] if getattr(engine,'quality_mode',False) else [c for c in candidates if float(c.get('score',0)) >= .30]
            result['quality_rejected'] = len(candidates)-len(relevant)
            result['active_providers'] = providers
            from .media_quality import other_media_history
            cross_media = other_media_history(engine.retrieval_output, 'image', slot.beat_id) if hasattr(engine,'retrieval_output') else []
            if getattr(engine,'quality_mode',False):
                social,a = diverse_candidates([c for c in relevant if c.get('source')!='pexels'],history+cross_media,limit=3)
                stock,b = diverse_candidates([c for c in relevant if c.get('source')=='pexels'],history+cross_media+social,limit=3)
                retained,removed=social+stock,a+b
            else:
                retained, removed = diverse_candidates(relevant, history + cross_media, limit=3)
            history.extend(retained)
            result['candidates'] = retained
            result['duplicates_rejected'] = removed
            result.setdefault('raw_result_count',len(candidates) + len(result.get('rejected_candidates') or []))
            if getattr(engine,'quality_mode',False):
                result['eligible_candidate_count']=sum(c.get('clip_verified',False) for c in retained)
            valid = {c['id'] for c in retained}
            for key in ('proposal_A','proposal_B','proposal_C'):
                proposal = (result.get('proposals') or {}).get(key)
                if isinstance(proposal,dict) and proposal.get('id') not in valid:
                    result['proposals'][key] = None


    coverage_by_beat: dict[str, list[dict[str, Any]]] = {}
    candidate_by_beat_and_id: dict[str, dict[str, dict[str, Any]]] = {}
    annotated_results: list[dict[str, Any]] = []

    for slot, result in zip(slots, results):
        proposals = result.get("proposals") or {}
        row = asdict(slot)
        if slot.id in route_by_slot:
            route = route_by_slot[slot.id]
            row.update({"route_reason": route.reason, "route_confidence": route.confidence,
                        "transcript": context_by_slot[slot.id]})
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
                "visual_route": result.get("visual_route"),
                "evidence_intent": result.get("evidence_intent"),
                "source_strategy": result.get("source_strategy"),
                "searched_source_classes": result.get("searched_source_classes", []),
                "rejected_candidates": result.get("rejected_candidates", []),
                "quality_floor_state": result.get("quality_floor_state"),
                "presentation_mode": (
                    proposals.get("proposal_A", {}).get("recommended_presentation_mode")
                    if isinstance(proposals.get("proposal_A"), dict) else None
                ),
            }
        )
        coverage_by_beat.setdefault(slot.beat_id, []).append(row)

        bucket = candidate_by_beat_and_id.setdefault(slot.beat_id, {})
        eligible_candidates = (
            [proposals[key] for key in ("proposal_A", "proposal_B", "proposal_C")
             if isinstance(proposals.get(key), dict)]
            if taste_context is not None else result.get("candidates", [])
        )
        for candidate in eligible_candidates:
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
    taste_context: TasteContext | None = None,
    event_callback: Any = None,
    outline_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not client_id:
        raise ValueError("client_id is required")
    if source_frames <= 0:
        raise ValueError("source_frames must be positive")
    if taste_context is not None and taste_context.client_id != client_id:
        raise ValueError("taste context violates client isolation")
    started = time.perf_counter()
    transcript = FasterWhisperArtifact(transcript_path).load()
    stored_outline = json.loads(outline_path.read_text(encoding="utf-8"))
    outline = outline_override or stored_outline
    normalized = dict(transcript)
    normalized["segments"] = [
        dict(segment, text=" ".join(str(segment["text"]).split()))
        for segment in transcript["segments"]
    ]

    sourcing_started = time.perf_counter()
    candidate_map, sourcing_results, coverage_map = asyncio.run(
        _source_outline(outline, sourcing_engine, client_id=client_id,
                        transcript=normalized, taste_context=taste_context, event_callback=event_callback)
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
    external = any(b.get('external_plan') for b in outline['beats'])
    if external:
        # A retrieval report is not an edit decision. Preserve the supplied actions
        # and timing even when no usable media is found; no RuleDirector runs here.
        plan = {'schema_version':'imported-retrieval-review-1','client_id':client_id,
                'beats':[{**b['visual_plan'],'candidates':candidate_map.get(b['id'],[])} for b in outline['beats']],
                'coverage_slots':[r for rows in coverage_map.values() for r in rows]}
    else:
        plan = build_edit_plan(
            normalized,
            outline,
            [],
            client_id=client_id,
            source_frames=source_frames,
            candidate_assets_by_beat=candidate_map,
            coverage_slots_by_beat=coverage_map,
            taste_context=taste_context,
        )
    # Analyze is explicitly Resolve-independent. Persist that invariant in the
    # review artifact so the integration gate can prove no timeline operation occurred.
    plan["resolve_calls"] = 0
    _rehash_plan(plan)
    plan_seconds = time.perf_counter() - plan_started

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "transcript-raw.json", transcript)
    _write_json(output_dir / "transcript-normalized.json", normalized)
    _write_json(output_dir / "semantic-beats.json", stored_outline)
    _write_json(output_dir / "online-candidates.json", sourcing_results)
    _write_json(output_dir / "edit-plan.json", plan)
    if external:
        import html
        report = '<!doctype html><meta charset="utf-8"><h1>Imported plan retrieval</h1><pre>'+html.escape(json.dumps(plan,ensure_ascii=False,indent=2))+'</pre>'
    else:
        report = render_report(plan)
    (output_dir / "review.html").write_text(report, encoding="utf-8")

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
        "duplicates_rejected": sum(int(row.get("duplicates_rejected",0)) for row in sourcing_results),
        "quality_rejected": sum(int(row.get("quality_rejected",0)) for row in sourcing_results),
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
    pexels_api_key: str | None,
    model_root: Path,
    embedding_code_root: Path | None,
    cache_root: Path,
    max_candidates: int,
    embedder: LocalQwenEmbedder | None = None,
    providers: set[str] | None = None,
) -> OnlineSourcingEngine:
    ranker = create_retrieval_ranker(client_id, model_root, embedding_code_root)
    provider_filter = {str(value).casefold().strip() for value in (providers or set()) if str(value).strip()}
    sources: list[Any] = []
    include_youtube = not provider_filter or "youtube" in provider_filter
    vertical_names = {"youtube_shorts", "tiktok", "instagram", "web_video"}
    requested_vertical = vertical_names if not provider_filter else (provider_filter & vertical_names)

    if include_youtube or requested_vertical:
        if provider_filter:
            from .vertical_social import build_default_vertical_sources
            vertical_sources = [
                source for source in build_default_vertical_sources()
                if str(getattr(source, "provider_name", "")).casefold() in requested_vertical
            ]
            sources.append(
                YouTubeOnlineSourceAdapter(
                    YouTubeSource(discover=_discover_youtube),
                    vertical_sources=vertical_sources,
                    include_base_youtube=include_youtube,
                )
            )
        else:
            sources.append(YouTubeOnlineSourceAdapter(YouTubeSource(discover=_discover_youtube)))

    if pexels_api_key and (not provider_filter or "pexels" in provider_filter):
        sources.append(PexelsSource(pexels_api_key))
    engine = OnlineSourcingEngine(
        sources=sources,
        cache=AssetCache(cache_root),
        ranker=ranker,
        max_results_per_query=max_candidates,
        max_preview_candidates=max_candidates,
        download_selected=False,
    )
    engine.quality_mode = True
    engine.query_intents = {}
    return engine


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search online evidence per short coverage slot, Qwen-rank previews and write a Resolve-independent review plan"
    )
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--outline", type=Path, required=True)
    parser.add_argument("--chunks", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--source-frames", type=int, required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--embedding-code-root", type=Path)
    parser.add_argument('--beat-ids',nargs='+')
    parser.add_argument(
        "--providers",
        nargs="+",
        choices=("youtube", "youtube_shorts", "tiktok", "instagram", "web_video", "pexels"),
    )
    parser.add_argument("--pexels-key-env", default="PEXELS_API_KEY")
    parser.add_argument("--max-candidates", type=int, default=12)
    args = parser.parse_args()
    if args.max_candidates <= 0 or args.max_candidates > 40:
        raise SystemExit("--max-candidates must be between 1 and 40")
    from .project_config import load_project_credentials,provider_status
    load_project_credentials()
    print("RAMBLA_EVENT "+json.dumps({"stage":"online_search","message":"Provider configuration","data":provider_status()}),flush=True)
    key = os.environ.get(args.pexels_key_env)
    chunks_path = args.chunks or args.output_dir / "semantic-chunks.json"
    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    stored_outline = json.loads(args.outline.read_text(encoding="utf-8"))
    args.output_dir, chunks, visual_plan, imported_outline = retrieval_bundle(args.output_dir)
    sourcing_outline = {**stored_outline, **imported_outline}
    if args.beat_ids:sourcing_outline['beats']=[b for b in sourcing_outline['beats'] if b['id'] in args.beat_ids]
    engine = _real_engine(
        client_id=args.client_id,
        pexels_api_key=key,
        model_root=args.model_root,
        embedding_code_root=args.embedding_code_root,
        cache_root=args.output_dir / "asset-cache",
        max_candidates=args.max_candidates,
        providers=set(args.providers or ()),
    )
    engine.retrieval_output = args.output_dir
    engine.query_intents = {q: shot['description'] for beat in visual_plan['chunks'].values() for shot in beat['shots'] for q in shot['video_queries']}
    plan = run_online_from_artifacts(
        args.transcript,
        args.outline,
        args.output_dir,
        client_id=args.client_id,
        source_frames=args.source_frames,
        sourcing_engine=engine,
        event_callback=lambda stage, progress, message, **data: print("RAMBLA_EVENT " + json.dumps({"stage": stage, "progress": progress, "message": message, "data": data}, ensure_ascii=False), flush=True),
        outline_override=sourcing_outline,
    )
    sourcing_rows = json.loads((args.output_dir / "online-candidates.json").read_text(encoding="utf-8"))
    video_diagnostics: dict[str, dict[str, Any]] = {}
    for row in sourcing_rows:
        chunk_id = str(row.get("parent_beat_id") or "")
        target = video_diagnostics.setdefault(chunk_id, {"providers": [], "raw": 0, "accepted": 0, "rejected": 0, "proposals": 0, "errors": [], "selected": []})
        candidates = list(row.get("candidates") or [])
        shot_id = str(row.get('coverage_slot_id','')).split(':shot:')[-1] if ':shot:' in str(row.get('coverage_slot_id','')) else None
        for candidate in candidates: candidate['shot_id'] = shot_id
        rejected = list(row.get("rejected_candidates") or [])
        target["providers"] = sorted(set(target["providers"]) | set(row.get("active_providers", [])) | {str(candidate.get("source")) for candidate in candidates if candidate.get("source")})
        target["raw"] += int(row.get("raw_result_count") or len(candidates) + len(rejected))
        target["accepted"] += sum(c.get('clip_verified',False) for c in candidates) if row.get('quality_version') else len(candidates)
        target['preview_pending']=target.get('preview_pending',0)+sum(c.get('quality_state')=='source_found' for c in candidates)
        target["rejected"] += len(rejected)
        target["proposals"] += sum(isinstance((row.get("proposals") or {}).get(key), dict) for key in ("proposal_A", "proposal_B", "proposal_C"))
        target["errors"].extend(row.get("errors") or [])
        planned_shots = visual_plan.get("chunks", {}).get(chunk_id, {}).get("shots", [])
        query_to_shot = {query: shot.get("shot_id") for shot in planned_shots for query in shot.get("video_queries", [])}
        target["selected"].extend({"asset_id": candidate.get("id"), "shot_id": query_to_shot.get(candidate.get("query")), "query": candidate.get("query"), "provider": candidate.get("source"), "score": candidate.get("qwen_score", candidate.get("score"))} for candidate in candidates[:3])
    persist_visual_plan(args.output_dir / "online-candidates.json", sourcing_rows)
    for target in video_diagnostics.values():
        target["zero_result_reason"] = (
            None if target["accepted"] else
            "provider search failed" if target["errors"] else
            "0 provider results" if target["raw"] == 0 else
            "all candidates rejected"
        )
    persist_visual_plan(args.output_dir / "video-retrieval-plan.json", merge_visual_diagnostics(visual_plan, "video", video_diagnostics))
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
