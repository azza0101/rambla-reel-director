"""CLI entry point for APP REEL V5 API-first text-only editorial planning."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
from typing import Any

from .api_first_director import DirectorProvider, generate_director_plan
from .atomic_io import write_json
from .editorial_import import import_plan, normalized_chunks, transcript_package
from .gemini_interactions import DEFAULT_GEMINI_MODEL, GeminiInteractionsClient
from .project_config import load_project_credentials


def _infer_project_id(run_dir: Path) -> str:
    candidate = run_dir.parent.name
    if re.fullmatch(r"[a-f0-9]{12}", candidate):
        return candidate
    raise ValueError("--project-id is required when run directory is not inside a saved project")


def _duration_from_chunks(run_dir: Path) -> float:
    rows = normalized_chunks(run_dir)
    return max((float(row["end"]) for row in rows), default=0.0)


def run_api_first_director(
    *,
    run_dir: Path,
    project_id: str | None = None,
    duration: float | None = None,
    provider: DirectorProvider | None = None,
    max_attempts: int = 2,
) -> dict[str, Any]:
    run_dir = Path(run_dir).resolve()
    if not run_dir.is_dir():
        raise FileNotFoundError(run_dir)
    project_id = project_id or _infer_project_id(run_dir)
    duration = float(duration) if duration is not None else _duration_from_chunks(run_dir)
    package = transcript_package(run_dir, project_id, duration)

    if provider is None:
        load_project_credentials()
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY missing. Add it to .env.local or the process environment."
            )
        model = os.environ.get("RAMBLA_DIRECTOR_MODEL", DEFAULT_GEMINI_MODEL).strip()
        provider = GeminiInteractionsClient(api_key, model=model)

    result = generate_director_plan(package, provider, max_attempts=max_attempts)
    editorial_root = import_plan(run_dir, result.plan, package)

    audit_dir = run_dir / "api-first"
    audit_dir.mkdir(parents=True, exist_ok=True)
    write_json(audit_dir / "director-decisions.json", result.decisions)
    write_json(
        audit_dir / "director-run.json",
        {
            "schema_version": "rambla-api-first-director-run-1",
            "provider": result.provider,
            "model": result.model,
            "attempts": result.attempts,
            "interaction_id": result.interaction_id,
            "validation_errors": list(result.validation_errors),
            "transcript_signature": package["transcript_signature"],
            "visual_plan_path": str((run_dir / "visual-plan.json").resolve()),
            "editorial_root": str(editorial_root.resolve()),
            "source_video_sent_to_ai": False,
            "word_timestamps_sent_to_director": False,
        },
    )
    return {
        "provider": result.provider,
        "model": result.model,
        "attempts": result.attempts,
        "beats": len(result.plan["visual_beats"]),
        "visual_plan": str((run_dir / "visual-plan.json").resolve()),
        "editorial_root": str(editorial_root.resolve()),
        "source_video_sent_to_ai": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate canonical APP REEL visual-plan.json from transcript only via cloud AI"
    )
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--project-id")
    parser.add_argument("--duration", type=float)
    parser.add_argument("--max-attempts", type=int, default=2)
    args = parser.parse_args()
    summary = run_api_first_director(
        run_dir=args.run_dir,
        project_id=args.project_id,
        duration=args.duration,
        max_attempts=args.max_attempts,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
