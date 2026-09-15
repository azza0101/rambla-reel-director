"""Resumable semantic image sourcing with local Qwen visual ranking."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .debug_run_cli import discover_image_candidates, _event
from .qwen_stack import LocalQwenEmbedder, QwenConfig, QwenMultimodalRanker


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--outline", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--embedding-code-root", type=Path)
    parser.add_argument("--relevance-floor", type=float, default=0.12)
    args = parser.parse_args()
    chunks = json.loads(args.chunks.read_text(encoding="utf-8"))
    outline = json.loads(args.outline.read_text(encoding="utf-8"))
    embedder = LocalQwenEmbedder(QwenConfig(model_root=args.model_root, embedding_code_root=args.embedding_code_root))
    ranker = QwenMultimodalRanker(client_id=args.client_id, embed=embedder, rerank=None, top_k=16)
    payload = discover_image_candidates(
        chunks, args.output_dir, outline=outline, ranker=ranker, client_id=args.client_id,
        relevance_floor=args.relevance_floor, event_callback=_event,
    )
    print(json.dumps({
        "chunks": len(payload.get("chunks", {})),
        "covered": sum(bool(row.get("candidates")) for row in payload.get("chunks", {}).values()),
        "cache_reused_chunks": payload.get("cache_reused_chunks", 0),
        "retried_chunks": payload.get("retried_chunks", 0),
        "active_providers": payload.get("active_providers", []),
    }), flush=True)


if __name__ == "__main__":
    main()
