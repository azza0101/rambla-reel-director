"""CLI entry point for APP REEL V5 API-first text-only editorial planning."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

from .api_first_director import DirectorProvider, build_director_prompt, director_schema, generate_director_plan
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


def _request_signature(package: dict[str, Any], provider_name: str, model: str) -> str:
    payload = {
        "provider": provider_name,
        "model": model,
        "prompt": build_director_prompt(package),
        "schema": director_schema(),
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def run_api_first_director(
    *,
    run_dir: Path,
    project_id: str | None = None,
    duration: float | None = None,
    provider: DirectorProvider | None = None,
    max_attempts: int = 2,
    activate: bool = False,
    reuse: bool = True,
) -> dict[str, Any]:
    run_dir = Path(run_dir).resolve()
    if not run_dir.is_dir():
        raise FileNotFoundError(run_dir)
    project_id = project_id or _infer_project_id(run_dir)
    duration = float(duration) if duration is not None else _duration_from_chunks(run_dir)
    package = transcript_package(run_dir, project_id, duration)

    load_project_credentials()
    provider_name = str(getattr(provider, "provider_name", "gemini"))
    model = str(
        getattr(provider, "model", "")
        or os.environ.get("RAMBLA_DIRECTOR_MODEL", DEFAULT_GEMINI_MODEL)
    ).strip()
    signature = _request_signature(package, provider_name, model)

    audit_dir = run_dir / "api-first"
    audit_dir.mkdir(parents=True, exist_ok=True)
    candidate_plan_path = audit_dir / "visual-plan.json"
    decisions_path = audit_dir / "director-decisions.json"
    run_path = audit_dir / "director-run.json"

    cached_audit = _read_json(run_path) if reuse else None
    cached_plan = _read_json(candidate_plan_path) if reuse else None
    cache_hit = bool(
        cached_audit
        and cached_plan
        and cached_audit.get("request_signature") == signature
        and cached_audit.get("transcript_signature") == package["transcript_signature"]
    )

    if cache_hit:
        from .editorial_import import validate_import
        try:
            plan = validate_import(cached_plan, package)
        except (ValueError, KeyError, TypeError):
            cache_hit = False

    if cache_hit:
        result_provider = provider_name
        result_model = model
        attempts = 0
        interaction_id = cached_audit.get("interaction_id")
        validation_errors = []
        cache_status = "reused"
    else:
        if provider is None:
            api_key = os.environ.get("GEMINI_API_KEY", "").strip()
            if not api_key:
                raise RuntimeError(
                    "GEMINI_API_KEY missing. Add it to .env.local or the process environment."
                )
            provider = GeminiInteractionsClient(api_key, model=model)
        result = generate_director_plan(package, provider, max_attempts=max_attempts)
        plan = result.plan
        result_provider = result.provider
        result_model = result.model
        attempts = result.attempts
        interaction_id = result.interaction_id
        validation_errors = list(result.validation_errors)
        cache_status = "generated"
        write_json(decisions_path, result.decisions)
        write_json(candidate_plan_path, plan)

    editorial_root = None
    if activate:
        editorial_root = import_plan(run_dir, plan, package)

    write_json(
        run_path,
        {
            "schema_version": "rambla-api-first-director-run-1",
            "provider": result_provider,
            "model": result_model,
            "attempts": attempts,
            "interaction_id": interaction_id,
            "validation_errors": validation_errors,
            "transcript_signature": package["transcript_signature"],
            "request_signature": signature,
            "cache_status": cache_status,
            "candidate_visual_plan_path": str(candidate_plan_path.resolve()),
            "activated": bool(activate),
            "active_visual_plan_path": str((run_dir / "visual-plan.json").resolve()) if activate else None,
            "editorial_root": str(editorial_root.resolve()) if editorial_root else None,
            "source_video_sent_to_ai": False,
            "word_timestamps_sent_to_director": False,
        },
    )
    return {
        "provider": result_provider,
        "model": result_model,
        "attempts": attempts,
        "cache_status": cache_status,
        "beats": len(plan["visual_beats"]),
        "visual_plan": str(candidate_plan_path.resolve()),
        "activated": bool(activate),
        "active_visual_plan": str((run_dir / "visual-plan.json").resolve()) if activate else None,
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
    parser.add_argument("--activate", action="store_true", help="replace the active run/visual-plan.json after validation")
    parser.add_argument("--review", action="store_true", help="write a V4 vs V5 side-by-side A/B review")
    parser.add_argument("--no-reuse", action="store_true", help="ignore a matching API-first cache")
    args = parser.parse_args()
    summary = run_api_first_director(
        run_dir=args.run_dir,
        project_id=args.project_id,
        duration=args.duration,
        max_attempts=args.max_attempts,
        activate=args.activate,
        reuse=not args.no_reuse,
    )
    if args.review:
        from .api_first_review import build_review
        try:
            review = build_review(args.run_dir)
        except ValueError as exc:
            summary["review_error"] = str(exc)
        else:
            summary["review_html"] = review["review_html"]
            summary["review_json"] = review["review_json"]
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
