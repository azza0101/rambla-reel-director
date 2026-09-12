"""Compare heuristic and optional Qwen planning on identical offline inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from .director_engine import build_edit_plan
from .qwen_stack import (LocalQwenDirectorGenerator, LocalQwenEmbedder, LocalQwenReranker,
                         QwenConfig, capabilities, compose_qwen_plan, offline_model_environment)


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _summary(plan: dict[str, Any], duration_ms: float) -> dict[str, Any]:
    return {"status": "COMPLETE", "duration_ms": round(duration_ms, 3), "plan_hash": plan["content_hash"],
            "beat_count": len(plan["beats"]), "caption_count": len(plan["captions"]),
            "decisions": [{"id": beat["id"], "action": beat["action"],
                           "selected_asset_id": beat["selected_asset"]["id"] if beat["selected_asset"] else None,
                           "providers": beat["providers"]} for beat in plan["beats"]]}


def benchmark(transcript: dict[str, Any], outline: dict[str, Any], assets: list[dict[str, Any]], *,
              client_id: str, source_frames: int, config: QwenConfig) -> dict[str, Any]:
    started = time.perf_counter()
    heuristic = build_edit_plan(transcript, outline, assets, client_id=client_id, source_frames=source_frames)
    elapsed = (time.perf_counter() - started) * 1000
    caps = capabilities(config)
    required = ("director", "embedding", "reranker")
    blockers = {role: caps[role]["reason"] for role in required if not caps[role]["available"]}
    report = {"schema_version": "director-benchmark-1",
              "same_input": {"transcript_hash": _hash(transcript), "outline_hash": _hash(outline),
                             "asset_manifest_hash": _hash(assets), "client_id": client_id,
                             "source_frames": source_frames, "beat_ids": [beat["id"] for beat in outline["beats"]]},
              "capabilities": caps, "heuristic": _summary(heuristic, elapsed)}
    if len(blockers) == len(required):
        report["qwen"] = {"status": "UNAVAILABLE", "duration_ms": None, "models_exercised": [],
                          "blockers": blockers, "decisions": None}
        return report
    started = time.perf_counter()
    exercised: list[str] = []
    try:
        generator = LocalQwenDirectorGenerator(config) if caps["director"]["available"] else None
        embedder = LocalQwenEmbedder(config) if caps["embedding"]["available"] else None
        reranker = LocalQwenReranker(config) if caps["reranker"]["available"] else None
        with offline_model_environment(config.model_root):
            qwen_plan = compose_qwen_plan(transcript, outline, assets, client_id=client_id, source_frames=source_frames,
                                          generator=generator, embedder=embedder, reranker=reranker,
                                          director_model=config.director_model)
        for adapter, name in ((generator, config.director_model), (embedder, "Qwen3-VL-Embedding-2B"),
                              (reranker, "Qwen3-VL-Reranker-2B")):
            if adapter is not None and adapter.completed_calls > 0:
                exercised.append(name)
        if not exercised:
            report["qwen"] = {"status": "FAILED_FALLBACK", "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                              "models_exercised": [], "blockers": {**blockers, "runtime": "no Qwen role completed inference"},
                              "decisions": None}
        else:
            report["qwen"] = {**_summary(qwen_plan, (time.perf_counter() - started) * 1000),
                              "status": "PARTIAL_COMPLETE" if blockers else "COMPLETE",
                              "models_exercised": exercised, "blockers": blockers}
    except Exception as exc:
        report["qwen"] = {"status": "FAILED_FALLBACK", "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                          "models_exercised": exercised, "blockers": {"runtime": f"{type(exc).__name__}: {exc}"},
                          "decisions": None}
    return report


def run_from_files(transcript_path: Path, outline_path: Path, manifest_path: Path, *, output_path: Path,
                   model_root: Path, source_frames: int) -> dict[str, Any]:
    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    outline = json.loads(outline_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    client_id = manifest["client_id"]
    if not client_id or any(asset.get("client_id") != client_id for asset in manifest["assets"]):
        raise ValueError("manifest mixes client assets")
    report = benchmark(transcript, outline, manifest["assets"], client_id=client_id,
                       source_frames=source_frames, config=QwenConfig(model_root=model_root))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare local heuristic/Qwen Director paths without Resolve")
    for name in ("transcript", "outline", "manifest", "output", "model-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--source-frames", type=int, required=True)
    args = parser.parse_args()
    report = run_from_files(args.transcript, args.outline, args.manifest, output_path=args.output,
                            model_root=args.model_root, source_frames=args.source_frames)
    print(json.dumps({"heuristic": report["heuristic"]["status"], "qwen": report["qwen"]["status"],
                      "blockers": report["qwen"]["blockers"]}))


if __name__ == "__main__":
    main()
