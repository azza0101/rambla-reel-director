"""Resumable semantic image sourcing with local Qwen visual ranking."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .debug_run_cli import discover_image_candidates, _event
from .editorial_import import retrieval_bundle
from .retrieval_ranker import create_retrieval_ranker
from .visual_planner import merge_visual_diagnostics, persist_visual_plan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--outline", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--embedding-code-root", type=Path)
    parser.add_argument("--relevance-floor", type=float, default=0.30)
    args = parser.parse_args()
    chunks = json.loads(args.chunks.read_text(encoding="utf-8"))
    outline = json.loads(args.outline.read_text(encoding="utf-8"))
    args.output_dir, chunks, visual_plan, imported_outline = retrieval_bundle(args.output_dir)
    outline = {**outline, **imported_outline}
    ranker = create_retrieval_ranker(args.client_id, args.model_root, args.embedding_code_root)
    sourcing_started = time.perf_counter()
    payload = discover_image_candidates(
        chunks, args.output_dir, outline=outline, ranker=ranker, client_id=args.client_id,
        relevance_floor=args.relevance_floor, event_callback=_event, visual_plan=visual_plan,
    )
    sourcing_seconds = round(time.perf_counter()-sourcing_started,4)
    persist_visual_plan(args.output_dir / "image-sourcing-timings.json", {"sourcing_seconds":sourcing_seconds,"chunks":len(chunks)})
    visual_plan = merge_visual_diagnostics(visual_plan, "image", {
        chunk_id: {
            "providers": row.get("active_providers", []), "raw": row.get("raw_count", 0),
            "accepted": row.get("accepted_count", 0), "zero_result_reason": row.get("zero_result_reason"),
            "errors": row.get("errors", []), "selected": [
                {"asset_id": candidate.get("id"), "shot_id": candidate.get("shot_id"), "query": candidate.get("matched_query"), "provider": candidate.get("provider"), "score": candidate.get("score")}
                for candidate in row.get("candidates", [])
            ],
        } for chunk_id, row in payload.get("chunks", {}).items()
    })
    persist_visual_plan(args.output_dir / "image-retrieval-plan.json", visual_plan)
    print(json.dumps({
        "sourcing_seconds": sourcing_seconds,
        "chunks": len(payload.get("chunks", {})),
        "covered": sum(bool(row.get("candidates")) for row in payload.get("chunks", {}).values()),
        "cache_reused_chunks": payload.get("cache_reused_chunks", 0),
        "retried_chunks": payload.get("retried_chunks", 0),
        "active_providers": payload.get("active_providers", []),
    }), flush=True)


if __name__ == "__main__":
    main()
