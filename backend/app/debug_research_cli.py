"""Dedicated per-beat media research worker.

This worker never runs ASR or semantic analysis. It snapshots current retrieval
artifacts, executes provider searches for one imported visual beat, then merges
replace/append results atomically. Failed provider runs restore previous state.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from .atomic_io import write_json
from .beat_research import merge_image_artifact, merge_video_rows
from .debug_run_cli import (
    DEFAULT_EMBEDDING_CODE, DEFAULT_MODEL_ROOT, DEFAULT_PIPELINE_PYTHON,
    _event, _probe, persist_video_diagnostics,
)
from .editorial_import import retrieval_bundle


def research_stage_type(beat_id: str, mode: str) -> str:
    beat_id = str(beat_id or "").strip()
    if not beat_id or ":" in beat_id: raise ValueError("invalid beat id")
    if mode not in {"replace", "append"}: raise ValueError("invalid research mode")
    return f"research:{mode}:{beat_id}"


def parse_research_stage(stage: str) -> tuple[str, str]:
    parts = str(stage or "").split(":", 2)
    if len(parts) != 3 or parts[0] != "research" or parts[1] not in {"replace", "append"} or not parts[2]:
        raise ValueError("invalid research stage")
    return parts[2], parts[1]


def _pipeline_python() -> str:
    return str(DEFAULT_PIPELINE_PYTHON if DEFAULT_PIPELINE_PYTHON.is_file() else Path(sys.executable))


def video_sourcing_command(
    output: Path,
    transcript_path: Path,
    outline_path: Path,
    client_id: str,
    source_frames: int,
    *,
    beat_id: str,
    research_mode: str,
    providers: tuple[str, ...] = (),
) -> list[str]:
    command = [
        _pipeline_python(), "-m", "backend.app.online_sourcing_cli",
        "--transcript", str(transcript_path), "--outline", str(outline_path),
        "--chunks", str(output / "semantic-chunks.json"), "--output-dir", str(output),
        "--client-id", client_id, "--source-frames", str(source_frames),
        "--model-root", str(DEFAULT_MODEL_ROOT), "--embedding-code-root", str(DEFAULT_EMBEDDING_CODE),
        "--beat-ids", beat_id,
    ]
    # Append asks providers for a wider discovery pool. Merge semantics still
    # enforce the same verification thresholds and project-wide dedupe.
    command += ["--max-candidates", "24" if research_mode == "append" else "12"]
    if providers:
        command += ["--providers", *providers]
    return command


def image_sourcing_command(output: Path, chunks_path: Path, outline_path: Path, client_id: str, *, beat_id: str, research_mode: str) -> list[str]:
    return [
        _pipeline_python(), "-m", "backend.app.image_sourcing_cli",
        "--chunks", str(chunks_path), "--outline", str(outline_path),
        "--output-dir", str(output), "--client-id", client_id,
        "--model-root", str(DEFAULT_MODEL_ROOT), "--embedding-code-root", str(DEFAULT_EMBEDDING_CODE),
        "--beat-ids", beat_id,
    ]


def _read_json(path: Path, default):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError): return default


def _snapshot(paths: list[Path]) -> dict[Path, bytes | None]:
    return {path: path.read_bytes() if path.is_file() else None for path in paths}


def _restore(snapshot: dict[Path, bytes | None]) -> None:
    for path, data in snapshot.items():
        if data is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".restore.tmp")
            temporary.write_bytes(data); temporary.replace(path)


def _clear_target_selection(path: Path, beat_id: str) -> None:
    payload = _read_json(path, None)
    if not isinstance(payload, dict) or not isinstance(payload.get("chunks"), dict): return
    row = payload["chunks"].get(beat_id)
    if not isinstance(row, dict): return
    row["selected_assets"] = []
    row["no_broll"] = False
    write_json(path, payload)


def run_research(
    *,
    video: Path,
    output: Path,
    beat_id: str,
    mode: str,
    client_id: str,
    providers: tuple[str, ...] = (),
) -> dict:
    if mode not in {"replace", "append"}: raise ValueError("research mode must be replace or append")
    if not video.is_file(): raise FileNotFoundError(video)
    transcript = output / "transcript-raw.json"; outline = output / "semantic-beats.json"; chunks_path = output / "semantic-chunks.json"
    for required in (transcript, outline, chunks_path):
        if not required.is_file(): raise RuntimeError("analysis required before beat research")
    retrieval_root, chunks, visual_plan, _ = retrieval_bundle(output)
    if beat_id not in {str(row.get("id")) for row in chunks}:
        raise ValueError("unknown visual beat")
    visual_beat = next((row for row in visual_plan.get("visual_beats", []) if str(row.get("id")) == beat_id), None)
    if isinstance(visual_beat, dict) and visual_beat.get("action") != "BROLL":
        raise ValueError("media research is only available for BROLL beats")

    video_artifact = retrieval_root / "online-candidates.json"
    image_artifact = retrieval_root / "image-candidates.json"
    diagnostic = retrieval_root / "video-sourcing-diagnostics.json"
    selection = retrieval_root / "selection-plan.json"
    tracked = [video_artifact, image_artifact, diagnostic, retrieval_root / "video-retrieval-plan.json", retrieval_root / "image-retrieval-plan.json", selection]
    snapshot = _snapshot(tracked)
    existing_video = _read_json(video_artifact, [])
    existing_images = _read_json(image_artifact, {"chunks": {}})
    _, source_frames = _probe(video)

    provider_scope = tuple(dict.fromkeys(str(value).casefold().strip() for value in providers if str(value).strip()))
    _event(
        "research", 1, "Beat media research started",
        beat_id=beat_id, mode=mode, providers=list(provider_scope),
    )
    try:
        if not provider_scope:
            subprocess.run(image_sourcing_command(output, chunks_path, outline, client_id, beat_id=beat_id, research_mode=mode), check=True)
            fresh_images = _read_json(image_artifact, {"chunks": {}})
            merged_images = merge_image_artifact(existing_images, fresh_images, beat_id, mode)
            write_json(image_artifact, merged_images)
            _event("research", 45, "Beat image research merged", beat_id=beat_id, mode=mode, candidates=len(merged_images.get("chunks", {}).get(beat_id, {}).get("candidates", [])))
        else:
            _event(
                "research", 35, "Provider-scoped video research; image search skipped",
                beat_id=beat_id, mode=mode, providers=list(provider_scope),
            )

        subprocess.run(
            video_sourcing_command(
                output, transcript, outline, client_id, source_frames,
                beat_id=beat_id, research_mode=mode, providers=provider_scope,
            ),
            check=True,
        )
        fresh_video = _read_json(video_artifact, [])
        merged_video = merge_video_rows(existing_video, fresh_video, beat_id, mode)
        write_json(video_artifact, merged_video)
        persist_video_diagnostics(retrieval_root)
        if mode == "replace": _clear_target_selection(selection, beat_id)
        count = sum(len(row.get("candidates") or []) for row in merged_video if str(row.get("parent_beat_id")) == beat_id)
        _event(
            "research", 100, "Beat media research completed",
            beat_id=beat_id, mode=mode, providers=list(provider_scope), video_candidates=count,
        )
    except Exception:
        _restore(snapshot)
        raise
    return {"beat_id": beat_id, "mode": mode, "providers": list(provider_scope), "resolve_calls": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description="Research media for one already-analyzed RAMBLA visual beat")
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--beat-id", required=True)
    parser.add_argument("--research-mode", choices=("replace", "append"), required=True)
    parser.add_argument("--providers", nargs="+")
    parser.add_argument("--client-id", default="debug-reel")
    args = parser.parse_args()
    run_research(
        video=args.video.resolve(),
        output=args.output_dir.resolve(),
        beat_id=args.beat_id,
        mode=args.research_mode,
        client_id=args.client_id,
        providers=tuple(args.providers or ()),
    )


if __name__ == "__main__": main()
