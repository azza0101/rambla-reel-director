"""Product server extension for RAMBLA project/media lifecycle controls.

The proven debug_server remains the core project/curation runtime. This module
adds project-library, clean-media, social login and beat-scoped research routes
without coupling those operations to Analyze/ASR.
"""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
import uuid
from typing import Any, Awaitable, Callable

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

from . import debug_server as debug
from .browser_profiles import BrowserProfileManager, SUPPORTED_SOCIAL_PROVIDERS
from .curation_project import ProjectStore
from .curation_ui_v2 import render_curation_page_v2
from .editorial_import import active_retrieval_root
from .project_maintenance import clean_beat_media, clean_project_media, delete_project_tree, project_library_rows, rename_project
from .debug_research_cli import research_stage_type
from .theme_preferences import ThemePreferences, load_theme_preferences, save_theme_preferences, validate_theme_preferences
from .resolve_title_templates import DEFAULT_RESOLVE_TITLE_NAME
from .export_components import ExportComponents, normalize_components, filter_selected_media


class BeatSplitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cut: int = Field(gt=0)
    revision: str


class PhraseCorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunks: dict[str, str] = Field(min_length=1, max_length=100)
    expected_text: str


class RenameProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str


class SocialSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    providers: tuple[str, ...] = ("tiktok", "instagram")


class SocialSessionQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=300)
    limit: int = Field(default=6, ge=1, le=30)


class BeatResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: str
    providers: tuple[str, ...] = ()
    visual_verify: bool = False
    variation_round: int = Field(default=0,ge=0)
    query_overrides: dict[str,str] = Field(default_factory=dict,max_length=30)
    magic_exact_query: bool = False


class DirectorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = "auto"


class FullTranscriptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=500_000)
    expected_revision: str = Field(min_length=1, max_length=128)


class PhraseIntentsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    changes: dict[str, dict[str, Any]] = Field(max_length=10_000)
    expected_signature: str = Field(min_length=1, max_length=128)


class ResolveTitleTemplateSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template_id: str = Field(min_length=8, max_length=100)


class EnvatoDownloadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: str = Field(min_length=8, max_length=300)


class ResolveBridgeCaptureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str | None = None
    detect_videos: bool = True
    include_v1: bool = False
    force_recalculate: bool = False


class ResolveBridgeSessionRequest(BaseModel):
    bridge_session_id: str | None = Field(default=None, max_length=128)
    bridge_version: str | None = Field(default=None, max_length=32)


class ResolveHandoffApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    destination_mode: str = "new"
    apply_scope: str = "all"
    current_project: str
    current_timeline_id: str
    current_mark_in: int | None = None


class GenericCoverageSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_ids: list[str] = Field(default_factory=list, max_length=12)


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
    if state.research_options:
        command += ['--search-options-json',json.dumps(state.research_options)]
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
        detail = next((e.message for e in reversed(state.events) if e.stage == 'log' and any(token in e.message for token in ('GroqAPIError:', 'GeminiAPIError:', 'ValueError:', 'RuntimeError:'))), '')
        if 'max completion tokens' in detail or 'output truncated' in detail or 'max_completion_tokens' in detail:
            detail = 'Risposta Director troncata al limite di token. Nessun nuovo piano attivato; testo corretto conservato.'
        raise RuntimeError(detail[:500] or f"API Director worker exited with code {state.return_code}; consulta la console")


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
    review_bridge_client: Any = None,
    resolve_template_library_root: Path | None = None,
    resolve_template_bundled_root: Path | None = None,
    resolve_template_install_root: Path | None = None,
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
    from .resolve_handoff import ResolveHandoffStore
    from .resolve_handoff_jobs import ResolveHandoffJobs
    from .resolve_textplus_timeline import run_resolve_helper as resolve_handoff_runner
    handoff_store = ResolveHandoffStore(root)
    handoff_jobs = ResolveHandoffJobs(handoff_store, resolve_handoff_runner)
    app.state.resolve_handoff_jobs = handoff_jobs
    last_resolve_bridge_status = {'connected': False, 'bridge_api_version': 2}
    from .resolve_prepare_jobs import ResolvePrepareJobs
    prepare_jobs = ResolvePrepareJobs()
    social_profiles = browser_profile_manager or BrowserProfileManager(_default_browser_profile_root(root), owns_live_session=True)
    app.state.social_profiles = social_profiles
    envato_download_sessions: dict[str, dict[str, Any]] = {}
    bridge_session_path = root.parent / "bridge-session.json"
    theme_preferences_path = root.parent / "theme-preferences.json"
    bridge_session_state = _read_json(bridge_session_path, {})
    active_bridge_session_id = str(bridge_session_state.get("bridge_session_id") or "")
    bridge_last_seen = 0.0
    active_bridge_version = ''

    @app.post("/api/curation/resolve-bridge/session")
    async def start_resolve_bridge_session(request: ResolveBridgeSessionRequest | None = None) -> dict[str, Any]:
        nonlocal active_bridge_session_id, bridge_last_seen, active_bridge_version
        requested = str(request.bridge_session_id or "").strip() if request else ""
        active_bridge_session_id = requested or uuid.uuid4().hex
        active_bridge_version = str(request.bridge_version or '') if request else ''
        bridge_last_seen = time.time()
        from .atomic_io import write_json
        write_json(bridge_session_path, {"bridge_session_id": active_bridge_session_id, "last_seen": bridge_last_seen})
        return {"bridge_session_id": active_bridge_session_id, "connected": True, "last_seen": bridge_last_seen}

    @app.get("/api/curation/resolve-bridge/session")
    async def resolve_bridge_session_status() -> dict[str, Any]:
        age = max(0.0, time.time() - bridge_last_seen) if bridge_last_seen else None
        return {"bridge_session_id": active_bridge_session_id, "connected": age is not None and age <= 6.0,
                "last_seen": bridge_last_seen or None, "age_seconds": age}

    @app.get("/api/curation/desktop-target")
    async def desktop_target() -> dict[str, Any]:
        target = _read_json(root.parent / "desktop-target.json", {})
        return {"project_id": str(target.get("project_id") or ""),
                "url": str(target.get("url") or ""),
                "revision": int(target.get("revision") or 0)}

    @app.get("/api/curation/theme-preferences")
    async def get_theme_preferences() -> dict[str, Any]:
        return {"theme": load_theme_preferences(theme_preferences_path), "resolve_calls": 0}

    @app.put("/api/curation/theme-preferences")
    async def put_theme_preferences(request: ThemePreferences) -> dict[str, Any]:
        try:
            validated = validate_theme_preferences(request)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"theme": save_theme_preferences(theme_preferences_path, validated), "resolve_calls": 0}

    @app.post("/api/curation/projects/{project_id}/workspace-backup")
    async def create_workspace_backup(project_id: str) -> dict[str, Any]:
        load_project(project_id)
        from .workspace_backup import backup_project_state
        archive = await asyncio.to_thread(
            backup_project_state, root / project_id, root.parent / "backups"
        )
        return {"status": "saved", "project_id": project_id, "backup": archive.name}

    @app.get("/api/curation/resolve-bridge/status")
    async def resolve_bridge_status() -> dict[str, Any]:
        nonlocal last_resolve_bridge_status
        if handoff_jobs.is_applying:
            return {**last_resolve_bridge_status, 'operation_in_progress': True}
        from .resolve_bridge import connect_resolve, timeline_range
        try:
            resolve = await asyncio.to_thread(connect_resolve)
            project = resolve.GetProjectManager().GetCurrentProject()
            timeline = project.GetCurrentTimeline() if project else None
            if not project or not timeline:
                raise RuntimeError("Apri un progetto e una timeline DaVinci Resolve")
            mark_in, mark_out, source = timeline_range(timeline)
            last_resolve_bridge_status = {"connected": True, "bridge_api_version": 2,
                    "project": project.GetName(), "timeline": timeline.GetName(),
                    "timeline_id": str(timeline.GetUniqueId()),
                    "mark_in": mark_in, "mark_out": mark_out, "range_source": source}
            return last_resolve_bridge_status
        except Exception as exc:
            return {"connected": False, "bridge_api_version": 2, "detail": str(exc)}

    @app.post("/api/curation/resolve-bridge/install")
    async def resolve_bridge_install() -> dict[str, Any]:
        import shutil
        source = Path(__file__).resolve().parents[2] / "tools" / "resolve_bridge" / "RAMBLA_B_ROLL.py"
        target = Path(os.environ.get("APPDATA", str(Path.home() / "AppData/Roaming"))) / (
            "Blackmagic Design/DaVinci Resolve/Support/Fusion/Scripts/Utility/RAMBLA_B_ROLL.py"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return {"status": "installed", "path": str(target), "menu": "Workspace > Scripts > RAMBLA_B_ROLL"}

    @app.get("/api/curation/resolve-bridge/plugin.py")
    async def resolve_bridge_plugin_source() -> PlainTextResponse:
        source = Path(__file__).resolve().parents[2] / "tools" / "resolve_bridge" / "RAMBLA_B_ROLL.py"
        payload = source.read_bytes()
        return PlainTextResponse(
            payload.decode("utf-8"), media_type="text/x-python",
            headers={"X-RAMBLA-Bridge-SHA256": hashlib.sha256(payload).hexdigest()},
        )

    @app.post('/api/curation/resolve-bridge/open')
    async def resolve_bridge_open() -> dict[str, Any]:
        from .resolve_project_links import saved_project_to_open
        try:
            status = await asyncio.wait_for(resolve_bridge_status(), timeout=5)
        except asyncio.TimeoutError:
            status = {}
        project_id, opened_from = saved_project_to_open(root, status.get('timeline_id', ''))
        if not project_id:
            raise HTTPException(status_code=409, detail='Nessun progetto salvato da riaprire. Usa USA AUDIO IN RMBL B ROLL una prima volta.')
        project = store.load(project_id)
        return {'project_id': project_id, 'name': project.name, 'url': f'/curation?project={project_id}',
                'opened_from': opened_from}

    @app.post("/api/curation/resolve-bridge/capture")
    async def resolve_bridge_capture(request: ResolveBridgeCaptureRequest) -> dict[str, Any]:
        import tempfile
        from .atomic_io import write_json
        from .resolve_bridge import can_reuse_audio_capture, capture_active_timeline, inspect_active_timeline, require_explicit_capture_range
        inspection = await asyncio.to_thread(
            inspect_active_timeline, detect_videos=request.detect_videos, include_v1=request.include_v1, include_cut_snapshot=True
        )
        if request.force_recalculate:
            try:
                require_explicit_capture_range(inspection.get("range_source", "timeline"))
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        from .resolve_project_links import linked_project
        saved_id = linked_project(root, inspection['resolve_timeline_id'])
        saved_manifest = _read_json(root / saved_id / 'resolve-bridge.json', {}) if saved_id else {}
        if (saved_id and not request.project_id
                and saved_manifest.get('resolve_timeline_id') != inspection['resolve_timeline_id']
                and (root / saved_id / 'run' / 'phrase-intents.json').is_file()):
            raise HTTPException(status_code=409, detail=(
                'Questa è una timeline generata da RAMBLA. Premi APRI RAMBLA per ritrovare le selezioni salvate. '
                'Per aggiornare la guida audio, seleziona la timeline sorgente: '
                + str(saved_manifest.get('resolve_timeline') or 'originale')
            ))
        linked: list[tuple[int, str, dict[str, Any]]] = []
        for path in root.glob("*/resolve-bridge.json"):
            manifest = _read_json(path, {})
            try:
                row=(path.stat().st_mtime_ns,path.parent.name,manifest)
                if str(manifest.get("resolve_timeline_id") or "") == inspection["resolve_timeline_id"]: linked.append(row)
            except OSError: pass
        linked.sort(reverse=True)
        from .resolve_project_links import linked_project
        preferred = linked_project(root, inspection['resolve_timeline_id'])
        # Capture updates only a project bound to this exact source timeline.
        # Opening a generated copy uses /open and its persistent lineage.
        exact_preferred = preferred if any(row[1] == preferred for row in linked) else ''
        project_id = str(request.project_id or "").strip() or exact_preferred or (linked[0][1] if linked else "")
        if project_id:
            project = store.load(project_id)
            manifest = _read_json(root / project_id / "resolve-bridge.json", {})
            guide_ready = bool(project.guide_audio and Path(project.guide_audio.path).is_file())
            if can_reuse_audio_capture(
                manifest, inspection, guide_ready=guide_ready,
                force_recalculate=request.force_recalculate,
            ):
                reused = {**manifest, **inspection, "schema_version": "rambla-resolve-bridge-1",
                          "project_id": project_id, "reused_audio": True,
                          "reused_audio_reason": "unchanged_audio"}
                write_json(root / project_id / "resolve-bridge.json", reused)
                return {"status": "reused", "project_id": project_id,
                        "url": f"/curation?project={project_id}", **reused}
        try:
            capture = await asyncio.to_thread(
                capture_active_timeline, Path(tempfile.gettempdir()) / "RAMBLA-BROLL-Bridge",
                detect_videos=request.detect_videos, include_v1=request.include_v1,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if project_id:
            project = store.load(project_id)
            from .workspace_backup import backup_project_state
            await asyncio.to_thread(backup_project_state, root / project_id, root.parent / 'backups')
        else:
            project = store.create(f"{capture['resolve_project']} · {capture['resolve_timeline']}")
            project_id = project.project_id
        audio_path = Path(capture["audio_path"])
        project = await asyncio.to_thread(
            store.write_primary_audio, project_id, audio_path.name, [audio_path.read_bytes()]
        )
        manifest = {"schema_version": "rambla-resolve-bridge-1", **capture, "project_id": project_id}
        write_json(root / project_id / "resolve-bridge.json", manifest)
        from .resolve_project_links import link_project
        link_project(root, project_id, capture.get('resolve_timeline_id'))
        audio_path.unlink(missing_ok=True)
        return {"status": "captured", "project_id": project_id,
                "url": f"/curation?project={project_id}", **capture}

    @app.get("/api/curation/projects/{project_id}/resolve-bridge")
    async def project_resolve_bridge(project_id: str) -> dict[str, Any]:
        load_project(project_id)
        manifest = _read_json(root / project_id / "resolve-bridge.json", {})
        if not manifest:
            return {"received": False, "detect_videos": False, "existing_video_count": 0}
        return {
            "received": True,
            "resolve_project": manifest.get("resolve_project"),
            "resolve_timeline": manifest.get("resolve_timeline"),
            "duration": manifest.get("duration"),
            "detect_videos": bool(manifest.get("detect_videos")),
            "include_v1": bool(manifest.get("include_v1")),
            "existing_video_count": len(manifest.get("existing_video_ranges") or []),
            "audio_capture_format": manifest.get("audio_capture_format"),
        }
    if review_bridge_client is None:
        from .review_bridge import ReviewBridgeClient
        review_bridge_client = ReviewBridgeClient.from_environment()
    app.state.review_bridge = review_bridge_client
    title_library_root = Path(resolve_template_library_root or root.parent / "resolve-title-templates")
    title_bundled_root = Path(
        resolve_template_bundled_root
        or Path(__file__).resolve().parents[1] / "assets" / "resolve_titles"
    )
    title_install_root = Path(
        resolve_template_install_root
        or Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
        / "Blackmagic Design" / "DaVinci Resolve" / "Support" / "Fusion" / "Templates"
    )

    from contextlib import asynccontextmanager
    previous_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def social_lifespan(application):
        async with previous_lifespan(application) as state:
            try:
                yield state
            finally:
                closer = getattr(social_profiles, "close", None)
                if closer:
                    await closer()

    app.router.lifespan_context = social_lifespan

    @app.post("/api/curation/social/{provider}/session-search")
    async def session_search(provider: str, query: SocialSessionQuery, request: Request):
        import secrets
        expected = os.environ.get("RAMBLA_SOCIAL_SESSION_TOKEN", "")
        supplied = request.headers.get("X-Rambla-Session", "")
        if not expected or not secrets.compare_digest(expected, supplied):
            raise HTTPException(status_code=403, detail="Internal session authentication required")
        if provider not in {"tiktok", "instagram"}:
            raise HTTPException(status_code=404, detail="unsupported social provider")
        from .social_browser_source import BrowserSocialSource
        try:
            result=await BrowserSocialSource(provider, social_profiles)._browser_search(query.query, query.limit)
            social_profiles.connection_ready[provider]=bool(result.get('rows')) or result.get('diagnostics',{}).get('browser_state')=='zero_results'
            return result
        except Exception as exc:
            social_profiles.connection_ready[provider]=False
            raise HTTPException(status_code=503, detail=str(exc)[:400]) from exc

    @app.post("/api/curation/social/{provider}/session-cookies")
    async def session_cookies(provider: str, request: Request):
        import secrets
        expected=os.environ.get('RAMBLA_SOCIAL_SESSION_TOKEN','')
        if not expected or not secrets.compare_digest(expected,request.headers.get('X-Rambla-Session','')):
            raise HTTPException(status_code=403,detail='Internal session authentication required')
        if provider not in {'tiktok','instagram'} or not social_profiles.status().get(provider,{}).get('connection_ready'):
            raise HTTPException(status_code=409,detail='Verify the existing provider session first')
        async def read_cookie_scope(page,context):
            return await context.cookies(['https://www.'+provider+'.com/'])
        return {'cookies':await social_profiles.run_in_profile(provider,read_cookie_scope)}

    def load_project(project_id: str):
        try:
            return store.load(project_id)
        except (FileNotFoundError, ValueError, json.JSONDecodeError):
            raise HTTPException(status_code=404, detail="project non trovato") from None

    def run_root(project_id: str) -> Path:
        load_project(project_id)
        return root / project_id / "run"

    from .cut_pass_routes import install_cut_routes
    cut_engine = install_cut_routes(app, store, root, load_project, _active_run_for)

    @app.middleware('http')
    async def protect_cut_resolve_export(request, call_next):
        parts=request.url.path.split('/')
        if request.method=='POST' and len(parts)>5 and parts[1:4]==['api','curation','projects']:
            pid=parts[4]
            if parts[5] == 'resolve':
                try:
                    load_project(pid)
                except HTTPException as exc:
                    return JSONResponse(status_code=exc.status_code,content={'detail':exc.detail})
                if (root/pid/'cut-origin.json').is_file():
                    return JSONResponse(status_code=409,content={'detail':
                        'Progetto CUT: revisione e workflow disponibili nel plugin. L’applicazione dei tagli alla timeline Resolve sarà abilitata nella fase successiva.'})
        return await call_next(request)

    def title_templates():
        from .resolve_title_templates import template_library
        return template_library(title_library_root, title_bundled_root)

    def title_row(template) -> dict[str, Any]:
        from .resolve_title_templates import template_install_status
        return {
            "template_id": template.template_id,
            "display_name": template.display_name,
            "resolve_name": template.resolve_name,
            "original_filename": template.original_filename,
            "size_bytes": template.size_bytes,
            "sha256": template.sha256,
            "bundled": template.bundled,
            "default": template.resolve_name == DEFAULT_RESOLVE_TITLE_NAME,
            "install_status": template_install_status(template, title_install_root),
        }

    def persist_title_selection(project_id: str, template) -> None:
        selection_path = root / project_id / "resolve-title-template.json"
        temporary = selection_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"template_id": template.template_id, "resolve_name": template.resolve_name}),
            encoding="utf-8",
        )
        os.replace(temporary, selection_path)

    def selected_title(project_id: str):
        load_project(project_id)
        rows = title_templates()
        selection_path = root / project_id / "resolve-title-template.json"
        selection = _read_json(selection_path, {}) if selection_path.is_file() else {}
        selected_id = str(selection.get("template_id") or "")
        selected_name = str(selection.get("resolve_name") or "")
        if selected_id:
            chosen = next((row for row in rows if row.template_id == selected_id), None)
            if chosen is not None:
                return chosen
            # v0046 and earlier stored only the template hash. If that bundled
            # preset disappeared (notably v8), migrate the legacy selection to
            # the single current default instead of carrying a dead name forever.
            if selected_name:
                raise HTTPException(status_code=409, detail="Selected Resolve title template file is missing")
        chosen = next((row for row in rows if row.resolve_name == DEFAULT_RESOLVE_TITLE_NAME), None)
        if chosen is None:
            raise HTTPException(
                status_code=409,
                detail=f"Bundled {DEFAULT_RESOLVE_TITLE_NAME} template is missing",
            )
        if selected_id:
            persist_title_selection(project_id, chosen)
        return chosen

    @app.get("/api/curation/resolve-title-templates")
    async def list_resolve_title_templates() -> dict[str, Any]:
        return {"templates": [title_row(row) for row in title_templates()]}

    @app.post("/api/curation/resolve-title-templates")
    async def upload_resolve_title_template(request: Request) -> dict[str, Any]:
        from .resolve_title_templates import TemplateValidationError, store_uploaded_drfx
        from io import BytesIO
        try:
            payload = bytearray()
            async for block in request.stream():
                payload.extend(block)
                if len(payload) > 64 * 1024 * 1024:
                    raise TemplateValidationError("DRFX upload is too large")
            filename = request.headers.get("X-Rambla-Filename", "template.drfx")
            template = store_uploaded_drfx(BytesIO(payload), filename, title_library_root)
            return {"template": title_row(template)}
        except TemplateValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/curation/resolve-title-templates/{template_id}/install")
    async def install_resolve_title_template(template_id: str) -> dict[str, Any]:
        from .resolve_title_templates import TemplateValidationError, install_template
        template = next((row for row in title_templates() if row.template_id == template_id), None)
        if template is None:
            raise HTTPException(status_code=404, detail="Resolve title template not found")
        try:
            result = install_template(template, title_install_root)
            return {"status": result.status, "template": title_row(template)}
        except (OSError, TemplateValidationError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/curation/projects/{project_id}/resolve-title-template")
    async def get_project_resolve_title_template(project_id: str) -> dict[str, Any]:
        return {"template": title_row(selected_title(project_id))}

    @app.put("/api/curation/projects/{project_id}/resolve-title-template")
    async def set_project_resolve_title_template(
        project_id: str, request: ResolveTitleTemplateSelectionRequest
    ) -> dict[str, Any]:
        load_project(project_id)
        template = next((row for row in title_templates() if row.template_id == request.template_id), None)
        if template is None:
            raise HTTPException(status_code=404, detail="Resolve title template not found")
        persist_title_selection(project_id, template)
        return {"template": title_row(template)}

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
        from .transcript_intents import load_phrase_intents
        intent_state = load_phrase_intents(run)
        if intent_state["explicit"] and not any(
            row.get("coverage") for row in intent_state["phrases"].values()
        ):
            raise HTTPException(status_code=422, detail="Select at least one Coverage phrase before generating the plan")
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
            opener = getattr(social_profiles, "open_login_async", None)
            result = await opener(clean) if opener else await asyncio.to_thread(social_profiles.open_login, clean)
        except (OSError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=503, detail=f"browser social non disponibile: {exc}") from exc
        return {**result, "resolve_calls": 0}

    @app.post("/api/curation/social/{provider}/check")
    async def social_check(provider: str) -> dict[str, Any]:
        clean = provider.casefold().strip()
        if clean not in {"tiktok", "instagram"}:
            raise HTTPException(status_code=404, detail="unsupported social provider")
        return {**await social_profiles.check_search(clean), "resolve_calls": 0}

    @app.post("/api/curation/projects/{project_id}/envato/download/start")
    async def start_envato_download(project_id: str, request: EnvatoDownloadRequest) -> dict[str, Any]:
        from .browser_profiles import BrowserUnavailableError
        from .curation_artifacts import load_curation_run
        from .envato_download_bridge import capture_snapshot, default_downloads_dir
        run = run_root(project_id)
        candidate = load_curation_run(run).candidate_index.get(request.asset_id)
        if candidate is None or candidate.provider != "envato":
            raise HTTPException(status_code=404, detail="Envato asset not found")
        downloads = default_downloads_dir()
        downloads.mkdir(parents=True, exist_ok=True)
        token = uuid.uuid4().hex
        envato_download_sessions[token] = {
            "project_id": project_id,
            "asset_id": request.asset_id,
            "downloads": downloads,
            "baseline": capture_snapshot(downloads),
        }
        try:
            await asyncio.to_thread(
                social_profiles.open_login,
                "envato",
                start_url=candidate.source_page,
            )
        except (BrowserUnavailableError, OSError, RuntimeError, ValueError) as exc:
            envato_download_sessions.pop(token, None)
            raise HTTPException(status_code=503, detail=f"Google Chrome non disponibile: {exc}") from exc
        return {
            "status": "waiting",
            "token": token,
            "asset_id": request.asset_id,
            "open_url": candidate.source_page,
            "opened_in_chrome": True,
            "detail": "Complete the official Envato download in Chrome; RAMBLA will attach the completed file.",
            "resolve_calls": 0,
        }

    @app.get("/api/curation/projects/{project_id}/envato/download/{token}")
    async def envato_download_status(project_id: str, token: str) -> dict[str, Any]:
        from .envato_download_bridge import adopt_new_download
        session = envato_download_sessions.get(token)
        if session is None or session.get("project_id") != project_id:
            raise HTTPException(status_code=404, detail="Envato download session not found")
        result = await asyncio.to_thread(
            adopt_new_download,
            session["downloads"],
            session["baseline"],
            run_root(project_id),
            session["asset_id"],
        )
        if result.get("status") == "ready":
            envato_download_sessions.pop(token, None)
        return {**result, "resolve_calls": 0}

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

    @app.get("/api/curation/projects/{project_id}/beats/{beat_id}/transcript")
    async def phrase_transcript(project_id: str, beat_id: str):
        from .editorial_import import normalized_chunks
        run=run_root(project_id)
        plan=_read_json(run/'visual-plan.json',{})
        beat=next((b for b in plan.get('visual_beats',[]) if b['id']==beat_id),None)
        if not beat: raise HTTPException(status_code=404,detail='Frase non trovata')
        return {'text':beat['original_text'],'chunks':[c for c in normalized_chunks(run) if c['id'] in beat['covered_chunk_ids']]}

    @app.get("/api/curation/projects/{project_id}/transcript/full")
    async def full_transcript(project_id: str):
        from .transcript_intents import transcript_document
        try:
            run = run_root(project_id)
            document = transcript_document(run)
            bridge = _read_json(root / project_id / "resolve-bridge.json", {})
            document["existing_video_ranges"] = bridge.get("existing_video_ranges", [])
            document["detect_videos"] = bool(bridge.get("detect_videos", False))
            return document
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.put("/api/curation/projects/{project_id}/transcript/full")
    async def save_full_transcript(project_id: str, request: FullTranscriptRequest):
        from .transcript_intents import save_transcript_document
        run = run_root(project_id)
        if _active_run_for(run):
            raise HTTPException(status_code=409, detail="Wait for the running project stage")
        try:
            return save_transcript_document(run, request.text, request.expected_revision)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/curation/projects/{project_id}/phrase-intents")
    async def phrase_intents(project_id: str):
        from .transcript_intents import load_phrase_intents
        try:
            return load_phrase_intents(run_root(project_id))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.put("/api/curation/projects/{project_id}/phrase-intents")
    async def save_intents(project_id: str, request: PhraseIntentsRequest):
        from .transcript_intents import save_phrase_intents
        run = run_root(project_id)
        if _active_run_for(run):
            raise HTTPException(status_code=409, detail="Wait for the running project stage")
        try:
            return save_phrase_intents(run, request.changes, request.expected_signature)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/curation/projects/{project_id}/review/status")
    async def review_status(project_id: str):
        from .review_bridge import load_review_state
        run = run_root(project_id)
        state = load_review_state(run)
        return {
            "configured": bool(getattr(review_bridge_client, "configured", False)),
            "review_id": state.get("review_id"),
            "review_url": state.get("review_url"),
            "last_applied_revision": int(state.get("last_applied_revision", 0) or 0),
        }

    @app.post("/api/curation/projects/{project_id}/review/publish")
    async def publish_review(project_id: str):
        from .review_bridge import build_review_payload, save_review_state
        project = load_project(project_id)
        run = run_root(project_id)
        if _active_run_for(run):
            raise HTTPException(status_code=409, detail="Wait for the running project stage")
        if not getattr(review_bridge_client, "configured", False):
            raise HTTPException(status_code=422, detail="Configure RAMBLA_REVIEW_WEBAPP_URL and RAMBLA_REVIEW_OWNER_SECRET in .env.local")
        try:
            published = await review_bridge_client.publish(build_review_payload(run, project_id, project.name))
            state = {**published, "last_applied_revision": 0}
            save_review_state(run, state)
            return {"configured": True, **state}
        except (OSError, ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/api/curation/projects/{project_id}/review/pull")
    async def pull_review(project_id: str):
        from .review_bridge import apply_review_submission, load_review_state, save_review_state
        run = run_root(project_id)
        if _active_run_for(run):
            raise HTTPException(status_code=409, detail="Wait for the running project stage")
        state = load_review_state(run)
        if not state.get("review_id"):
            raise HTTPException(status_code=409, detail="Create a review link first")
        try:
            remote = await review_bridge_client.pull(str(state["review_id"]))
            revision = int(remote.get("submitted_revision", 0) or 0)
            if not remote.get("submission") or revision <= int(state.get("last_applied_revision", 0) or 0):
                return {**state, "updated": False, "submitted_revision": revision}
            intents = apply_review_submission(run, remote["submission"])
            state["last_applied_revision"] = revision
            save_review_state(run, state)
            return {**state, "updated": True, "submitted_revision": revision, "intents": intents}
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (OSError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/api/curation/projects/{project_id}/exports/captions.srt")
    async def export_semantic_captions(project_id: str):
        from .captions import render_semantic_srt
        from .editorial_import import normalized_chunks
        try:
            body = render_semantic_srt(normalized_chunks(run_root(project_id)))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return PlainTextResponse(body, media_type="application/x-subrip", headers={"Content-Disposition": f'attachment; filename="captions-{project_id}.srt"'})

    @app.get("/api/curation/projects/{project_id}/exports/animation.json")
    async def export_animation_phrases(project_id: str):
        from .animation_context import build_animation_context
        from .transcript_intents import build_animation_export
        plan = _read_json(run_root(project_id) / "visual-plan.json", {})
        try:
            payload = build_animation_export(run_root(project_id), project_id, build_animation_context(plan or None))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return JSONResponse(payload, headers={"Content-Disposition": f'attachment; filename="animation-{project_id}.json"'})

    def project_export_fps(project_id: str, project: Any) -> int:
        bridge = _read_json(root / project_id / 'resolve-bridge.json', {})
        source_fps = getattr(project.source_video, 'fps', 25) if project.source_video else 25
        return int(round(float(bridge.get('fps') or source_fps or 25)))

    @app.get("/api/curation/projects/{project_id}/exports/highlights.json")
    async def export_highlight_textplus(project_id: str):
        from .transcript_intents import build_textplus_export
        project = load_project(project_id)
        fps = project_export_fps(project_id, project)
        try:
            payload = build_textplus_export(run_root(project_id), project_id, fps=fps)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return JSONResponse(payload, headers={"Content-Disposition": f'attachment; filename="resolve-textplus-{project_id}.json"'})

    @app.post("/api/curation/projects/{project_id}/resolve/textplus-timeline")
    async def create_resolve_textplus_timeline(project_id: str):
        from .resolve_textplus_timeline import run_resolve_helper
        from .transcript_intents import build_textplus_export
        project = load_project(project_id)
        fps = project_export_fps(project_id, project)
        try:
            payload = build_textplus_export(run_root(project_id), project_id, fps=fps)
            payload["title_name"] = selected_title(project_id).resolve_name
            return await asyncio.to_thread(run_resolve_helper, payload)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except (OSError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    def combined_resolve_payload(project_id: str, components=None, fps_override=None) -> dict[str, Any]:
        from .transcript_intents import build_combined_resolve_export
        project = load_project(project_id)
        fps = fps_override or project_export_fps(project_id, project)
        payload = build_combined_resolve_export(run_root(project_id), project_id, fps=fps,
            include_highlights=components is None or components['highlights'])
        subtitle_key = hashlib.sha256(
            json.dumps(payload["subtitles"], ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:10]
        subtitle_path = run_root(project_id) / "exports" / (
            f"RAMBLA_{payload['subtitle_count']}_NATIVE_SUBS_{subtitle_key}_{uuid.uuid4().hex[:8]}.srt"
        )
        payload.update(
            mode="combined",
            project_name=project.name,
            timeline_name=f"{project.name} - SUBS + KEYWORDS TIMELINE v1",
            media_bin_name="TEMP",
            subtitle_srt_path=str(subtitle_path),
        )
        if payload['titles'] and (components is None or components['highlights']):
            template = selected_title(project_id)
            payload['title_name'] = template.resolve_name
            payload['title_package_path'] = str(template.source_path)
        elif components is not None and not components['highlights']:
            payload['titles'] = []
            payload['title_count'] = 0
        if components is not None and not components['subtitles']:
            payload['subtitles'] = []
            payload['subtitle_count'] = 0
        return payload

    def broll_timeline_payload(project_id: str, *, allow_unavailable: bool = False, fps_override=None, components=None) -> dict[str, Any]:
        from .broll_timeline_export import build_broll_timeline_plan
        from .curation_artifacts import load_curation_run
        from .video_preview import probe_preview
        project = load_project(project_id)
        run = run_root(project_id)
        fps = fps_override or project_export_fps(project_id, project)
        view = load_curation_run(run)
        selection = _read_json(active_retrieval_root(run) / "selection-plan.json", {"chunks": {}})
        if components is not None:
            selection = {'chunks': {beat_id: {**choice, 'selected_assets': [row for row in choice.get('selected_assets') or []
                if filter_selected_media([view.candidate_index.get(str(row.get('asset_id')))], components)]}
                for beat_id, choice in (selection.get('chunks') or {}).items() if isinstance(choice, dict)}}
            if not any(choice['selected_assets'] for choice in selection['chunks'].values()):
                return {'clips': [], 'clip_count': 0, 'unavailable': [], 'selected_beat_count': 0}
        wanted = {str(row.get('asset_id')) for choice in (selection.get('chunks') or {}).values()
                  for row in choice.get('selected_assets') or []}
        visual_plan = _read_json(run / "visual-plan.json", {})
        assets = {}
        for asset_id, candidate in view.candidate_index.items():
            if asset_id not in wanted:
                continue
            kind = str(candidate.kind or "video")
            path = str(candidate.local_asset_path or "").strip()
            preview_path = str(candidate.preview_path or "").strip()
            full_source = bool(
                path and candidate.source_start_seconds is not None
                and (not preview_path or os.path.normcase(os.path.abspath(path)) != os.path.normcase(os.path.abspath(preview_path)))
            )
            if kind == "video" and candidate.provider == 'pexels':
                from .stock_export_media import stock_media_path
                stock_path = stock_media_path(run, asset_id.rsplit(':', 1)[-1])
                if stock_path.is_file():
                    path = str(stock_path)
                    full_source = True
            if kind == "video" and candidate.provider in {"tiktok", "instagram", "youtube", "youtube_shorts"}:
                from .social_media import media_path
                social_path = media_path(candidate.source_page, candidate.provider, run, "full")
                if social_path.is_file():
                    path = str(social_path)
                    full_source = True
            facts = probe_preview(path) if path and kind == "video" else {"playable": bool(path), "duration": 0}
            selected_start = float(candidate.source_start_seconds or 0) if full_source else 0.0
            selected_end = (
                float(candidate.source_end_seconds)
                if full_source and candidate.source_end_seconds is not None
                else None
            )
            assets[asset_id] = {
                "media_path": path if path and Path(path).is_file() and (kind == "image" or float(facts.get("duration") or 0) > 0) else None,
                "duration_seconds": facts.get("duration", 0),
                "kind": kind,
                "source_start_seconds": selected_start,
                "source_end_seconds": selected_end,
                "source_offset_seconds": selected_start,
                "title": candidate.title,
                "source_page": candidate.source_page,
                "provider": candidate.provider,
            }
        magic = _read_json(active_retrieval_root(run) / 'magic-coverage.json', {})
        decisions = magic.get('decisions') or []
        if decisions:
            from .magic_store import fingerprint
            if magic.get('plan_signature') != fingerprint(visual_plan) or abs(float(magic.get('fps') or 0)-fps) > .001:
                raise ValueError('Il piano MAGICO è cambiato: rigenera le coperture prima di esportare')
        plan = build_broll_timeline_plan(visual_plan, selection, assets, fps=fps, magic_decisions=decisions)
        if plan["selected_beat_count"] == 0:
            raise ValueError("Select at least one B-roll clip before exporting the timeline")
        if plan["unavailable"] and not plan["clips"] and not allow_unavailable:
            rows = ", ".join(f"{row['beat_id']} · {row['asset_id']}: {row['reason']}" for row in plan["unavailable"][:8])
            raise ValueError("No selected clip is ready for timeline export. Download or replace them: " + rows)
        return plan

    async def prepare_selected_timeline_media(project_id: str, report=None, components=None, asset_ids=None) -> list[dict[str, str]]:
        if components is not None and not (components['broll'] or components['social']):
            if report:
                report(60, 'Media esclusi dall’export · salto download')
            return []
        from .curation_artifacts import load_curation_run
        from .resolve_media_issues import download_issue
        from .social_media import media_path, prepare_media
        from .transcript_intents import has_selected_intent
        run = run_root(project_id)
        if not has_selected_intent(run, "coverage"):
            if report:
                report(60, "Nessun B-roll selezionato · salto download media")
            return []
        view = load_curation_run(run)
        selection = _read_json(active_retrieval_root(run) / "selection-plan.json", {"chunks": {}})
        wanted = [str(row.get("asset_id")) for choice in (selection.get("chunks") or {}).values() for row in (choice.get("selected_assets") or [])]
        if asset_ids is not None:
            wanted = list(dict.fromkeys(asset_ids))
        if components is not None:
            wanted = [aid for aid in wanted if filter_selected_media([view.candidate_index.get(aid)], components)]
        failures = []
        for index, asset_id in enumerate(wanted):
            candidate = view.candidate_index.get(asset_id)
            if report:
                report(5 + int(60 * index / max(1, len(wanted))), f'Coperture: {index}/{len(wanted)} pronte · controllo {candidate.title if candidate else asset_id}')
            if candidate and candidate.kind == "image":
                if not candidate.local_asset_path or not Path(candidate.local_asset_path).is_file():
                    failures.append(download_issue(candidate, RuntimeError("Selected image is not available locally")))
                continue
            if candidate and candidate.provider == 'pexels':
                from .stock_export_media import prepare_pexels_video
                try:
                    def download_progress(received, total):
                        fraction = received / total if total else 0
                        report(5 + int(60 * (index + min(1, fraction)) / max(1, len(wanted))),
                               f'Scarico {candidate.title} · {received/1048576:.1f}' + (f'/{total/1048576:.1f}' if total else '') + ' MB')
                    await prepare_pexels_video(run, asset_id.rsplit(':', 1)[-1], progress=download_progress if report else None)
                except Exception as exc:
                    failures.append(download_issue(candidate, exc))
                continue
            if not candidate or candidate.provider not in {"tiktok", "instagram", "youtube", "youtube_shorts"}:
                continue
            if media_path(candidate.source_page, candidate.provider, run, "full").is_file():
                continue
            cookies = []
            if candidate.provider in {"tiktok", "instagram"} and social_profiles.status().get(candidate.provider, {}).get("connection_ready"):
                async def read_session(page, context, source=candidate.source_page):
                    return await context.cookies([source])
                cookies = await social_profiles.run_in_profile(candidate.provider, read_session)
            try:
                await asyncio.to_thread(prepare_media, candidate.source_page, candidate.provider, run, "full", cookies=cookies)
            except (ValueError, RuntimeError) as exc:
                failures.append(download_issue(candidate, exc))
        return failures

    def editing_resolve_payload(project_id: str, components=None) -> dict[str, Any]:
        from .transcript_intents import has_selected_intent
        components = normalize_components(components)
        native_cut = None
        native_reference = None
        if components['video']:
            from .native_cut_export import load_native_cut
            from fractions import Fraction
            native_cut = load_native_cut(root / project_id, root)
            if (root / project_id / 'resolve-bridge.json').is_file():
                raise ValueError('CUT nativo supportato sul video originale caricato, non sulla guida multitraccia Resolve')
            if any(components[k] for k in ('subtitles', 'highlights', 'broll', 'social', 'generic')) and not (root / project_id / 'cut-origin.json').is_file():
                raise ValueError('Conferma CUT e continua prima di esportare testo e coperture sul montaggio pulito')
        elif (root / project_id / 'cut-origin.json').is_file():
            from .native_cut_export import load_native_cut
            from fractions import Fraction
            native_reference = load_native_cut(root / project_id, root)
            from .native_cut_export import find_native_cut_receipt
            receipt = find_native_cut_receipt(root / project_id, root, native_reference)
            if not receipt:
                raise ValueError('Seleziona Video CUT per creare prima la base nativa corrispondente')
        export_cut = native_cut or native_reference
        if components['subtitles'] or components['highlights']:
            payload = combined_resolve_payload(project_id, components, float(Fraction(export_cut['fps'])) if export_cut else None)
        else:
            project = load_project(project_id)
            payload = {'project_id': project_id, 'project_name': project.name,
                       'fps': project_export_fps(project_id, project), 'titles': [], 'subtitles': [],
                       'title_count': 0, 'subtitle_count': 0}
        if (components['broll'] or components['social']) and has_selected_intent(run_root(project_id), "coverage"):
            broll = broll_timeline_payload(project_id, allow_unavailable=True,
                fps_override=float(Fraction(export_cut['fps'])) if export_cut else None, components=components)
            broll['clips'] = filter_selected_media(broll['clips'], components)
            broll['unavailable'] = [row for row in broll['unavailable']
                                    if filter_selected_media([{'provider': str(row.get('asset_id', '')).split(':')[0].split('--')[-1]}], components)]
            broll['clip_count'] = len(broll['clips'])
        else:
            broll = {"clips": [], "clip_count": 0, "unavailable": []}
        project = load_project(project_id)
        bridge = _read_json(root / project_id / "resolve-bridge.json", {})
        generic = _read_json(run_root(project_id) / "generic-coverage.json", {"items": [], "selected": []})
        chosen = set(generic.get("selected") or [])
        used_generics = {str(row.get('asset_id','')).rsplit(':',1)[-1] for row in broll['clips'] if row.get('role') == 'generic'}
        generic_clips = [row for row in generic.get("items") or [] if components['generic'] and str(row.get("provider_id")) in chosen and str(row.get('provider_id')) not in used_generics]
        payload.update(
            mode="editing", broll_clips=broll["clips"], broll_count=broll["clip_count"], broll_unavailable=broll["unavailable"],
            timeline_name=f"{project.name} - SUBS + KEYWORDS + B-ROLL TIMELINE v1",
            media_staging_root=str(run_root(project_id) / "resolve-media"),
            source_timeline_id=bridge.get("resolve_timeline_id"),
            source_project_name=bridge.get("resolve_project"),
            source_timeline_name=bridge.get("resolve_timeline"),
            bridge_mark_in=bridge.get("mark_in"),
            duration_seconds=bridge.get("duration") or 0,
            generic_broll_clips=generic_clips,
            generic_tail_gap_seconds=2.0,
            components=components,
        )
        if native_cut:
            payload.update(native_cut=native_cut, fps=float(Fraction(native_cut['fps'])),
                           duration_seconds=native_cut['duration_seconds'], destination_mode='new')
        elif native_reference:
            payload.update(native_cut_reference=native_reference, source_timeline_id=receipt['timeline_id'],
                           source_project_name=receipt.get('resolve_project'), source_timeline_name=receipt.get('timeline_name'),
                           native_cut_fps=native_reference['fps'], fps=float(Fraction(native_reference['fps'])),
                           duration_seconds=native_reference['duration_seconds'], destination_mode='active')
        return payload

    async def prepare_generic_media(project_id: str, report=None) -> None:
        import httpx
        from .atomic_io import write_json
        path = run_root(project_id) / "generic-coverage.json"
        data = _read_json(path, {"items": [], "selected": []})
        from .stock_export_media import prepare_pexels_video
        by_id = {str(row['provider_id']): row for row in data.get('items') or []}
        errors = []
        selected = list(map(str, data.get('selected') or []))
        for index, provider_id in enumerate(selected):
            if report:
                report(65 + int(15 * index / max(1, len(selected))), f'Video finali: {index}/{len(selected)} pronti · controllo Pexels {provider_id}')
            try:
                def download_progress(received, total):
                    fraction = received / total if total else 0
                    report(65 + int(15 * (index + min(1, fraction)) / max(1, len(selected))),
                           f'Scarico video finale Pexels {provider_id} · {received/1048576:.1f}' + (f'/{total/1048576:.1f}' if total else '') + ' MB')
                by_id[provider_id] = {**by_id.get(provider_id, {}), **await prepare_pexels_video(run_root(project_id), provider_id, progress=download_progress if report else None)}
            except Exception as exc:
                errors.append(f'Pexels {provider_id}: {exc}')
        data['items'] = list(by_id.values())
        write_json(path, data)
        if errors:
            raise ValueError('Download coperture generiche non completato: ' + ' · '.join(errors))
        return
    @app.get("/api/curation/projects/{project_id}/generic-coverage")
    async def generic_coverage(project_id: str, refresh: bool = False, scope: str = "topic", max_queries: int = 4):
        from .atomic_io import write_json
        from .generic_coverage import candidate_dict, derive_topic_queries, merge_unique
        from .online_assets import PexelsSource
        run = run_root(project_id)
        path = run / "generic-coverage.json"
        existing = _read_json(path, {})
        if existing.get("items") and not refresh and scope == "topic":
            return existing
        visual = _read_json(run / "visual-plan.json", {})
        transcript = _read_json(run / "transcript-raw.json", {})
        topic = str(visual.get("global_topic") or visual.get("summary") or "")
        raw_text = str(transcript.get("text") or " ".join(str(x.get("text") or "") for x in transcript.get("segments", []) if isinstance(x, dict)))
        from .geographic_context import places_in, conflicting_place
        from .stock_export_media import preserve_selected_generics
        if scope not in {"topic", "places"}: raise HTTPException(status_code=422, detail="Tipo di copertura sconosciuto")
        source=PexelsSource(os.environ.get("PEXELS_API_KEY"))
        errors=[]; items=[]; places=places_in(raw_text) or places_in(topic)
        query_groups = [(place, [place + " landscape", place + " city", place]) for place in places] if scope == "places" else [("", derive_topic_queries(topic, raw_text))]
        if scope == 'places' and not places:
            errors.append('Nessun luogo riconosciuto nel testo. Specifica il luogo nella trascrizione o usa una query manuale sulla scena.')
        for place, queries in query_groups:
            groups=[]
            for query in queries[:max(1,min(4,max_queries))]:
                try:
                    rows=await source.search(query, orientation="landscape", min_duration=2, max_duration=180, limit=12)
                    group=[{**candidate_dict(row), "coverage_group": scope, "place": place} for row in rows if not place or not conflicting_place(row.title+' '+row.description,[place])]
                    groups.append(group)
                    if len(merge_unique(groups,limit=12)["items"])>=12: break
                except Exception as exc: errors.append(str(exc))
            items.extend(merge_unique(groups,limit=12)['items'])
        retained=[row for row in existing.get('items',[]) if row.get('coverage_group','topic')!=scope]
        merged=merge_unique([items,retained],limit=max(12,len(retained)+len(items)))
        existing = _read_json(path, existing)
        payload={**merged,"items":preserve_selected_generics(existing, merged['items']),"selected":existing.get("selected",[]),"topic":topic or raw_text[:160],"places":places,"errors":errors}
        if scope == 'places':
            locations={str(row['provider_id']):row['place'] for row in items}
            for row in payload['items']:
                if str(row['provider_id']) in locations:
                    row.update(coverage_group='places',place=locations[str(row['provider_id'])])
        write_json(path,payload)
        return payload

    @app.put("/api/curation/projects/{project_id}/generic-coverage/selection")
    async def select_generic_coverage(project_id: str, request: GenericCoverageSelectionRequest):
        from .atomic_io import write_json
        path=run_root(project_id)/"generic-coverage.json"; data=_read_json(path,{"items":[]})
        available={str(row.get("provider_id")) for row in data.get("items") or []}
        if not set(request.provider_ids)<=available: raise HTTPException(status_code=422,detail="Copertura generica sconosciuta")
        data["selected"]=list(dict.fromkeys(request.provider_ids)); write_json(path,data); return data

    def handoff_project_root(project_id: str) -> Path:
        load_project(project_id)
        return root / project_id

    @app.get('/api/curation/projects/{project_id}/export-options')
    async def get_export_options(project_id: str):
        load_project(project_id)
        saved = _read_json(root / project_id / 'export-options.json', {})
        available = ((root / project_id / 'cut-origin.json').is_file() or (root / project_id / 'cut' / 'plan.json').is_file()) and not (root / project_id / 'resolve-bridge.json').is_file()
        draft_cut = available and not (root / project_id / 'cut-origin.json').is_file()
        defaults = {'video': True} if draft_cut else None
        flags = normalize_components(saved.get('components', defaults), has_native_cut=available)
        counts = {key: 0 for key in flags}
        run = run_root(project_id)
        origin = _read_json(root / project_id / 'cut-origin.json', {})
        cut = origin.get('plan') or _read_json(root / project_id / 'cut' / 'plan.json', {})
        counts['video'] = len(cut.get('segments') or [])
        generic = _read_json(run / 'generic-coverage.json', {})
        counts['generic'] = len(generic.get('selected') or [])
        if (run / 'semantic-chunks.json').is_file():
            from .transcript_intents import build_combined_resolve_export
            text = build_combined_resolve_export(run, project_id, include_highlights=flags['highlights'])
            counts['subtitles'], counts['highlights'] = text['subtitle_count'], text['title_count']
            from .curation_artifacts import load_curation_run
            from .export_components import SOCIAL
            view = load_curation_run(run)
            selection = _read_json(active_retrieval_root(run) / 'selection-plan.json', {})
            for choice in (selection.get('chunks') or {}).values():
                for selected in choice.get('selected_assets') or []:
                    candidate = view.candidate_index.get(str(selected.get('asset_id')))
                    if candidate:
                        counts['social' if candidate.provider in SOCIAL else 'broll'] += 1
        return {'components': flags, 'counts': counts,
                'component_availability': {key: not draft_cut for key in ('subtitles', 'highlights', 'broll', 'social', 'generic')},
                'video_available': available,
                'video_reason': 'Conferma CUT e continua per aggiungere testo e coperture ai tagli' if draft_cut else '' if available else 'Video disponibile dopo ANALIZZA CUT sul file originale caricato'}

    @app.put('/api/curation/projects/{project_id}/export-options')
    async def put_export_options(project_id: str, components: ExportComponents):
        load_project(project_id)
        try:
            flags = normalize_components(components)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        from .atomic_io import write_json
        write_json(root / project_id / 'export-options.json', {'components': flags})
        return {'components': flags}

    def find_handoff(package_id: str) -> tuple[Path, dict[str, Any]]:
        matches = list(root.glob(f"*/resolve-outbox/{package_id}/package.json"))
        if not matches:
            raise HTTPException(status_code=404, detail="Pacchetto Resolve non trovato")
        project_root = matches[0].parents[2]
        return project_root, handoff_store.read(project_root, package_id)

    @app.post("/api/curation/projects/{project_id}/resolve-handoffs")
    async def prepare_resolve_handoff(project_id: str, components: ExportComponents | None = None):
        try:
            flags = normalize_components(components)
            media_issues = await prepare_selected_timeline_media(project_id, components=flags)
            if flags['generic']:
                await prepare_generic_media(project_id)
            payload = editing_resolve_payload(project_id, flags)
            payload["project_id"] = project_id
            payload["bridge_session_id"] = active_bridge_session_id
            payload["media_issues"] = media_issues
            package = handoff_store.prepare(handoff_project_root(project_id), payload)
            return {key: value for key, value in package.items() if key != "payload"}
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post('/api/curation/projects/{project_id}/resolve-preparation')
    async def start_resolve_preparation(project_id: str, components: ExportComponents | None = None):
        load_project(project_id)
        try:
            flags = normalize_components(components)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if (root / project_id / 'cut-origin.json').is_file() and not flags['video']:
            try:
                await asyncio.to_thread(editing_resolve_payload, project_id, flags)
            except (OSError, ValueError, KeyError) as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        if flags['video']:
            from .native_cut_export import load_native_cut
            try:
                await asyncio.to_thread(load_native_cut, root / project_id, root)
            except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            if not active_bridge_session_id or time.time() - bridge_last_seen > 6:
                raise HTTPException(status_code=409, detail='Apri il bridge e attendi CONNECTED prima di inviare il CUT nativo')
            if not active_bridge_version.startswith('v') or not active_bridge_version[1:].isdigit() or int(active_bridge_version[1:]) < 71:
                raise HTTPException(status_code=409, detail='Aggiorna il bridge a v0071 per ricevere il CUT nativo')
        session_id = active_bridge_session_id
        async def prepare(report):
            media_issues = await prepare_selected_timeline_media(project_id, report, flags)
            report(65, 'Coperture pronte · controllo video finali')
            if flags['generic']:
                await prepare_generic_media(project_id, report)
            report(80, 'Media pronti · preparo sottotitoli, frasi e tempi')
            payload = await asyncio.to_thread(editing_resolve_payload, project_id, flags)
            payload.update(project_id=project_id, bridge_session_id=session_id)
            payload["media_issues"] = media_issues
            report(85, 'Salvo il pacchetto per il bridge')
            package = await asyncio.to_thread(handoff_store.prepare, handoff_project_root(project_id), payload)
            return {k:v for k,v in package.items() if k != 'payload'}
        return prepare_jobs.start(project_id, prepare)

    @app.get('/api/curation/resolve-preparation/{job_id}')
    async def resolve_preparation_status(job_id: str):
        try:
            return prepare_jobs.status(job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail='Preparazione non disponibile: il server è stato riavviato. Ripeti INVIA A RESOLVE.') from None

    @app.get("/api/curation/resolve-handoffs/pending")
    async def pending_resolve_handoffs(resolve_project: str = "", timeline_id: str = "", bridge_session_id: str = "",
                                       native_only: bool = False):
        rows = handoff_store.pending(resolve_project=resolve_project, timeline_id=timeline_id,
                                     bridge_session_id=bridge_session_id, native_only=native_only)
        return {"packages": [{key: value for key, value in row.items() if key != "payload"} for row in rows]}

    @app.get("/api/curation/resolve-handoffs/{package_id}")
    async def get_resolve_handoff(package_id: str):
        _, package = find_handoff(package_id)
        return {key: value for key, value in package.items() if key != "payload"}

    @app.post("/api/curation/resolve-handoffs/{package_id}/discard")
    async def discard_resolve_handoff(package_id: str):
        project_root, _ = find_handoff(package_id)
        try:
            return handoff_store.transition(project_root, package_id, "discarded")
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/curation/resolve-handoffs/{package_id}/received")
    async def receive_resolve_handoff(package_id: str, request: ResolveBridgeSessionRequest) -> dict[str, Any]:
        project_root, _ = find_handoff(package_id)
        try:
            return handoff_store.mark_received(
                project_root, package_id, bridge_session_id=str(request.bridge_session_id or "")
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/curation/resolve-handoffs/{package_id}/apply")
    async def apply_resolve_handoff(package_id: str, request: ResolveHandoffApplyRequest):
        project_root, package = find_handoff(package_id)
        try:
            if (package.get('payload') or {}).get('native_cut'):
                if package.get('bridge_session_id') != active_bridge_session_id or time.time() - bridge_last_seen > 6:
                    raise ValueError('Sessione bridge cambiata o offline: invia di nuovo il CUT da RMBL')
            # The package can stay open in the Resolve bridge while the user
            # changes the Fusion Title in EDITING. Titles must always use the
            # project's current selection, never the stale title_name frozen
            # when INVIA A RESOLVE originally prepared the handoff.
            if request.apply_scope in {"all", "titles"} and (package.get('payload') or {}).get('titles'):
                project_id = str(package.get("project_id") or project_root.name)
                template = selected_title(project_id)
                handoff_store.update_payload(
                    project_root,
                    package_id,
                    title_name=template.resolve_name,
                    title_package_path=str(template.source_path),
                )
            return handoff_jobs.apply(project_root, package_id, request.destination_mode, request.apply_scope,
                                      current_project=request.current_project,
                                      current_timeline_id=request.current_timeline_id,
                                      current_mark_in=request.current_mark_in)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=423, detail=str(exc)) from exc

    @app.post("/api/curation/resolve-handoffs/{package_id}/cancel")
    async def cancel_resolve_handoff(package_id: str):
        project_root, _ = find_handoff(package_id)
        try:
            return handoff_jobs.cancel(project_root, package_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=423, detail=str(exc)) from exc

    @app.get("/api/curation/resolve-handoffs/{package_id}/status")
    async def resolve_handoff_status(package_id: str):
        _, package = find_handoff(package_id)
        return {key: value for key, value in package.items() if key != "payload"}

    @app.get('/api/curation/resolve-handoffs/{package_id}/diagnostics')
    async def resolve_handoff_diagnostics(package_id: str):
        _, package = find_handoff(package_id)
        version=(Path(__file__).resolve().parents[2]/'RAMBLA_VERSION').read_text(encoding='utf-8').strip()
        return {'version':version,'build':os.environ.get('RAMBLA_BUILD_TOKEN',''),
                'bridge':await resolve_bridge_session_status(),
                **{k:package.get(k) for k in ('package_id','project_id','status','created_at','updated_at','summary','destination_mode','apply_scope','destination_timeline_id','bridge_received_at','progress','error','diagnostics','result')}}

    @app.get('/api/curation/projects/{project_id}/resolve-handoffs/latest')
    async def latest_resolve_handoff(project_id: str):
        load_project(project_id)
        rows = [_read_json(p, {}) for p in (root/project_id/'resolve-outbox').glob('*/package.json')]
        latest = max(rows, key=lambda row:row.get('created_at',''), default={})
        return {k:v for k,v in latest.items() if k != 'payload'}

    @app.get("/api/curation/projects/{project_id}/exports/broll-timeline.xml")
    async def export_broll_timeline_xml(project_id: str):
        from .broll_timeline_export import render_fcp7_xml
        try:
            await prepare_selected_timeline_media(project_id)
            plan = broll_timeline_payload(project_id)
            project = load_project(project_id)
            body = render_fcp7_xml(plan, sequence_name=f"{project.name} - B-ROLL TIMELINE v1")
            return PlainTextResponse(body, media_type="application/xml", headers={"Content-Disposition": f'attachment; filename="{project.name}-broll-timeline-v1.xml"'})
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/curation/projects/{project_id}/resolve/broll-timeline")
    async def create_resolve_broll_timeline(project_id: str):
        from .resolve_textplus_timeline import run_resolve_helper
        try:
            await prepare_selected_timeline_media(project_id)
            return await asyncio.to_thread(run_resolve_helper, editing_resolve_payload(project_id))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except (OSError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/api/curation/projects/{project_id}/resolve/broll-timeline.dra")
    async def export_resolve_broll_timeline_dra(project_id: str):
        from .resolve_textplus_timeline import run_resolve_helper
        target = run_root(project_id) / "exports" / f"{load_project(project_id).name}-broll-v{uuid.uuid4().hex[:6]}.dra"
        try:
            await prepare_selected_timeline_media(project_id)
            payload = editing_resolve_payload(project_id)
            payload["dra_output_path"] = str(target)
            result = await asyncio.to_thread(run_resolve_helper, payload, timeout=300)
            exported = Path(str(result.get("dra_path") or ""))
            if not exported.is_file() or exported.stat().st_size <= 0:
                raise RuntimeError("Resolve reported success but created no DRA package")
            return FileResponse(exported, media_type="application/zip", filename=exported.name)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except (OSError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/api/curation/projects/{project_id}/resolve/combined-timeline")
    async def create_resolve_combined_timeline(project_id: str):
        from .resolve_textplus_timeline import run_resolve_helper
        try:
            return await asyncio.to_thread(run_resolve_helper, combined_resolve_payload(project_id))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except (OSError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/api/curation/projects/{project_id}/resolve/combined-timeline.drt")
    async def export_resolve_combined_timeline(project_id: str):
        from .resolve_textplus_timeline import run_resolve_helper
        target = run_root(project_id) / "exports" / f"rambla-words-subs-{project_id}-{uuid.uuid4().hex[:8]}.drt"
        try:
            payload = combined_resolve_payload(project_id)
            payload["drt_output_path"] = str(target)
            result = await asyncio.to_thread(run_resolve_helper, payload)
            exported = Path(str(result.get("drt_path") or target))
            if not exported.is_file() or exported.stat().st_size <= 0:
                raise RuntimeError("Resolve reported success but created no DRT file")
            return FileResponse(
                exported,
                media_type="application/octet-stream",
                filename=exported.name,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except (OSError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/api/curation/projects/{project_id}/beats/{beat_id}/split")
    async def preview_beat_split(project_id: str, beat_id: str):
        from .beat_split import split_preview
        try: return split_preview(run_root(project_id), beat_id)
        except ValueError as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/curation/projects/{project_id}/beats/{beat_id}/split")
    async def apply_beat_split(project_id: str, beat_id: str, request: BeatSplitRequest):
        from .beat_split import split_beat
        run = run_root(project_id)
        if _active_run_for(run): raise HTTPException(status_code=409, detail='Attendi la ricerca in corso')
        try: return split_beat(run, beat_id, request.cut, request.revision)
        except ValueError as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.put("/api/curation/projects/{project_id}/beats/{beat_id}/transcript")
    async def save_phrase_transcript(project_id: str, beat_id: str, request: PhraseCorrectionRequest):
        from .transcript_corrections import correct_phrase
        run=run_root(project_id)
        if _active_run_for(run):raise HTTPException(status_code=409,detail='Attendi la fine della ricerca in corso')
        try:return correct_phrase(run,beat_id,request.chunks,request.expected_text)
        except ValueError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc

    @app.post("/api/curation/projects/{project_id}/media/clean")
    async def clean_media_route(project_id: str) -> dict[str, Any]:
        run = run_root(project_id)
        if _active_run_for(run):
            raise HTTPException(status_code=409, detail="project stage already running")
        cleanup = clean_project_media(run, active_retrieval_root(run))
        return {"project_id": project_id, "cleanup": cleanup, "resolve_calls": 0}

    @app.post("/api/curation/projects/{project_id}/beats/{beat_id}/media/clean")
    async def clean_beat_media_route(project_id: str, beat_id: str) -> dict[str, Any]:
        run = run_root(project_id)
        if _active_run_for(run):
            raise HTTPException(status_code=409, detail="project stage already running")
        beats = _read_json(run / "visual-plan.json", {}).get("visual_beats", [])
        if not any(b.get("id")==beat_id and b.get("action")=="BROLL" for b in beats):
            raise HTTPException(status_code=404, detail="BROLL beat not found")
        return {"project_id": project_id, "cleanup": clean_beat_media(run, active_retrieval_root(run), beat_id)}

    @app.post("/api/curation/projects/{project_id}/source/social")
    async def source_project_social(project_id: str, request: SocialSearchRequest | None = None) -> dict[str, Any]:
        from .transcript_corrections import require_current_editorial
        try: require_current_editorial(run_root(project_id))
        except ValueError as exc: raise HTTPException(status_code=409,detail=str(exc)) from exc
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
        allowed_providers = {"youtube", "youtube_shorts", "tiktok", "instagram", "web_video", "pexels", "envato", "images"}
        if any(value not in allowed_providers for value in provider_scope):
            raise HTTPException(status_code=422, detail="unsupported research provider")
        _validate_broll_beat(run, beat_id)
        from .transcript_corrections import require_current_editorial
        try: require_current_editorial(run)
        except ValueError as exc: raise HTTPException(status_code=409,detail=str(exc)) from exc
        if project.source_video is None:
            raise HTTPException(status_code=422, detail="source video required")
        if _active_run_for(run):
            raise HTTPException(status_code=409, detail="project stage already running")
        stage = research_stage_type(beat_id, request.mode)
        if any(len(k)>150 or len(v)>180 or '\n' in v for k,v in request.query_overrides.items()):
            raise HTTPException(status_code=422,detail='Keywords must be short single-line queries')
        state = debug.RunState(
            uuid.uuid4().hex[:12], Path(project.source_video.path), run,
            guide_audio=Path(project.guide_audio.path) if project.guide_audio else None,
            analysis_signature=project.analysis_signature, stage_type=stage,
        )
        debug.RUNS[state.run_id] = state
        from .runtime_mode import uses_api_runtime
        cloud_mode = uses_api_runtime()
        state.research_options={
            'visual_verify': False if cloud_mode else request.visual_verify,
            'variation_round': request.variation_round,
            'query_overrides': request.query_overrides,
            'magic_exact_query': request.magic_exact_query,
        }
        asyncio.create_task(_run_research_state(state, beat_id, request.mode, provider_scope, research_runner))
        return {
            "status": "started",
            "run_id": state.run_id,
            "stage": stage,
            "providers": list(provider_scope),
            "resolve_calls": 0,
        }

    from .magic_store import MagicStore
    from .magic_runner import MagicRunner
    from .magic_product import MagicProductServices, source_signature
    from .magic_routes import install_magic_routes
    magic_store = MagicStore(root)

    async def magic_research(pid, beat, provider, query):
        from .magic_usage import check_current
        result = await research_beat_route(pid, beat, BeatResearchRequest(mode='append',
            providers=('images' if provider == 'google_images' else provider,),
            query_overrides={'*':query}, magic_exact_query=True))
        state = debug.RUNS[result['run_id']]
        try:
            while state.status in {'QUEUED','RUNNING'}:
                check_current()
                await asyncio.sleep(.25)
        except Exception:
            state.status = 'CANCELLED'
            if state.process:
                state.process.terminate()
            raise
        if state.status != 'SUCCEEDED':
            raise RuntimeError(state.last_message)
        retrieval = active_retrieval_root(run_root(pid))
        rows = _read_json(retrieval/'online-candidates.json', [])
        errors = [error for row in rows if str(row.get('beat_id') or '').split(':')[0] == beat
                  for error in row.get('errors', [])]
        if provider == 'google_images':
            images = _read_json(retrieval/'image-candidates.json', {})
            errors.extend((images.get('chunks', {}).get(beat) or {}).get('errors', []))
        return {'status':'complete', 'errors':errors}

    async def magic_prepare(pid, asset_ids, report):
        return await prepare_selected_timeline_media(pid, report=report, asset_ids=asset_ids)

    async def magic_deliver(pid, payload, run_id, report):
        from .atomic_io import write_json
        from .magic_usage import check_current
        journal = magic_store._path(run_id).with_name('delivery.json')
        if not active_bridge_session_id or time.time()-bridge_last_seen > 6:
            return {'awaiting_bridge':True, 'received':False}
        old = _read_json(journal, {})
        session = active_bridge_session_id
        if old.get('bridge_session_id') == session:
            package = handoff_store.read(root/pid, old['package_id'])
        else:
            package = handoff_store.prepare(root/pid, {**payload, 'project_id':pid, 'bridge_session_id':session})
            write_json(journal, {'package_id':package['package_id'],'bridge_session_id':session})
        report(0,1,'Pacchetto salvato · attendo conferma di ricezione dal bridge')
        deadline = time.monotonic()+8
        while not package.get('bridge_received_at') and time.monotonic() < deadline:
            check_current()
            await asyncio.sleep(.25)
            package = handoff_store.read(root/pid, package['package_id'])
        received = bool(package.get('bridge_received_at'))
        report(int(received),1,'Ricevuto dal bridge · premi APPLICA in Resolve' if received else 'Pacchetto pronto · il bridge non ha ancora confermato la ricezione')
        return {'package_id':package['package_id'],'received':received,'awaiting_bridge':not received}

    magic_services = MagicProductServices(store, root, magic_store, cut_engine, magic_research, magic_prepare,
        lambda pid:editing_resolve_payload(pid, {'video':True,'subtitles':True,'highlights':True,'broll':True,'social':True,'generic':False}), magic_deliver,
        generics=lambda pid,limit:generic_coverage(pid,scope='places',max_queries=limit))
    magic_runner = MagicRunner(magic_store, magic_services, lambda pid:source_signature(store,root,pid))
    magic_services.check = magic_runner.check
    install_magic_routes(app, magic_runner, load_project)
    return app


app = create_app()
