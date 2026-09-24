"""Global TikTok + Instagram sourcing for already-planned B-roll beats.

This worker searches only authenticated/public social providers and merges new
results into existing video retrieval artifacts. It never reruns ASR, image
search, YouTube, Pexels or Resolve.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from .atomic_io import write_json
from .beat_research import merge_video_rows
from .debug_run_cli import (
    DEFAULT_EMBEDDING_CODE,
    DEFAULT_MODEL_ROOT,
    DEFAULT_PIPELINE_PYTHON,
    _event,
    _probe,
    persist_video_diagnostics,
)
from .editorial_import import retrieval_bundle


SOCIAL_PROVIDERS = ("tiktok", "instagram")


def _pipeline_python() -> str:
    return str(DEFAULT_PIPELINE_PYTHON if DEFAULT_PIPELINE_PYTHON.is_file() else Path(sys.executable))


def social_sourcing_command(
    output: Path,
    transcript_path: Path,
    outline_path: Path,
    client_id: str,
    source_frames: int,
    *,
    beat_ids: tuple[str, ...],
    providers: tuple[str, ...] = SOCIAL_PROVIDERS,
) -> list[str]:
    command = [
        _pipeline_python(), "-m", "backend.app.online_sourcing_cli",
        "--transcript", str(transcript_path),
        "--outline", str(outline_path),
        "--chunks", str(output / "semantic-chunks.json"),
        "--output-dir", str(output),
        "--client-id", client_id,
        "--source-frames", str(source_frames),
        "--model-root", str(DEFAULT_MODEL_ROOT),
        "--embedding-code-root", str(DEFAULT_EMBEDDING_CODE),
        "--max-candidates", "24",
        "--beat-ids", *beat_ids,
        "--providers", *providers,
    ]
    return command


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return default


def _snapshot(paths: list[Path]) -> dict[Path, bytes | None]:
    return {path: path.read_bytes() if path.is_file() else None for path in paths}


def _restore(snapshot: dict[Path, bytes | None]) -> None:
    for path, data in snapshot.items():
        if data is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".restore.tmp")
            temporary.write_bytes(data)
            temporary.replace(path)


def require_completed_social_search(rows: list[dict]) -> None:
    attempts = [a for row in rows for a in row.get("search_attempts", [])
                if a.get("provider") in SOCIAL_PROVIDERS]
    interrupted=[a for a in attempts if any(reason in str(a.get('browser_error',''))+' '+str(a.get('browser_error_detail','')) for reason in ('challenge_required','login_required'))]
    if interrupted:
        raise RuntimeError('Social search incomplete: '+str(interrupted[0].get('browser_error_detail') or interrupted[0].get('browser_error')))
    if not attempts or all(a.get("error") or a.get('browser_error') for a in attempts):
        reasons = list(dict.fromkeys(str(a.get("browser_error_detail") or a.get("error")) for a in attempts))
        raise RuntimeError("Social search blocked; no completed provider request. " + " | ".join(reasons[:3]))


def run_social_research(*, video: Path, output: Path, client_id: str, providers: tuple[str, ...] = SOCIAL_PROVIDERS) -> dict:
    providers = tuple(dict.fromkeys(providers))
    if not providers or any(p not in SOCIAL_PROVIDERS for p in providers):
        raise ValueError("Select TikTok and/or Instagram")
    if not video.is_file():
        raise FileNotFoundError(video)
    transcript = output / "transcript-raw.json"
    outline = output / "semantic-beats.json"
    chunks_path = output / "semantic-chunks.json"
    for required in (transcript, outline, chunks_path):
        if not required.is_file():
            raise RuntimeError("analysis required before social sourcing")

    retrieval_root, _chunks, visual_plan, _ = retrieval_bundle(output)
    beat_ids = tuple(
        str(row.get("id"))
        for row in visual_plan["chunks"].values()
        if isinstance(row, dict) and row.get("action") == "BROLL" and str(row.get("id") or "").strip()
    )
    if not beat_ids:
        _event("online_search", 100, "No B-roll beats require social search", providers=list(providers))
        return {"beats": 0, "providers": list(providers), "resolve_calls": 0}

    video_artifact = retrieval_root / "online-candidates.json"
    tracked = [
        video_artifact,
        retrieval_root / "video-sourcing-diagnostics.json",
        retrieval_root / "video-retrieval-plan.json",
    ]
    snapshot = _snapshot(tracked)
    existing_video = _read_json(video_artifact, [])
    _, source_frames = _probe(video)

    _event(
        "online_search",
        1,
        "Social-only search started",
        beats=len(beat_ids),
        providers=list(providers),
    )
    try:
        subprocess.run(
            social_sourcing_command(
                output,
                transcript,
                outline,
                client_id,
                source_frames,
                beat_ids=beat_ids,
                providers=providers,
            ),
            check=True,
        )
        fresh_video = _read_json(video_artifact, [])
        merged = existing_video
        for beat_id in beat_ids:
            merged = merge_video_rows(merged, fresh_video, beat_id, "append")
        write_json(video_artifact, merged)
        persist_video_diagnostics(retrieval_root)
        count = sum(
            sum(c.get("provider", c.get("source")) in SOCIAL_PROVIDERS for c in row.get("candidates") or [])
            for row in merged
            if str(row.get("parent_beat_id") or "") in set(beat_ids)
        )
        attempts = [a for row in fresh_video for a in row.get("search_attempts", []) if a.get("provider") in SOCIAL_PROVIDERS]
        failed = sum(bool(a.get("error")) for a in attempts)
        _event(
            "online_search",
            100,
            "Social search finished with provider errors" if failed else "Social-only search completed",
            search_attempts=len(attempts),
            failed_attempts=failed,
            beats=len(beat_ids),
            providers=list(providers),
            video_candidates=count,
        )
    except Exception:
        _restore(snapshot)
        raise
    require_completed_social_search(fresh_video)
    return {
        "beats": len(beat_ids),
        "providers": list(providers),
        "resolve_calls": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Search TikTok and Instagram only for all B-roll beats")
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--client-id", default="debug-reel")
    parser.add_argument("--providers", nargs="+", choices=SOCIAL_PROVIDERS, default=SOCIAL_PROVIDERS)
    args = parser.parse_args()
    run_social_research(
        video=args.video.resolve(),
        output=args.output_dir.resolve(),
        client_id=args.client_id,
        providers=tuple(args.providers),
    )


if __name__ == "__main__":
    main()
