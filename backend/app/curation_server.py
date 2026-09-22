"""Product server extension for RAMBLA project/media lifecycle controls.

The proven debug_server remains the core project/curation runtime. This module
adds project-library, clean-media, social login and beat-scoped research routes
without coupling those operations to Analyze/ASR.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import os
from pathlib import Path
import shlex
import sys
import uuid
from typing import Any, Awaitable, Callable

from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict

from . import debug_server as debug
from .browser_profiles import BrowserProfileManager, SUPPORTED_SOCIAL_PROVIDERS
from .curation_project import ProjectStore
from .curation_ui_v2 import render_curation_page_v2
from .editorial_import import active_retrieval_root
from .project_maintenance import clean_project_media, delete_project_tree, project_library_rows, rename_project
from .debug_research_cli import research_stage_type


class RenameProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str


class SocialSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    providers: tuple[str, ...] = ("tiktok", "instagram")


class BeatResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: str
    providers: tuple[str, ...] = ()


class DirectorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = "auto"


ResearchRunner = Callable[[debug.RunState, str, str], Awaitable[Any] | Any]


def _default_project_root() -> Path:
    return Path(os.environ.get("RAMBLA_PROJECT_ROOT", str(Path(debug.DEFAULT_OUTPUT).parent / "curation-projects")))


def _default_browser_profile_root(project_root: Path) -> Path:
    value = os.environ.get("RAMBLA_BROWSER_PROFILE_ROOT", "").strip()
    if value:
        return Path(value)
    return project_root.parent / "browser-profiles"


def _project_payload(project) -> dict[str, Any]:
    return debug._project_payload(project)


def _active_run_for(run_root: Path) -> debug.RunState | None:
    target = run_root.resolve()
    for state in debug.RUNS.values():
        if state.status not in {"QUEUED", "RUNNING"}:
            continue
        try:
            if Path(state.output_dir).resolve() == target:
                return state
        except OSError:
            continue
    return None


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return default


def _validate_broll_beat(run_root: Path, beat_id: str) -> dict[str, Any]:
    plan = _read_json(run_root / "visual-plan.json", {})
    beats = plan.get("visual_beats", []) if isinstance(plan, dict) else []
    beat = next((row for row in beats if isinstance(row, dict) and str(row.get("id")) == beat_id), None)
    if beat is None:
        raise HTTPException(status_code=404, detail="visual beat non trovato")
    if beat.get("action") != "BROLL":
        raise HTTPException(status_code=422, detail="media research disponibile solo per beat BROLL")
    for required in ("transcript-raw.json", "semantic-chunks.json", "semantic-beats.json"):
        if not (run_root / required).is_file():
            raise HTTPException(status_code=422, detail="analysis required before beat research")
    return beat


async def _default_research_runner(
    state: debug.RunState,
    beat_id: str,
    mode: str,
    providers: tuple[str, ...] = (),
) -> None:
    command = [
        sys.executable, "-m", "backend.app.debug_research_cli",
        "--video", str(state.video_path), "--output-dir", str(state.output_dir),
        "--beat-id", beat_id, "--research-mode", mode,
        "--client-id", f"project-{state.output_dir.parent.name}",
    ]
    if providers:
        command += ["--providers", *providers]
    cwd = Path.cwd()
    preflight = debug._preflight_worker(state, command, cwd)
    await debug._emit(state, debug.DebugEvent("preflight", "Research worker preflight completato", 100.0, preflight))
    await debug._emit(state, debug.DebugEvent("log", "Comando: " + " ".join(shlex.quote(x) for x in command)))
    process = await debug._spawn_worker(command, cwd)
    state.process = process
    await debug._emit(state, debug.DebugEvent("worker", "Research worker avviato", data={"spawn_mode": process.spawn_mode}))
    while True:
        line = await process.readline()
        if not line:
            break
        decoded = line.decode("utf-8", errors="replace")
        if not debug.suppress_worker_log_line(decoded):
            await debug._emit(state, debug.parse_worker_line(decoded))
    state.return_code = await process.wait()
    if state.return_code != 0:
        raise RuntimeError(f"beat research worker exited with code {state.return_code}")


async def _run_research_state(
    state: debug.RunState,
    beat_id: str,
    mode: str,
    providers: tuple[str, ...],
    runner: ResearchRunner | None,
) -> None:
    state.status = "RUNNING"
    try:
        await debug._emit(
            state,
            debug.DebugEvent(
                "research",
                "Beat research avviata",
                1.0,
                {"beat_id": beat_id, "mode": mode, "providers": list(providers)},
            ),
        )
        if runner is None:
            result = _default_research_runner(state, beat_id, mode, providers)
        else:
            result = runner(state, beat_id, mode)
        if inspect.isawaitable(result):
            await result
        if state.status != "CANCELLED":
            state.status = "SUCCEEDED"
            state.return_code = 0
            await debug._emit(
                state,
                debug.DebugEvent(
                    "research",
                    "Beat research completata",
                    100.0,
                    {"beat_id": beat_id, "mode": mode, "providers": list(providers)},
                ),
            )
    except Exception as exc:
        if state.status != "CANCELLED":
            state.status = "FAILED"
            state.return_code = state.return_code if state.return_code is not None else 1
            await debug._emit(
                state,
                debug.DebugEvent(
                    "error",
                    str(exc),
                    data={"beat_id": beat_id, "mode": mode, "providers": list(providers)},
                ),
            )
    finally:
        if state.process is not None and state.process.returncode is None:
            await debug._stop_worker(state.process)
        state.process = None



async def _default_director_runner(state: debug.RunState, provider: str) -> None:
    command = [
        sys.executable,
        "-m",
        "backend.app.api_first_director_cli",
        "--run-dir",
        str(state.output_dir),
        "--activate",
        "--provider",
        provider,
    ]
    cwd = Path.cwd()
    preflight = debug._preflight_worker(state, command, cwd)
    preflight["source_video_sent_to_ai"] = False
    await debug._emit(
        state,
        debug.DebugEvent(
            "preflight",
            "API Director preflight completato",
            100.0,
            preflight,
        ),
    )
    await debug._emit(
        state,
        debug.DebugEvent(
            "log",
            "API Director command: " + " ".join(shlex.quote(x) for x in command),
        ),
    )
    process = await debug._spawn_worker(command, cwd)
    state.process = process
    await debug._emit(
        state,
        debug.DebugEvent(
            "worker",
            "API Director worker avviato",
            data={"spawn_mode": process.spawn_mode, "source_video_sent_to_ai": False},
        ),
    )
    while True:
        line = await process.readline()
        if not line:
            break
        decoded = line.decode("utf-8", errors="replace")
        if not debug.suppress_worker_log_line(decoded):
            await debug._emit(state, debug.parse_worker_line(decoded))
    state.return_code = await process.wait()
    if state.return_code != 0:
        raise RuntimeError(f"API Director worker exited with code {state.return_code}")


async def _run_director_state(state: debug.RunState, provider: str) -> None:
    state.status = "RUNNING"
    try:
        await debug._emit(
            state,
            debug.DebugEvent(
                "visual_planning",
                "API Director avviato",
                1.0,
                {"provider": provider, "source_video_sent_to_ai": False},
            ),
        )
        await _default_director_runner(state, provider)
        if state.status != "CANCELLED":
            state.status = "SUCCEEDED"
            state.return_code = 0
            audit = _read_json(Path(state.output_dir) / "api-first" / "director-run.json", {})
            await debug._emit(
                state,
                debug.DebugEvent(
                    "visual_planning",
                    "API Director completato",
                    100.0,
                    {
                        "provider": audit.get("provider", provider),
                        "model": audit.get("model"),
                        "requested_model": audit.get("requested_model"),
                        "fallback_used": audit.get("fallback_used", False),
                        "api_calls_this_run": audit.get("api_calls_this_run"),
                        "source_video_sent_to_ai": False,
                    },
                ),
            )
    except Exception as exc:
        if state.status != "CANCELLED":
            state.status = "FAILED"
            state.return_code = state.return_code if state.return_code is not None else 1
            await debug._emit(
                state,
                debug.DebugEvent(
                    "error",
                    str(exc),
                    data={"provider": provider, "source_video_sent_to_ai": False},
                ),
            )
    finally:
        if state.process is not None and state.process.returncode is None:
            await debug._stop_worker(state.process)
        state.process = None


async def _default_social_runner(state: debug.RunState, providers: tuple[str, ...] = ("tiktok", "instagram")) -> None:
    command = [
        sys.executable, "-m", "backend.app.debug_social_cli",
        "--providers", *providers,
        "--video", str(state.video_path),
        "--output-dir", str(state.output_dir),
        "--client-id", f"project-{state.output_dir.parent.name}",
    ]
    cwd = Path.cwd()
    preflight = debug._preflight_worker(state, command, cwd)
    await debug._emit(state, debug.DebugEvent(
        "preflight", "Social worker preflight completato", 100.0, preflight,
    ))
    await debug._emit(
        state,
        debug.DebugEvent("log", "Comando: " + " ".join(shlex.quote(x) for x in command)),
    )
    process = await debug._spawn_worker(command, cwd)
    state.process = process
    await debug._emit(
        state,
        debug.DebugEvent("worker", "Social worker avviato", data={"spawn_mode": process.spawn_mode}),
    )
    while True:
        line = await process.readline()
        if not line:
            break
        decoded = line.decode("utf-8", errors="replace")
        if not debug.suppress_worker_log_line(decoded):
            await debug._emit(state, debug.parse_worker_line(decoded))
    state.return_code = await process.wait()
    if state.return_code != 0:
        raise RuntimeError(f"social sourcing worker exited with code {state.return_code}")


async def _run_social_state(state: debug.RunState, providers: tuple[str, ...] = ("tiktok", "instagram")) -> None:
    state.status = "RUNNING"
    try:
        await debug._emit(
            state,
            debug.DebugEvent(
                "online_search",
                " + ".join(providers) + " search avviata",
                1.0,
                {"providers": list(providers)},
            ),
        )
        await _default_social_runner(state, providers)
        if state.status != "CANCELLED":
            state.status = "SUCCEEDED"
            state.return_code = 0
            await debug._emit(
                state,
                debug.DebugEvent(
                    "online_search",
                    " + ".join(providers) + " search completata",
                    100.0,
                    {"providers": list(providers)},
                ),
            )
    except Exception as exc:
        if state.status != "CANCELLED":
            state.status = "FAILED"
            state.return_code = state.return_code if state.return_code is not None else 1
            await debug._emit(
                state,
                debug.DebugEvent(
                    "error",
                    str(exc),
                    data={"providers": list(providers)},
                ),
            )
    finally:
        if state.process is not None and state.process.returncode is None:
            await debug._stop_worker(state.process)
        state.process = None

def create_app(
    *,
    project_root: Path | None = None,
    curation_run_root: Path | None = None,
    allowed_media_roots: list[Path] | None = None,
    probe_runner: Any = None,
    audio_probe_runner: Any = None,
    audio_command_runner: Any = None,
    research_runner: ResearchRunner | None = None,
    browser_profile_manager: Any = None,
):
    root = Path(project_root or _default_project_root())
    app = debug.create_app(
        project_root=root,
        curation_run_root=curation_run_root,
        allowed_media_roots=allowed_media_roots,
        probe_runner=probe_runner,
        audio_probe_runner=audio_probe_runner,
        audio_command_runner=audio_command_runner,
    )

    # Replace the core page route with the augmented product UI while retaining
    # every existing core API/run endpoint.
    app.router.routes[:] = [route for route in app.router.routes if getattr(route, "path", None) != "/curation"]

    @app.get("/curation", response_class=HTMLResponse)
    async def product_curation_page() -> HTMLResponse:
        token = os.environ.get("RAMBLA_BUILD_TOKEN", "development")
        return HTMLResponse(render_curation_page_v2(token), headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache", "Expires": "0",
        })

    store = ProjectStore(root, probe_runner=probe_runner or debug._probe_source_video, audio_probe_runner=audio_probe_runner)
    social_profiles = browser_profile_manager or BrowserProfileManager(_default_browser_profile_root(root))

    def load_project(project_id: str):
        try:
            return store.load(project_id)
        except (FileNotFoundError, ValueError, json.JSONDecodeError):
            raise HTTPException(status_code=404, detail="project non trovato") from None

    def run_root(project_id: str) -> Path:
        load_project(project_id)
        return root / project_id / "run"

    @app.get("/api/curation/ai/status")
    async def ai_status() -> dict[str, Any]:
        from .gemini_interactions import DEFAULT_GEMINI_MODEL
        from .groq_api import DEFAULT_GROQ_MODEL
        thinking = os.environ.get("RAMBLA_DIRECTOR_THINKING", "high").strip()
        gemini_configured = bool(os.environ.get("GEMINI_API_KEY", "").strip())
        groq_configured = bool(os.environ.get("GROQ_API_KEY", "").strip())
        return {
            "providers": {
                "auto": {
                    "configured": gemini_configured or groq_configured,
                    "chain": [
                        *(
                            [
                                os.environ.get("RAMBLA_DIRECTOR_MODEL", DEFAULT_GEMINI_MODEL).strip(),
                                "gemini-3.7-flash",
                            ]
                            if gemini_configured else []
                        ),
                        *(
                            [
                                os.environ.get("RAMBLA_GROQ_DIRECTOR_MODEL", DEFAULT_GROQ_MODEL).strip(),
                                "openai/gpt-oss-120b",
                            ]
                            if groq_configured else []
                        ),
                    ],
                    "thinking_level": thinking,
                    "source_video_sent_to_ai": False,
                },
                "gemini": {
                    "configured": gemini_configured,
                    "model": os.environ.get("RAMBLA_DIRECTOR_MODEL", DEFAULT_GEMINI_MODEL).strip(),
                    "thinking_level": thinking,
                    "source_video_sent_to_ai": False,
                },
                "groq": {
                    "configured": groq_configured,
                    "model": os.environ.get("RAMBLA_GROQ_DIRECTOR_MODEL", DEFAULT_GROQ_MODEL).strip(),
                    "fallback_model": "openai/gpt-oss-120b",
                    "thinking_level": thinking,
                    "source_video_sent_to_ai": False,
                },
            },
            "resolve_calls": 0,
        }

    @app.post("/api/curation/projects/{project_id}/director")
    async def run_project_director(project_id: str, request: DirectorRequest) -> dict[str, Any]:
        project = load_project(project_id)
        run = run_root(project_id)
        provider = str(request.provider or "auto").casefold().strip()
        if provider not in {"auto", "gemini", "groq"}:
            raise HTTPException(status_code=422, detail="unsupported AI director provider")
        if provider == "gemini" and not os.environ.get("GEMINI_API_KEY", "").strip():
            raise HTTPException(status_code=422, detail="GEMINI_API_KEY is not configured")
        if provider == "groq" and not os.environ.get("GROQ_API_KEY", "").strip():
            raise HTTPException(status_code=422, detail="GROQ_API_KEY is not configured")
        if provider == "auto" and not (
            os.environ.get("GEMINI_API_KEY", "").strip()
            or os.environ.get("GROQ_API_KEY", "").strip()
        ):
            raise HTTPException(status_code=422, detail="No cloud Director API is configured")
        for required in ("transcript-raw.json", "semantic-chunks.json", "analysis-signature.json"):
            if not (run / required).is_file():
                raise HTTPException(status_code=422, detail="analyze transcript before running the API Director")
        if project.source_video is None:
            raise HTTPException(status_code=422, detail="source video required for the project timeline")
        if _active_run_for(run):
            raise HTTPException(status_code=409, detail="project stage already running")
        state = debug.RunState(
            uuid.uuid4().hex[:12],
            Path(project.source_video.path),
            run,
            guide_audio=Path(project.guide_audio.path) if project.guide_audio else None,
            analysis_signature=project.analysis_signature,
            stage_type="director_api",
        )
        debug.RUNS[state.run_id] = state
        asyncio.create_task(_run_director_state(state, provider))
        return {
            "status": "started",
            "run_id": state.run_id,
            "stage": "director_api",
            "provider": provider,
            "source_video_sent_to_ai": False,
            "resolve_calls": 0,
        }

    @app.get("/api/curation/social/status")
    async def social_status() -> dict[str, Any]:
        return {"providers": social_profiles.status(), "resolve_calls": 0}

    @app.post("/api/curation/social/{provider}/login")
    async def social_login(provider: str) -> dict[str, Any]:
        clean = str(provider or "").casefold().strip()
        if clean not in SUPPORTED_SOCIAL_PROVIDERS:
            raise HTTPException(status_code=404, detail="social provider non supportato")
        try:
            result = await asyncio.to_thread(social_profiles.open_login, clean)
        except (OSError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=503, detail=f"browser social non disponibile: {exc}") from exc
        return {**result, "resolve_calls": 0}

    @app.post("/api/curation/social/{provider}/check")
    async def social_check(provider: str) -> dict[str, Any]:
        clean = provider.casefold().strip()
        if clean not in {"tiktok", "instagram"}:
            raise HTTPException(status_code=404, detail="unsupported social provider")
        return {**await social_profiles.check_search(clean), "resolve_calls": 0}

    @app.get("/api/curation/projects")
    async def list_projects() -> dict[str, Any]:
        return {"projects": project_library_rows(store), "resolve_calls": 0}

    @app.patch("/api/curation/projects/{project_id}")
    async def rename_project_route(project_id: str, request: RenameProjectRequest) -> dict[str, Any]:
        load_project(project_id)
        try:
            project = rename_project(store, project_id, request.name)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _project_payload(project)

    @app.delete("/api/curation/projects/{project_id}")
    async def delete_project_route(project_id: str) -> dict[str, Any]:
        run = run_root(project_id)
        if _active_run_for(run):
            raise HTTPException(status_code=409, detail="project stage already running")
        return delete_project_tree(store, project_id)

    @app.post("/api/curation/projects/{project_id}/media/clean")
    async def clean_media_route(project_id: str) -> dict[str, Any]:
        run = run_root(project_id)
        if _active_run_for(run):
            raise HTTPException(status_code=409, detail="project stage already running")
        cleanup = clean_project_media(run, active_retrieval_root(run))
        return {"project_id": project_id, "cleanup": cleanup, "resolve_calls": 0}

    @app.post("/api/curation/projects/{project_id}/source/social")
    async def source_project_social(project_id: str, request: SocialSearchRequest | None = None) -> dict[str, Any]:
        providers = tuple(dict.fromkeys((request or SocialSearchRequest()).providers))
        if not providers or any(p not in {"tiktok", "instagram"} for p in providers):
            raise HTTPException(status_code=422, detail="Select TikTok and/or Instagram")
        project = load_project(project_id)
        run = run_root(project_id)
        for required in ("transcript-raw.json", "semantic-chunks.json", "semantic-beats.json"):
            if not (run / required).is_file():
                raise HTTPException(status_code=422, detail="analysis required before social sourcing")
        visual_plan = _read_json(run / "visual-plan.json", {})
        beats = visual_plan.get("visual_beats", []) if isinstance(visual_plan, dict) else []
        if not any(isinstance(row, dict) and row.get("action") == "BROLL" for row in beats):
            raise HTTPException(status_code=422, detail="no BROLL beats available for social sourcing")
        if project.source_video is None:
            raise HTTPException(status_code=422, detail="source video required")
        if _active_run_for(run):
            raise HTTPException(status_code=409, detail="project stage already running")
        state = debug.RunState(
            uuid.uuid4().hex[:12],
            Path(project.source_video.path),
            run,
            guide_audio=Path(project.guide_audio.path) if project.guide_audio else None,
            analysis_signature=project.analysis_signature,
            stage_type="social",
        )
        debug.RUNS[state.run_id] = state
        asyncio.create_task(_run_social_state(state, providers))
        return {
            "status": "started",
            "run_id": state.run_id,
            "stage": "social",
            "providers": list(providers),
            "resolve_calls": 0,
        }

    @app.post("/api/curation/projects/{project_id}/beats/{beat_id}/research")
    async def research_beat_route(project_id: str, beat_id: str, request: BeatResearchRequest) -> dict[str, Any]:
        project = load_project(project_id)
        run = run_root(project_id)
        if request.mode not in {"replace", "append"}:
            raise HTTPException(status_code=422, detail="mode must be replace or append")
        provider_scope = tuple(dict.fromkeys(str(value).casefold().strip() for value in request.providers if str(value).strip()))
        allowed_providers = {"youtube", "youtube_shorts", "tiktok", "instagram", "web_video", "pexels", "envato"}
        if any(value not in allowed_providers for value in provider_scope):
            raise HTTPException(status_code=422, detail="unsupported research provider")
        _validate_broll_beat(run, beat_id)
        if project.source_video is None:
            raise HTTPException(status_code=422, detail="source video required")
        if _active_run_for(run):
            raise HTTPException(status_code=409, detail="project stage already running")
        stage = research_stage_type(beat_id, request.mode)
        state = debug.RunState(
            uuid.uuid4().hex[:12], Path(project.source_video.path), run,
            guide_audio=Path(project.guide_audio.path) if project.guide_audio else None,
            analysis_signature=project.analysis_signature, stage_type=stage,
        )
        debug.RUNS[state.run_id] = state
        asyncio.create_task(_run_research_state(state, beat_id, request.mode, provider_scope, research_runner))
        return {
            "status": "started",
            "run_id": state.run_id,
            "stage": stage,
            "providers": list(provider_scope),
            "resolve_calls": 0,
        }

    return app


app = create_app()
