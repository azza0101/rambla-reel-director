"""File-based Resolve vs RAMBLA ASR benchmark runner.

This command consumes exported artifacts only. It never imports or connects to
Resolve, which keeps the benchmark safe to run while Resolve mutation is frozen.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .asr_benchmark import (
    TranscriptArtifact,
    compare_transcripts,
    normalize_transcript_artifact,
    parse_srt,
)


def _artifact_format(path: Path) -> str:
    suffix = path.suffix.casefold()
    if suffix == ".srt":
        return "srt"
    if suffix == ".json":
        return "json"
    raise ValueError(f"unsupported transcript format: {path.suffix or '<none>'}")


def _load_artifact(
    path: Path,
    *,
    provider: str,
    source_duration_seconds: float | None,
    elapsed_seconds: float | None,
) -> TranscriptArtifact:
    fmt = _artifact_format(path)
    if fmt == "srt":
        artifact = parse_srt(
            path.read_text(encoding="utf-8"),
            provider=provider,
            elapsed_seconds=elapsed_seconds,
        )
        if source_duration_seconds is None or source_duration_seconds <= artifact.source_duration_seconds:
            return artifact
        return TranscriptArtifact(
            provider=artifact.provider,
            language=artifact.language,
            source_duration_seconds=float(source_duration_seconds),
            segments=artifact.segments,
            elapsed_seconds=artifact.elapsed_seconds,
        )

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON transcript must be an object")
    return normalize_transcript_artifact(
        payload,
        provider=provider,
        source_duration_seconds=source_duration_seconds,
        elapsed_seconds=elapsed_seconds,
    )


def run_from_files(
    *,
    local_path: Path,
    resolve_path: Path,
    output_path: Path,
    reference_path: Path | None = None,
    source_duration_seconds: float | None = None,
    local_elapsed_seconds: float | None = None,
    resolve_elapsed_seconds: float | None = None,
) -> dict[str, Any]:
    local_path = Path(local_path)
    resolve_path = Path(resolve_path)
    output_path = Path(output_path)
    reference_path = Path(reference_path) if reference_path is not None else None

    local = _load_artifact(
        local_path,
        provider="rambla-local",
        source_duration_seconds=source_duration_seconds,
        elapsed_seconds=local_elapsed_seconds,
    )
    resolve = _load_artifact(
        resolve_path,
        provider="resolve",
        source_duration_seconds=source_duration_seconds,
        elapsed_seconds=resolve_elapsed_seconds,
    )
    reference = (
        _load_artifact(
            reference_path,
            provider="human-reference",
            source_duration_seconds=source_duration_seconds,
            elapsed_seconds=None,
        )
        if reference_path is not None
        else None
    )

    report = compare_transcripts(reference=reference, candidates=[local, resolve])
    report["inputs"] = {
        "local_format": _artifact_format(local_path),
        "resolve_format": _artifact_format(resolve_path),
        "reference_format": _artifact_format(reference_path) if reference_path is not None else None,
        "source_duration_seconds": source_duration_seconds,
    }
    report["resolve_calls"] = 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare a RAMBLA/local transcript JSON with an exported Resolve SRT without connecting to Resolve"
    )
    parser.add_argument("--local", type=Path, required=True, help="RAMBLA/local transcript JSON")
    parser.add_argument("--resolve", type=Path, required=True, help="Resolve transcript export (.srt or .json)")
    parser.add_argument("--output", type=Path, required=True, help="Output benchmark JSON")
    parser.add_argument("--reference", type=Path, help="Optional human reference transcript (.srt or .json)")
    parser.add_argument("--source-duration-seconds", type=float)
    parser.add_argument("--local-elapsed-seconds", type=float)
    parser.add_argument("--resolve-elapsed-seconds", type=float)
    args = parser.parse_args()

    if args.source_duration_seconds is not None and args.source_duration_seconds <= 0:
        raise SystemExit("--source-duration-seconds must be positive")
    for name, value in (
        ("--local-elapsed-seconds", args.local_elapsed_seconds),
        ("--resolve-elapsed-seconds", args.resolve_elapsed_seconds),
    ):
        if value is not None and value < 0:
            raise SystemExit(f"{name} cannot be negative")

    report = run_from_files(
        local_path=args.local,
        resolve_path=args.resolve,
        output_path=args.output,
        reference_path=args.reference,
        source_duration_seconds=args.source_duration_seconds,
        local_elapsed_seconds=args.local_elapsed_seconds,
        resolve_elapsed_seconds=args.resolve_elapsed_seconds,
    )
    print(
        json.dumps(
            {
                "mode": report["mode"],
                "winner": report["winner"],
                "resolve_calls": report["resolve_calls"],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
