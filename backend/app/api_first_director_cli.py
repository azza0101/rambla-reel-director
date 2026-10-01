"""CLI entry point for APP REEL V5 API-first text-only editorial planning."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any

from .api_first_director import DIRECTOR_SCHEMA_VERSION, DirectorProvider, build_director_prompt, director_schema, generate_director_plan
from .atomic_io import write_json
from .editorial_import import import_plan, normalized_chunks, transcript_package
from .director_provider import FailoverDirectorProvider
from .gemini_interactions import DEFAULT_GEMINI_MODEL, GeminiInteractionsClient
from .groq_api import DEFAULT_GROQ_MODEL, GroqDirectorClient
from .project_config import load_project_credentials


def _infer_project_id(run_dir: Path) -> str:
    candidate = run_dir.parent.name
    if re.fullmatch(r"[a-f0-9]{12}", candidate):
        return candidate
    raise ValueError("--project-id is required when run directory is not inside a saved project")


def _duration_from_chunks(run_dir: Path) -> float:
    rows = normalized_chunks(run_dir)
    return max((float(row["end"]) for row in rows), default=0.0)


def _request_signature(
    package: dict[str, Any],
    provider_name: str,
    model: str,
    thinking_level: str,
) -> str:
    payload = {
        "planner_contract": DIRECTOR_SCHEMA_VERSION,
        "provider": provider_name,
        "model": model,
        "thinking_level": thinking_level,
        "prompt": build_director_prompt(package),
        "schema": director_schema(len(package.get("chunks") or [])),
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _configure_utf8_stdio() -> None:
    """Keep Windows subprocess logging UTF-8 safe when stdout/stderr are piped."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def _gemini_progress(event: str, data: dict[str, Any]) -> None:
    stamp = time.strftime("%H:%M:%S")
    provider = str(data.get("provider") or "ai").casefold()
    label = {"gemini": "Gemini", "groq": "Groq", "auto": "AUTO"}.get(provider, provider.upper())
    progress = 12.0
    if event == "waiting":
        progress = min(82.0, 12.0 + 70.0 * float(data.get("elapsed_seconds") or 0) / max(1.0, float(data.get("timeout_seconds") or 1)))
    elif event in {"retry", "transport_error", "quota_exhausted", "model_skipped", "model_exhausted"}:
        progress = 18.0
    print("RAMBLA_EVENT " + json.dumps({"stage":"visual_planning", "progress":progress,
        "message": f"{label} · " + ("in attesa della risposta" if event=="waiting" else "richiesta piano in corso"),
        "data": {"provider":provider, "event":event, **data}}, ensure_ascii=False), flush=True)
    if event == "request_start":
        print(
            f"[{stamp}] {label} · {data.get('model')} · attempt "
            f"{data.get('attempt')}/{data.get('attempts_for_model')} · sending "
            f"(read timeout {float(data.get('timeout_seconds') or 0):.0f}s)...",
            flush=True,
        )
    elif event == "waiting":
        print(
            f"[{stamp}] {label} · {data.get('model')} · still waiting · "
            f"{float(data.get('elapsed_seconds') or 0):.0f}s elapsed",
            flush=True,
        )
    elif event == "transport_error":
        detail = str(data.get("detail") or "").strip()
        suffix = f" · {detail}" if detail else ""
        print(
            f"[{stamp}] {label} · {data.get('error_type')} on {data.get('model')}{suffix}",
            flush=True,
        )
    elif event == "retry":
        detail = str(data.get("detail") or "").strip()
        suffix = f" · {detail}" if detail else ""
        print(
            f"[{stamp}] {label} · HTTP {data.get('status')} · retry in "
            f"{float(data.get('delay_seconds') or 0):.1f}s{suffix}",
            flush=True,
        )
    elif event == "quota_exhausted":
        detail = str(data.get("detail") or "").strip()
        suffix = f" · {detail}" if detail else ""
        cooldown = float(data.get("cooldown_seconds") or 0)
        cooldown_text = f" · cooldown {cooldown:.0f}s" if cooldown else ""
        print(
            f"[{stamp}] {label} · quota/rate limit on {data.get('model')} · switching model"
            f"{cooldown_text}{suffix}",
            flush=True,
        )
    elif event == "model_skipped":
        wait = float(data.get("retry_in_seconds") or 0)
        print(
            f"[{stamp}] {label} · skip {data.get('model')} · quota cooldown · retry in {wait:.0f}s",
            flush=True,
        )
    elif event == "model_exhausted":
        print(
            f"[{stamp}] {label} · {data.get('model')} still unavailable after retries.",
            flush=True,
        )
    elif event == "provider_fallback":
        print(
            f"[{stamp}] AUTO · provider fallback {data.get('from_provider')} → {data.get('to_provider')}",
            flush=True,
        )
    elif event == "fallback":
        print(
            f"[{stamp}] {label} · fallback {data.get('from_model')} → {data.get('to_model')}",
            flush=True,
        )
    elif event == "request_complete":
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        total = usage.get("total_tokens")
        token_text = f" · {total} tokens" if total is not None else ""
        print(
            f"[{stamp}] {label} · completed on {data.get('model')}{token_text}",
            flush=True,
        )


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
    provider_choice: str | None = None,
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
    choice = str(
        provider_choice
        or os.environ.get("RAMBLA_DIRECTOR_PROVIDER", "auto")
    ).casefold().strip()
    if provider is None and choice not in {"auto", "gemini", "groq"}:
        raise ValueError("RAMBLA_DIRECTOR_PROVIDER must be auto, gemini or groq")

    thinking_level = str(
        getattr(provider, "thinking_level", "")
        or os.environ.get("RAMBLA_DIRECTOR_THINKING", "high")
    ).casefold().strip()
    if thinking_level not in {"low", "medium", "high"}:
        raise ValueError("RAMBLA_DIRECTOR_THINKING must be low, medium or high")

    if provider is not None:
        provider_name = str(getattr(provider, "provider_name", "custom"))
        model = str(getattr(provider, "model", "") or "custom").strip()
    else:
        provider_name = choice
        gemini_model = os.environ.get("RAMBLA_DIRECTOR_MODEL", DEFAULT_GEMINI_MODEL).strip()
        groq_model = os.environ.get("RAMBLA_GROQ_DIRECTOR_MODEL", DEFAULT_GROQ_MODEL).strip()
        if choice == "gemini":
            model = gemini_model
        elif choice == "groq":
            model = groq_model
        else:
            configured_models = []
            if os.environ.get("GEMINI_API_KEY", "").strip():
                configured_models.append("gemini:" + gemini_model)
            if os.environ.get("GROQ_API_KEY", "").strip():
                configured_models.append("groq:" + groq_model)
            model = "|".join(configured_models) or "auto:no-provider"

    signature = _request_signature(package, provider_name, model, thinking_level)

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
        result_provider = str(cached_audit.get("provider") or provider_name)
        result_model = str(cached_audit.get("model") or model)
        requested_model = str(cached_audit.get("requested_model") or model)
        fallback_used = bool(cached_audit.get("fallback_used", result_model != requested_model))
        transport_attempts = 0
        attempts = 0
        interaction_id = cached_audit.get("interaction_id")
        validation_errors = []
        api_usage = list(cached_audit.get("api_usage") or [])
        api_calls_this_run = 0
        cache_status = "reused"
    else:
        if provider is None:
            gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
            groq_key = os.environ.get("GROQ_API_KEY", "").strip()
            gemini_model = os.environ.get("RAMBLA_DIRECTOR_MODEL", DEFAULT_GEMINI_MODEL).strip()
            groq_model = os.environ.get("RAMBLA_GROQ_DIRECTOR_MODEL", DEFAULT_GROQ_MODEL).strip()

            if choice == "gemini":
                if not gemini_key:
                    raise RuntimeError(
                        "GEMINI_API_KEY missing. Add it to .env.local or the process environment."
                    )
                provider = GeminiInteractionsClient(
                    gemini_key,
                    model=gemini_model,
                    thinking_level=thinking_level,
                    event_callback=_gemini_progress,
                    cooldown_state_path=audit_dir / "provider-health.json",
                )
            elif choice == "groq":
                if not groq_key:
                    raise RuntimeError(
                        "GROQ_API_KEY missing. Add it to .env.local or the process environment."
                    )
                provider = GroqDirectorClient(
                    groq_key,
                    model=groq_model,
                    thinking_level=thinking_level,
                    event_callback=_gemini_progress,
                )
            else:
                providers = []
                if gemini_key:
                    providers.append(
                        GeminiInteractionsClient(
                            gemini_key,
                            model=gemini_model,
                            thinking_level=thinking_level,
                            event_callback=_gemini_progress,
                            cooldown_state_path=audit_dir / "provider-health.json",
                        )
                    )
                if groq_key:
                    providers.append(
                        GroqDirectorClient(
                            groq_key,
                            model=groq_model,
                            thinking_level=thinking_level,
                            event_callback=_gemini_progress,
                        )
                    )
                if not providers:
                    raise RuntimeError(
                        "No cloud Director API configured. Add GEMINI_API_KEY and/or GROQ_API_KEY to .env.local."
                    )
                provider = (
                    providers[0]
                    if len(providers) == 1
                    else FailoverDirectorProvider(providers, event_callback=_gemini_progress)
                )
        result = generate_director_plan(package, provider, max_attempts=max_attempts)
        plan = result.plan
        result_provider = result.provider
        result_model = result.model
        requested_model = result.requested_model
        fallback_used = result.fallback_used
        transport_attempts = result.transport_attempts
        attempts = result.attempts
        interaction_id = result.interaction_id
        validation_errors = list(result.validation_errors)
        api_usage = [dict(row) for row in result.usage]
        api_calls_this_run = result.transport_attempts
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
            "provider_choice": provider_name,
            "model": result_model,
            "requested_model": requested_model,
            "fallback_used": fallback_used,
            "transport_attempts": transport_attempts,
            "thinking_level": thinking_level,
            "attempts": attempts,
            "interaction_id": interaction_id,
            "validation_errors": validation_errors,
            "api_calls_this_run": api_calls_this_run,
            "api_usage": api_usage,
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
        "provider_choice": provider_name,
        "model": result_model,
        "requested_model": requested_model,
        "fallback_used": fallback_used,
        "transport_attempts": transport_attempts,
        "thinking_level": thinking_level,
        "attempts": attempts,
        "api_calls_this_run": api_calls_this_run,
        "api_usage": api_usage,
        "cache_status": cache_status,
        "beats": len(plan["visual_beats"]),
        "visual_plan": str(candidate_plan_path.resolve()),
        "activated": bool(activate),
        "active_visual_plan": str((run_dir / "visual-plan.json").resolve()) if activate else None,
        "source_video_sent_to_ai": False,
    }

def main() -> None:
    _configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Generate canonical APP REEL visual-plan.json from transcript only via cloud AI"
    )
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--project-id")
    parser.add_argument("--duration", type=float)
    parser.add_argument("--provider", choices=("auto", "gemini", "groq"), default="auto")
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--activate", action="store_true", help="replace the active run/visual-plan.json after validation")
    parser.add_argument("--review", action="store_true", help="write a V4 vs V5 side-by-side A/B review")
    parser.add_argument("--no-reuse", action="store_true", help="ignore a matching API-first cache")
    args = parser.parse_args()
    summary = run_api_first_director(
        run_dir=args.run_dir,
        project_id=args.project_id,
        duration=args.duration,
        provider_choice=args.provider,
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
