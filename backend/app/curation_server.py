"""Product server extension for RAMBLA project/media lifecycle controls.

The proven debug_server remains the core project/curation runtime. This module
adds project-library, clean-media and beat-scoped research routes without
coupling those operations to Analyze/ASR.
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
from .curation_project import ProjectStore
from .curation_ui_v2 import render_curation_page_v2
from .editorial_import import active_retrieval_root
from .project_maintenance import clean_project_media, delete_project_tree, project_library_rows, rename_project
from .debug_research_cli import research_stage_type


class RenameProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str


class BeatResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: str


ResearchRunner = Callable[[debug.RunState, str, str], Awaitable[Any] | Any]


def _default_project_root() -> Path:
    return Path(os.environ.get("RAMBLA_PROJECT_ROOT", str(Path(debug.DEFAULT_OUTPUT).parent / "curation-projects")))


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


async def _default_research_runner(state: debug.RunState, beat_id: str, mode: str) -> None:
    command = [
        sys.executable, "-m", "backend.app.debug_research_cli",
        "--video", str(state.video_path), "--output-dir", str(state.output_dir),
        "--beat-id", beat_id, "--research-mode", mode,
        "--client-id", f"project-{state.output_dir.parent.name}",
    ]
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


async def _run_research_state(state: debug.RunState, beat_id: str, mode: str, runner: ResearchRunner | None) -> None:
    state.status = "RUNNING"
    try:
        await debug._emit(state, debug.DebugEvent("research", "Beat research avviata", 1.0, {"beat_id": beat_id, "mode": mode}))
        result = (runner or _default_research_runner)(state, beat_id, mode)
        if inspect.isawaitable(result):
            await result
        if state.status != "CANCELLED":
            state.status = "SUCCEEDED"
            state.return_code = 0
            await debug._emit(state, debug.DebugEvent("research", "Beat research completata", 100.0, {"beat_id": beat_id, "mode": mode}))
    except Exception as exc:
        if state.status != "CANCELLED":
            state.status = "FAILED"
            state.return_code = state.return_code if state.return_code is not None else 1
            await debug._emit(state, debug.DebugEvent("error", str(exc), data={"beat_id": beat_id, "mode": mode}))
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

    def load_project(project_id: str):
        try:
            return store.load(project_id)
        except (FileNotFoundError, ValueError, json.JSONDecodeError):
            raise HTTPException(status_code=404, detail="project non trovato") from None

    def run_root(project_id: str) -> Path:
        load_project(project_id)
        return root / project_id / "run"

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

    @app.post("/api/curation/projects/{project_id}/beats/{beat_id}/research")
    async def research_beat_route(project_id: str, beat_id: str, request: BeatResearchRequest) -> dict[str, Any]:
        project = load_project(project_id)
        run = run_root(project_id)
        if request.mode not in {"replace", "append"}:
            raise HTTPException(status_code=422, detail="mode must be replace or append")
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
        asyncio.create_task(_run_research_state(state, beat_id, request.mode, research_runner))
        return {"status": "started", "run_id": state.run_id, "stage": stage, "resolve_calls": 0}

    return app


app = create_app()
