from __future__ import annotations

import asyncio
import json
import os
import shlex
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict

from .curation_artifacts import load_curation_run
from .curation_project import CurationProject, ProjectStore
from .curation_selection import SelectionStore
from .curation_ui import render_curation_page
from .project_config import load_project_credentials,provider_status
from .editorial_import import transcript_package, validate_import, import_plan, load_import, active_retrieval_root, contract_schema, parse_plan
from .project_lock import project_stage_lock
from .atomic_io import write_json

DEFAULT_VIDEO = r"Z:\APP REEL TEST\VIDEO BASE\KURA_Finto etico_draft 1.mp4"
DEFAULT_OUTPUT = r"Z:\APP REEL TEST\qwen-embedding-smoke\kura-finto-etico-smoke\run"
DEFAULT_PROFILE = r"Z:\APP REEL TEST\qwen-embedding-smoke\debug-runner-command.json"
STAGES = (
    ("prepare", "Preparazione", 3.0),
    ("asr", "ASR / trascrizione", 12.0),
    ("semantic_chunking", "Chunk semantici", 9.0),
    ("visual_planning", "Concrete visual planning", 8.0),
    ("image_search", "Ricerca immagini", 12.0),
    ("coverage", "CoveragePlanner", 7.0),
    ("evidence_intent", "EvidenceIntent", 8.0),
    ("source_strategy", "SourceStrategy", 7.0),
    ("online_search", "Ricerca online", 13.0),
    ("qwen_coarse", "Qwen coarse", 11.0),
    ("bounded_acquisition", "Acquisizione bounded", 8.0),
    ("qwen_final", "Qwen final", 10.0),
    ("edit_plan", "Edit Plan", 7.0),
    ("review", "Review HTML", 5.0),
)
WEIGHTS = {key: weight for key, _, weight in STAGES}
WINDOWS = os.name == "nt"


@dataclass(slots=True, frozen=True)
class DebugEvent:
    stage: str
    message: str
    progress: float | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"stage": self.stage, "message": self.message, "progress": self.progress, "data": self.data}


def parse_worker_line(line: str) -> DebugEvent:
    text = line.rstrip("\r\n")
    if text.startswith("RAMBLA_EVENT "):
        try:
            payload = json.loads(text[13:])
            progress = payload.get("progress")
            progress = None if progress is None else max(0.0, min(100.0, float(progress)))
            return DebugEvent(
                stage=str(payload.get("stage") or "log"),
                message=str(payload.get("message") or payload.get("stage") or "event"),
                progress=progress,
                data=payload.get("data") if isinstance(payload.get("data"), dict) else {},
            )
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return DebugEvent("log", text)


def suppress_worker_log_line(line: str) -> bool:
    text = line.strip()
    return text.rstrip(".") == "Deprecated Feature: Support for Python version 3.10 has been deprecated. Please update to Python 3.11 or above"


class ArtifactProgressTracker:
    ARTIFACTS = (
        ("asr", ("transcript-raw.json", "transcript.json"), "Trascrizione pronta"),
        ("semantic_chunking", ("semantic-chunks.json", "semantic-beats.json"), "Chunk semantici pronti"),
        ("visual_planning", ("visual-plan.json",), "Concrete visual plan pronto"),
        ("coverage", ("coverage-metrics.json",), "Coverage planning disponibile"),
        ("online_search", ("online-candidates.json", "candidate-metrics.json"), "Candidati online disponibili"),
        ("edit_plan", ("edit-plan.json",), "Edit Plan scritto"),
        ("review", ("review.html",), "Review HTML pronta"),
    )

    def __init__(self, output_dir: Path, *, ignore_existing: bool = False):
        self.output_dir = output_dir
        self.seen: set[str] = set()
        if ignore_existing:
            self.seen = {
                stage for stage, names, _message in self.ARTIFACTS
                if any((self.output_dir / name).exists() for name in names)
            }

    def scan(self) -> list[DebugEvent]:
        out: list[DebugEvent] = []
        for stage, names, message in self.ARTIFACTS:
            if stage not in self.seen and any((self.output_dir / name).exists() for name in names):
                self.seen.add(stage)
                out.append(DebugEvent(stage, message, 100.0))
        return out


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    video_path: str = DEFAULT_VIDEO
    output_dir: str = DEFAULT_OUTPUT


class CurationSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selections: dict[str, str]


class ProjectCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = "New Reel"


class LocalSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str


class TextSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str


class ProjectSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_ids: list[str] = []
    no_broll: bool = False


class WorkspaceSessionRequest(BaseModel):
    project_id: str
    active_chunk_id: str | None = None


@dataclass(slots=True)
class RunState:
    run_id: str
    video_path: Path
    output_dir: Path
    status: str = "QUEUED"
    return_code: int | None = None
    progress: dict[str, float] = field(default_factory=dict)
    last_message: str = "In attesa"
    events: list[DebugEvent] = field(default_factory=list)
    subscribers: list[asyncio.Queue[DebugEvent]] = field(default_factory=list)
    process: Any = None
    guide_audio: Path | None = None
    analysis_signature: str = ""
    stage_type: str = "all"
    research_options: dict[str, Any] = field(default_factory=dict)

    def total(self) -> float:
        scopes = {
            "analyze": {"prepare", "asr", "semantic_chunking", "analysis"},
            "videos": {"prepare", "visual_planning", "coverage", "evidence_intent", "source_strategy", "online_search", "qwen_coarse", "bounded_acquisition", "qwen_final", "edit_plan", "review"},
            "images": {"prepare", "visual_planning", "image_search"},
            "director_api": {"visual_planning"},
        }
        keys = scopes.get(self.stage_type, set(WEIGHTS))
        total_weight = sum(WEIGHTS.get(key, 0) for key in keys)
        done = sum(WEIGHTS.get(key, 0) * self.progress.get(key, 0.0) / 100.0 for key in keys)
        return round(done * 100.0 / total_weight, 2) if total_weight else 0.0

    def snapshot(self) -> dict[str, Any]:
        asr_started = any(event.stage == "asr" for event in self.events)
        transcript_status = None
        transcript_message = None
        if self.stage_type == "analyze":
            transcript_status = "active" if asr_started else "failed" if self.status == "FAILED" else "waiting"
            transcript_message = self.last_message if transcript_status == "failed" else None
        return {
            "run_id": self.run_id,
            "video_path": str(self.video_path),
            "output_dir": str(self.output_dir),
            "status": self.status,
            "return_code": self.return_code,
            "stage_progress": self.progress,
            "total_progress": 100.0 if self.status == "SUCCEEDED" else self.total(),
            "stage_type": self.stage_type,
            "last_message": self.last_message,
            "events": [event.as_dict() for event in self.events[-30:]],
            "transcript_status": transcript_status,
            "transcript_message": transcript_message,
            "review_path": str(self.output_dir / "review.html"),
            "edit_plan_path": str(self.output_dir / "edit-plan.json"),
        }


RUNS: dict[str, RunState] = {}


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _curation_payload(output_dir: Path) -> dict[str, Any]:
    chunks = _read_json(output_dir / "semantic-chunks.json", [])
    online = _read_json(output_dir / "online-candidates.json", [])
    image_data = _read_json(output_dir / "image-candidates.json", {"chunks": {}})
    selected = _read_json(output_dir / "curation-selection.json", {"selections": {}}).get("selections", {})
    by_chunk: dict[str, list[dict[str, Any]]] = {}
    for slot in online if isinstance(online, list) else []:
        parent = str(slot.get("parent_beat_id") or str(slot.get("beat_id", "")).split(":", 1)[0])
        for row in slot.get("candidates", [])[:3]:
            preview = row.get("preview_path") or row.get("path")
            by_chunk.setdefault(parent, []).append({
                "asset_id": str(row.get("id")), "chunk_id": parent, "kind": "video",
                "provider": str(row.get("source") or "online"), "title": str(row.get("description") or row.get("id")),
                "rights_state": str(row.get("rights_state") or "review_required"), "orientation": str(row.get("orientation") or "unknown"),
                "preview_path": str(preview) if preview else None,
            })
    for chunk_id, details in image_data.get("chunks", {}).items() if isinstance(image_data, dict) else []:
        for row in details.get("candidates", [])[:4]:
            by_chunk.setdefault(chunk_id, []).append({"asset_id": f"{row.get('provider')}:{row.get('provider_id')}", "chunk_id": chunk_id, "kind": "image", "provider": row.get("provider"), "title": row.get("title"), "rights_state": row.get("rights_state"), "orientation": row.get("orientation"), "preview_path": None})
    result = []
    for chunk in chunks if isinstance(chunks, list) else []:
        cid = str(chunk.get("id"))
        assets = by_chunk.get(cid, [])
        for asset in assets:
            path = asset.pop("preview_path", None)
            asset["preview_url"] = f"/api/curation/run/default/media/{asset['asset_id']}/preview" if path and Path(path).is_file() else None
        result.append({"id": cid, "text": chunk.get("text", ""), "assets": assets[:7]})
    return {"chunks": result, "selections": selected, "resolve_calls": 0}


def _selection_path(output_dir: Path) -> Path:
    return output_dir / "curation-selection.json"


def _candidate_can_be_selected(item: Any) -> bool:
    """A surfaced provider source is an editorial choice even before download.

    Clip verification remains visible as a separate truth state; it must not
    prevent the editor from saving a discovery-only Pexels/Envato/social card.
    """
    if getattr(item, "kind", None) != "video":
        return True
    if getattr(item, "preview_status", None) == "ready" and bool(getattr(item, "clip_verified", False)):
        return True
    source = str(getattr(item, "source_page", "") or "").strip()
    return source.startswith(("https://", "http://"))


def _write_selection(output_dir: Path, selections: dict[str, str]) -> None:
    target = _selection_path(output_dir)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps({"schema_version": "curation-selection-0.1", "selections": selections}, indent=2), encoding="utf-8")
    temporary.replace(target)


def _command(state: RunState) -> list[str]:
    from .runtime_mode import uses_api_runtime
    if uses_api_runtime():
        module = "backend.app.cloud_analyze_cli" if state.stage_type == "analyze" else "backend.app.debug_run_cli"
        command = [
            sys.executable, "-m", module,
            "--video", str(state.video_path),
            "--output-dir", str(state.output_dir),
            "--stage", state.stage_type,
        ]
        if state.guide_audio:
            command.extend(["--guide-audio", str(state.guide_audio)])
        if state.analysis_signature:
            command.extend(["--analysis-signature", state.analysis_signature])
        if module == "backend.app.debug_run_cli":
            command.extend(["--model-cache", str(state.output_dir / ".cloud-model-cache")])
        return command
    raw = os.environ.get("RAMBLA_DEBUG_COMMAND_JSON", "").strip()
    if raw:
        try:
            payload: Any = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("RAMBLA_DEBUG_COMMAND_JSON non valido") from exc
    else:
        profile = Path(os.environ.get("RAMBLA_DEBUG_COMMAND_FILE", DEFAULT_PROFILE))
        if not profile.is_file():
            raise RuntimeError(f"profilo comando mancante: {profile}")
        try:
            payload = json.loads(profile.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"profilo comando non valido: {profile}") from exc
        if isinstance(payload, dict):
            payload = payload.get("command")
    if not isinstance(payload, list) or not payload or not all(isinstance(x, str) for x in payload):
        raise RuntimeError("il profilo deve contenere un array command di stringhe")
    values = {"video": str(state.video_path), "output": str(state.output_dir), "guide": str(state.guide_audio or state.video_path), "analysis_signature": state.analysis_signature}
    command = [item.format_map(values) for item in payload]
    if state.guide_audio and "--guide-audio" not in command:
        command.extend(["--guide-audio", str(state.guide_audio)])
    if state.analysis_signature and "--analysis-signature" not in command:
        command.extend(["--analysis-signature", state.analysis_signature])
    if state.stage_type and "--stage" not in command:
        command.extend(["--stage", state.stage_type])
    if 'backend.app.debug_run_cli' in command and os.environ.get("RAMBLA_ASR_PYTHON"):
        command[0] = os.environ["RAMBLA_ASR_PYTHON"]
    return command


async def _emit(state: RunState, event: DebugEvent) -> None:
    state.events.append(event)
    state.last_message = event.message
    if event.stage in WEIGHTS and event.progress is not None:
        state.progress[event.stage] = max(state.progress.get(event.stage, 0.0), event.progress)
    for queue in list(state.subscribers):
        await queue.put(event)


class _AsyncioWorker:
    spawn_mode = "asyncio"

    def __init__(self, process: Any):
        self.process = process

    @property
    def returncode(self) -> int | None:
        return self.process.returncode

    async def readline(self) -> bytes:
        assert self.process.stdout is not None
        return await self.process.stdout.readline()

    async def wait(self) -> int:
        return await self.process.wait()

    def terminate(self) -> None:
        self.process.terminate()

    def kill(self) -> None:
        self.process.kill()


class _PopenWorker:
    spawn_mode = "popen-thread"

    def __init__(self, process: subprocess.Popen[bytes]):
        self.process = process

    @property
    def returncode(self) -> int | None:
        return self.process.poll()

    async def readline(self) -> bytes:
        assert self.process.stdout is not None
        return await asyncio.to_thread(self.process.stdout.readline)

    async def wait(self) -> int:
        try:
            return await asyncio.to_thread(self.process.wait)
        finally:
            if self.process.stdout is not None and not self.process.stdout.closed:
                self.process.stdout.close()

    def terminate(self) -> None:
        self.process.terminate()

    def kill(self) -> None:
        self.process.kill()


def _readable_file(label: str, path: Path) -> None:
    if not path.is_file():
        raise RuntimeError(f"Worker preflight failed: {label} is not a file: {path}")
    try:
        with path.open("rb") as stream:
            stream.read(1)
    except OSError as exc:
        raise RuntimeError(f"Worker preflight failed: {label} is not readable: {path}: {exc}") from exc


def _preflight_worker(state: RunState, command: list[str], cwd: Path) -> dict[str, str]:
    executable_text = command[0]
    located = shutil.which(executable_text) if not Path(executable_text).is_absolute() else executable_text
    executable = Path(located) if located else Path(executable_text)
    _readable_file("executable", executable)
    if not cwd.is_dir():
        raise RuntimeError(f"Worker preflight failed: cwd is not a directory: {cwd}")
    try:
        next(cwd.iterdir(), None)
    except OSError as exc:
        raise RuntimeError(f"Worker preflight failed: cwd is not readable: {cwd}: {exc}") from exc
    _readable_file("source", state.video_path)
    _readable_file("guide", state.guide_audio or state.video_path)
    try:
        state.output_dir.mkdir(parents=True, exist_ok=True)
        probe = state.output_dir / f".worker-write-probe-{uuid.uuid4().hex}.tmp"
        try:
            with probe.open("xb") as stream:
                stream.write(b"ok")
        finally:
            if probe.exists():
                probe.unlink()
    except OSError as exc:
        raise RuntimeError(f"Worker preflight failed: output is not writable: {state.output_dir}: {exc}") from exc
    return {"executable": str(executable), "cwd": str(cwd), "source": str(state.video_path), "guide": str(state.guide_audio or state.video_path), "output": str(state.output_dir)}


async def _spawn_worker(command: list[str], cwd: Path) -> Any:
    try:
        return _AsyncioWorker(await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(cwd),
        ))
    except PermissionError as exc:
        if not WINDOWS or getattr(exc, "winerror", None) != 5:
            raise
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(cwd),
        )
        return _PopenWorker(process)


async def _stop_worker(process: Any) -> None:
    if process.returncode is not None:
        return
    if WINDOWS:
        # Windows .terminate() stops only the parent Python process. Its
        # ffmpeg/yt-dlp subprocesses can otherwise keep CPU saturated.
        pid = getattr(getattr(process, "process", None), "pid", None)
        if pid:
            try:
                result = await asyncio.to_thread(
                    subprocess.run, ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True, timeout=10, check=False,
                )
                if result.returncode == 0:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                    return
            except (OSError, subprocess.SubprocessError, asyncio.TimeoutError):
                pass
    process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=3.0)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()


async def _run(state: RunState) -> None:
    state.status = "RUNNING"
    try:
        command = _command(state)
        cwd = Path.cwd()
        preflight = _preflight_worker(state, command, cwd)
        tracker = ArtifactProgressTracker(state.output_dir, ignore_existing=True)
        await _emit(state, DebugEvent("prepare", "Run avviata", 100.0))
        await _emit(state, DebugEvent("preflight", "Worker preflight completato", 100.0, preflight))
        await _emit(state, DebugEvent("log", "Comando: " + " ".join(shlex.quote(x) for x in command)))
        process = await _spawn_worker(command, cwd)
        state.process = process
        await _emit(state, DebugEvent("worker", "Worker avviato", data={"spawn_mode": process.spawn_mode}))

        async def watch() -> None:
            while process.returncode is None:
                for event in tracker.scan():
                    await _emit(state, event)
                await asyncio.sleep(0.35)

        watcher = asyncio.create_task(watch())
        while True:
            line = await process.readline()
            if not line:
                break
            decoded = line.decode("utf-8", errors="replace")
            if not suppress_worker_log_line(decoded):
                await _emit(state, parse_worker_line(decoded))
        state.return_code = await process.wait()
        watcher.cancel()
        try:
            await watcher
        except asyncio.CancelledError:
            pass
        for event in tracker.scan():
            await _emit(state, event)
        if state.status != "CANCELLED":
            state.status = "SUCCEEDED" if state.return_code == 0 else "FAILED"
        await _emit(state, DebugEvent("review" if state.status == "SUCCEEDED" else "error", state.status, 100.0 if state.status == "SUCCEEDED" and (state.output_dir / "review.html").exists() else None, state.snapshot()))
    except Exception as exc:
        state.status = "FAILED"
        await _emit(state, DebugEvent("error", str(exc), data=state.snapshot()))
    finally:
        if state.process is not None and state.process.returncode is None:
            await _stop_worker(state.process)
        state.process = None


def _metrics(state: RunState) -> dict[str, Any]:
    result = {"certified_ab_pairs": None, "no_broll_count": None, "downloaded_bytes": None, "total_seconds": None}
    for name in ("online-sourcing-benchmark.json", "coverage-metrics.json", "candidate-metrics.json"):
        path = state.output_dir / name
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        result["certified_ab_pairs"] = result["certified_ab_pairs"] if result["certified_ab_pairs"] is not None else data.get("certified_ab_pairs", data.get("slots_with_2plus_proposals"))
        result["no_broll_count"] = result["no_broll_count"] if result["no_broll_count"] is not None else data.get("no_broll_count", data.get("quality_floor_no_broll_count"))
        result["downloaded_bytes"] = result["downloaded_bytes"] if result["downloaded_bytes"] is not None else data.get("downloaded_bytes")
        result["total_seconds"] = result["total_seconds"] if result["total_seconds"] is not None else data.get("total_seconds")
    return result


def render_debug_page(default_video: str = DEFAULT_VIDEO, default_output: str = DEFAULT_OUTPUT) -> str:
    stages = json.dumps([{"id": key, "label": label} for key, label, _ in STAGES], ensure_ascii=False)
    video = json.dumps(default_video, ensure_ascii=False)
    output = json.dumps(default_output, ensure_ascii=False)
    return f'''<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RAMBLA Debug Runner</title><style>
:root{{--bg:#0b0c0f;--card:#15171c;--line:#2a2e36;--text:#f3f4f6;--muted:#969daa;--accent:#d9ff5a;--good:#79e39c;--bad:#ff7d7d}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font-family:Inter,system-ui,sans-serif}}main{{max-width:1250px;margin:auto;padding:24px}}h1{{margin:0 0 4px;font-size:25px}}.muted{{color:var(--muted);font-size:13px}}.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:15px;margin-top:13px}}.row{{display:flex;gap:10px;align-items:end;flex-wrap:wrap}}.grow{{flex:1;min-width:300px}}label{{display:block;color:var(--muted);font-size:12px;margin-bottom:5px}}input{{width:100%;background:#0d0f13;color:white;border:1px solid #343a44;border-radius:8px;padding:10px;font-family:ui-monospace,monospace}}button{{background:var(--accent);color:#111;border:0;border-radius:8px;padding:11px 18px;font-weight:800;cursor:pointer}}button:disabled{{opacity:.4}}.total,.bar{{background:#242832;border-radius:99px;overflow:hidden}}.total{{height:14px;margin:8px 0}}.bar{{height:7px;margin-top:8px}}.fill{{height:100%;width:0;background:#8992a2;transition:width .2s}}.stage.done .fill{{background:var(--good)}}.stages{{display:grid;grid-template-columns:repeat(auto-fit,minmax(235px,1fr));gap:8px}}.stage{{background:#101217;border:1px solid var(--line);border-radius:9px;padding:10px}}.head{{display:flex;justify-content:space-between;gap:8px;font-size:13px}}.split{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}@media(max-width:900px){{.split{{grid-template-columns:1fr}}}}pre,#events{{height:320px;overflow:auto;background:#08090b;border-radius:9px;padding:10px;margin:0;font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere}}.event{{border-bottom:1px solid #22262b;padding:8px 3px}}.event b{{color:var(--accent)}}.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(135px,1fr));gap:8px}}.metric{{background:#101217;border-radius:8px;padding:9px}}.metric b{{display:block;font-size:18px;margin-top:3px}}.good{{color:var(--good)}}.bad{{color:var(--bad)}}
</style></head><body><main><div class="row" style="justify-content:space-between"><div><h1>RAMBLA Debug Runner</h1><div class="muted">Debug visivo live · Resolve calls = 0</div></div><b id="status" class="muted">PRONTO</b></div>
<div class="card row"><div class="grow"><label>Video</label><input id="video"></div><div class="grow"><label>Output</label><input id="out"></div><button id="run">ESEGUI</button><button id="stop" disabled>STOP</button></div>
<div class="card"><div class="head"><b>Barra totale</b><span id="totalText">0%</span></div><div class="total"><div id="total" class="fill"></div></div><div id="msg" class="muted">In attesa.</div></div>
<div class="card"><div id="stages" class="stages"></div></div>
<div class="card metrics"><div class="metric"><span class="muted">Run</span><b id="rid">—</b></div><div class="metric"><span class="muted">A/B certificate</span><b id="ab">—</b></div><div class="metric"><span class="muted">NO_BROLL</span><b id="nb">—</b></div><div class="metric"><span class="muted">Download bytes</span><b id="bytes">—</b></div><div class="metric"><span class="muted">Tempo</span><b id="secs">—</b></div></div>
<div class="card split"><div><div class="muted" style="margin-bottom:6px">Log live</div><pre id="log"></pre></div><div><div class="muted" style="margin-bottom:6px">Eventi / dati</div><div id="events"></div></div></div>
<div class="card muted" id="links">Gli output appariranno qui a fine run.</div>
<script>const DEF_VIDEO={video},DEF_OUT={output},STAGES={stages};const nodes={{}};let es=null,activeRunId=null;const $=id=>document.getElementById(id);$('video').value=DEF_VIDEO;$('out').value=DEF_OUT;function esc(v){{return String(v??'').replace(/[&<>\"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]))}}function init(){{$('stages').innerHTML='';STAGES.forEach(s=>{{const n=document.createElement('div');n.className='stage';n.innerHTML=`<div class="head"><b>${{esc(s.label)}}</b><span>0%</span></div><div class="bar"><div class="fill"></div></div>`;$('stages').appendChild(n);nodes[s.id]=n}})}}function setStage(k,v){{const n=nodes[k];if(!n)return;v=Math.max(0,Math.min(100,Number(v)||0));n.querySelector('span').textContent=v.toFixed(0)+'%';n.querySelector('.fill').style.width=v+'%';n.classList.toggle('done',v>=100)}}function snap(s){{$('rid').textContent=s.run_id||'—';$('totalText').textContent=(s.total_progress||0).toFixed(1)+'%';$('total').style.width=(s.total_progress||0)+'%';$('msg').textContent=s.last_message||'';Object.entries(s.stage_progress||{{}}).forEach(([k,v])=>setStage(k,v))}}async function metrics(id){{try{{const m=await (await fetch(`/v1/debug/runs/${{id}}/metrics`)).json();$('ab').textContent=m.certified_ab_pairs??'—';$('nb').textContent=m.no_broll_count??'—';$('bytes').textContent=m.downloaded_bytes??'—';$('secs').textContent=m.total_seconds==null?'—':m.total_seconds+'s'}}catch(_){{}}}}function ev(e){{const d=document.createElement('div');d.className='event';d.innerHTML=`<b>${{esc(e.stage)}}</b> · ${{esc(e.message)}}`;if(e.data&&Object.keys(e.data).length)d.innerHTML+=`<pre style="height:auto;margin-top:6px">${{esc(JSON.stringify(e.data,null,2))}}</pre>`;$('events').prepend(d);$('log').textContent+=`[${{e.stage}}] ${{e.message}}\n`;$('log').scrollTop=$('log').scrollHeight;if(e.progress!=null)setStage(e.stage,e.progress)}}async function run(){{if(es)es.close();$('run').disabled=true;$('log').textContent='';$('events').innerHTML='';init();$('status').textContent='AVVIO…';try{{const r=await fetch('/v1/debug/runs',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{video_path:$('video').value,output_dir:$('out').value}})}});const s=await r.json();if(!r.ok)throw new Error(s.detail||JSON.stringify(s));snap(s);activeRunId=s.run_id;$('stop').disabled=false;es=new EventSource(`/v1/debug/runs/${{s.run_id}}/events`);es.onmessage=async x=>{{const e=JSON.parse(x.data);if(e.stage==='snapshot'){{snap(e.data);await metrics(e.data.run_id);if(['SUCCEEDED','FAILED','CANCELLED'].includes(e.data.status)){{$('status').textContent=e.data.status;$('status').className=e.data.status==='SUCCEEDED'?'good':'bad';$('run').disabled=false;$('stop').disabled=true;if(e.data.status==='SUCCEEDED')$('links').innerHTML=`Review: <code>${{esc(e.data.review_path)}}</code><br>Edit Plan: <code>${{esc(e.data.edit_plan_path)}}</code>`}}}}else ev(e)}}}}catch(e){{$('status').textContent='ERRORE';$('status').className='bad';$('log').textContent+=String(e);$('run').disabled=false;$('stop').disabled=true}}}}$('stop').onclick=async()=>{{if(!activeRunId)return;await fetch(`/v1/debug/runs/${{activeRunId}}/cancel`,{{method:'POST'}})}};$('run').onclick=run;init();</script></main></body></html>'''


def _project_payload(project: CurationProject) -> dict[str, Any]:
    source_name = Path(project.source_video.path).name if project.source_video else ""
    source_kind = "text" if source_name == "text-timeline.mp4" else "audio" if source_name == "audio-timeline.mp4" else "video"
    return {
        "project_id": project.project_id,
        "name": project.name,
        "source_kind": source_kind,
        "source_video": None if project.source_video is None else {
            "path": project.source_video.path,
            "duration": project.source_video.duration,
            "fps": project.source_video.fps,
            "width": project.source_video.width,
            "height": project.source_video.height,
            "has_audio": project.source_video.has_audio,
        },
        "guide_audio": None if project.guide_audio is None else {
            "path": project.guide_audio.path, "mode": project.guide_audio.mode,
            "signature": project.guide_audio.signature,
            "duration": project.guide_audio.duration,
        },
        "analysis_signature": project.analysis_signature,
        "timeline_duration": project.source_video.duration if project.source_video else None,
        "guide_duration_warning": project.guide_duration_warning,
        "resolve_calls": 0,
    }


def _probe_source_video(source: Path) -> dict[str, Any]:
    """Probe local source metadata without starting analysis providers."""
    import subprocess

    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,r_frame_rate,width,height", "-of", "json", str(source)],
        check=True, capture_output=True, text=True,
    )
    payload = json.loads(result.stdout)
    streams = payload.get("streams", [])
    video = next(stream for stream in streams if stream.get("codec_type") == "video")
    numerator, denominator = str(video.get("r_frame_rate", "0/1")).split("/", 1)
    return {
        "duration": float(payload.get("format", {}).get("duration", 0)),
        "fps": float(numerator) / float(denominator or 1),
        "width": int(video.get("width", 0)),
        "height": int(video.get("height", 0)),
        "has_audio": any(stream.get("codec_type") == "audio" for stream in streams),
    }


def create_app(*, project_root: Path | None = None, curation_run_root: Path | None = None, allowed_media_roots: list[Path] | None = None, probe_runner: Any = None, audio_probe_runner: Any = None, audio_command_runner: Any = None) -> FastAPI:
    load_project_credentials()
    from .runtime_mode import uses_api_runtime
    if uses_api_runtime():
        os.environ.setdefault("RAMBLA_RETRIEVAL_RANKING", "provider")
    app = FastAPI(title="RAMBLA Debug Runner", version="0.1.0")
    project_root = project_root or Path(os.environ.get("RAMBLA_PROJECT_ROOT", str(Path(DEFAULT_OUTPUT).parent / "curation-projects")))
    # Legacy/default artifacts are deliberately never used by project routes.
    # Each project's analysis, media index, and selections live under its own root.
    allowed_roots = tuple(root.resolve() for root in (allowed_media_roots or [Path(DEFAULT_VIDEO).parent, project_root]))
    projects = ProjectStore(project_root, probe_runner=probe_runner or _probe_source_video, audio_probe_runner=audio_probe_runner)
    guide_command_runner = audio_command_runner or subprocess.run

    def select_default_guide(project: CurationProject) -> CurationProject:
        if project.source_video and project.source_video.has_audio:
            projects.extract_source_audio(project.project_id, command_runner=guide_command_runner)
            return projects.load(project.project_id)
        return project
    project_runs: dict[str, str] = {}

    def load_project(project_id: str) -> CurationProject:
        try:
            return projects.load(project_id)
        except (FileNotFoundError, ValueError):
            raise HTTPException(status_code=404, detail="project non trovato") from None

    def allowed_source(path: Path) -> Path:
        resolved = path.resolve()
        try:
            next(root for root in allowed_roots if resolved.is_relative_to(root))
        except StopIteration:
            raise HTTPException(status_code=403, detail="source fuori dalle root autorizzate") from None
        return resolved

    workspace_session_path = project_root.parent / "workspace-session.json"

    def workspace_session() -> dict[str, Any]:
        saved = _read_json(workspace_session_path, {})
        project_id = str(saved.get("project_id") or "")
        try:
            if project_id:
                projects.load(project_id)
                return saved
        except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError):
            pass
        recent = projects.list_recent(limit=1)
        return {
            "project_id": str(recent[0].get("project_id") or "") if recent else None,
            "active_chunk_id": None,
            "updated_at": None,
        }

    @app.get("/api/curation/workspace-session")
    async def get_workspace_session() -> dict[str, Any]:
        return workspace_session()

    @app.put("/api/curation/workspace-session")
    async def put_workspace_session(request: WorkspaceSessionRequest) -> dict[str, Any]:
        load_project(request.project_id)
        payload = {
            "project_id": request.project_id,
            "active_chunk_id": request.active_chunk_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        write_json(workspace_session_path, payload)
        return payload

    def project_run_root(project_id: str) -> Path:
        load_project(project_id)
        return project_root / project_id / "run"

    def project_run(project_id: str) -> Any:
        try:
            return load_curation_run(project_run_root(project_id))
        except (OSError, ValueError, json.JSONDecodeError):
            raise HTTPException(status_code=404, detail="artifact di curation non disponibile") from None

    def project_selection_store(project_id: str) -> SelectionStore:
        run = project_run(project_id)
        return SelectionStore(
            active_retrieval_root(project_run_root(project_id)),
            {asset_id: {"chunk_id": item.chunk_id,"selectable":_candidate_can_be_selected(item)} for asset_id, item in run.candidate_index.items()},
            [item.chunk_id for item in run.chunks],
        )

    def editorial_input(project_id: str) -> dict:
        project = load_project(project_id)
        root = project_run_root(project_id)
        from .analysis_reuse import ensure_analysis_ready
        if not ensure_analysis_ready(root,project):
            raise HTTPException(status_code=422, detail='Analyze this source/guide before exporting or sourcing')
        try:
            return transcript_package(root, project_id, project.source_video.duration)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=422, detail='Editorial input unavailable: '+str(exc)) from exc

    def approved_plan(project_id: str) -> dict:
        package = editorial_input(project_id)
        try:
            return validate_import(load_import(project_run_root(project_id)), package)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=422, detail='Import a valid editorial plan before sourcing: '+str(exc)) from exc

    @app.get('/api/curation/editorial-plan/schema')
    async def editorial_schema() -> dict:
        return contract_schema()

    @app.get('/api/curation/projects/{project_id}/editorial-input')
    async def export_editorial_input(project_id: str) -> dict:
        return editorial_input(project_id)

    @app.post('/api/curation/projects/{project_id}/editorial-plan')
    async def receive_editorial_plan(project_id: str, request: Request) -> dict:
        active = RUNS.get(project_runs.get(project_id, ''))
        if active and active.status in {'QUEUED','RUNNING'}:
            raise HTTPException(status_code=409, detail='Wait for the running project stage before importing')
        raw = await request.body()
        if len(raw)>2_000_000:
            raise HTTPException(status_code=413, detail='Editorial JSON exceeds 2 MB')
        try:
            plan = parse_plan(raw)
            with project_stage_lock(project_run_root(project_id)):
                root = import_plan(project_run_root(project_id), plan, editorial_input(project_id))
            return {'status':'imported','visual_beats':len(plan['visual_beats']),'plan_version':root.name,'resolve_calls':0}
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    def curation_payload(project_id: str) -> dict[str, Any]:
        analysis_ready = False
        editorial_plan = None
        editorial_error = None
        try:
            editorial_input(project_id)
            analysis_ready = True
            editorial_plan = approved_plan(project_id)
        except HTTPException as exc:
            editorial_error = exc.detail
        from .animation_context import build_animation_context
        from .transcript_corrections import needs_editorial_refresh
        flags = {'transcript_needs_plan':needs_editorial_refresh(project_run_root(project_id)), 'animation_context':build_animation_context({**editorial_plan,'global_topic':''} if editorial_plan and needs_editorial_refresh(project_run_root(project_id)) else editorial_plan), 'provider_status':provider_status(),'analysis_ready':analysis_ready,'editorial_plan_ready':editorial_plan is not None,'editorial_error':editorial_error}
        def transcript_rows() -> list[dict[str, Any]]:
            if not analysis_ready:
                return []
            rows = _read_json(project_run_root(project_id)/'semantic-chunks.json', [])
            return [
                {"id": str(row.get("id")), "start": row.get("start", row.get("start_seconds")),
                 "end": row.get("end", row.get("end_seconds")), "text": row.get("text", ""),
                 "action": "TRANSCRIPT", "covered_chunk_ids": [str(row.get("id"))],
                 "assets": [], "retrieval_diagnostics": {}}
                for row in rows if isinstance(row, dict) and row.get("id") is not None
            ]
        existing = _read_json(project_run_root(project_id)/'visual-plan.json',{})
        if not editorial_plan and existing.get('schema_version')=='rambla-visual-plan-1':
            return {**flags,'project_id':project_id,'chunks':transcript_rows(),'selection_plan':{'chunks':{}},'resolve_calls':0}
        try:
            run = project_run(project_id)
        except HTTPException as exc:
            if exc.status_code == 404:
                return {**flags, "project_id": project_id, "chunks": transcript_rows(), "selection_plan": {"chunks": {}}, "resolve_calls": 0}
            raise
        saved = project_selection_store(project_id).load()
        from .transcript_intents import planning_chunks_for_coverage
        intent_segment_index = {
            str(segment.get("id")): {
                "id": str(segment.get("id")),
                "source_chunk_id": str(segment.get("source_chunk_id")),
                "source_word_start_index": int(segment.get("source_word_start_index", 0)),
                "source_word_end_index": int(segment.get("source_word_end_index", 0)),
            }
            for segment in planning_chunks_for_coverage(project_run_root(project_id))
            if isinstance(segment, dict) and segment.get("id") is not None
        }
        retrieval_root = active_retrieval_root(project_run_root(project_id))
        imported_beats = {b['id']:b for b in editorial_plan['visual_beats']} if editorial_plan else {}
        for bid, beat in imported_beats.items():
            if beat['action'] != 'BROLL':
                saved['chunks'].setdefault(bid, {'chunk_id':bid,'no_broll':beat['action']=='KEEP_TALKING_HEAD','selected_assets':[],'action':beat['action'],'continuation_from':beat.get('continuation_from')})
        diagnostics = _read_json(retrieval_root / "video-sourcing-diagnostics.json", {"chunks": []})
        video_diagnostics = {str(row.get("chunk_id")): row for row in diagnostics.get("chunks", [])}
        image_artifact = _read_json(retrieval_root / "image-candidates.json", {"chunks": {}})
        image_diagnostics = image_artifact.get("chunks", {}) if isinstance(image_artifact, dict) else {}
        from .retrieval_diagnostics import image_diagnostic,video_diagnostic
        video_rows=_read_json(retrieval_root/'online-candidates.json',[])
        from .live_retrieval_diagnostics import overlay_live_rows
        active_runs=[s for s in RUNS.values() if s.status in {'QUEUED','RUNNING'} and Path(s.output_dir).resolve()==project_run_root(project_id).resolve()]
        if active_runs:
            video_rows=overlay_live_rows(video_rows,[e.as_dict() for e in active_runs[-1].events])
        def media_diagnostics(cid):
            rows=[r for r in video_rows if r.get('parent_beat_id')==cid]
            image_row=image_diagnostics.get(cid,{})
            return {'social':video_diagnostic(rows,'youtube'),'stock':video_diagnostic(rows,'pexels',provider_status()['pexels_configured']),
                'image':image_diagnostic(image_row),'image_attempts':image_row.get('search_attempts',[]),
                'image_rejections':image_row.get('rejected_candidates',[]),
                'video_attempts':[a for r in rows for a in r.get('search_attempts',[])],
                'video_errors':[e for r in rows for e in r.get('errors',[])],
                'video_rejections':[a for r in rows for a in r.get('rejected_candidates',[])]}
        def research_round(cid):
            return max((int(row.get('research_round') or 0) for row in video_rows if row.get('parent_beat_id')==cid),default=0)
        visual_artifact = _read_json(project_run_root(project_id) / "visual-plan.json", {"chunks": {}})
        visual_plans = visual_artifact.get("chunks", {}) if isinstance(visual_artifact, dict) else {}
        visual_plans.update(imported_beats)
        def video_reason(chunk_id: str) -> str:
            if imported_beats.get(chunk_id,{}).get('action','BROLL')!='BROLL':
                return imported_beats[chunk_id]['action'].replace('_',' ')
            row = video_diagnostics.get(chunk_id, {})
            if row.get("errors"): return "provider error: " + str(row["errors"][0])
            if row.get("raw_results", 0) == 0: return "0 provider results"
            if row.get("rejected", 0): return "all rejected: " + ", ".join(row.get("rejection_reasons", []))
            return "preview failed"
        def image_reason(chunk_id: str) -> str:
            if imported_beats.get(chunk_id,{}).get('action','BROLL')!='BROLL':
                return imported_beats[chunk_id]['action'].replace('_',' ')
            row = image_diagnostics.get(chunk_id, {})
            return str(row.get("zero_result_reason") or "images not searched")
        return {
            **flags,
            "retrieval_warnings":list(run.errors),
            "project_id": project_id,
            "chunks": [{"id": row.chunk_id, "text": row.text,
                "start": imported_beats.get(row.chunk_id, {}).get('start'),
                "end": imported_beats.get(row.chunk_id, {}).get('end'),
                "covered_chunk_ids": imported_beats.get(row.chunk_id, {}).get('covered_chunk_ids', [row.chunk_id]),
                "intent_segments": [intent_segment_index[covered_id] for covered_id in imported_beats.get(row.chunk_id, {}).get('covered_chunk_ids', [row.chunk_id]) if covered_id in intent_segment_index],
                "action": imported_beats.get(row.chunk_id, {}).get('action'),
                "visual_plan": visual_plans.get(row.chunk_id),
                "error": any(item.preview_error for item in (*row.video_candidates, *row.image_candidates)),
                "video_reason": None if row.video_candidates else media_diagnostics(row.chunk_id)['social']['message'],
                "stock_reason":media_diagnostics(row.chunk_id)['stock']['message'],
                "image_reason": None if row.image_candidates else media_diagnostics(row.chunk_id)['image']['message'],
                "retrieval_diagnostics":media_diagnostics(row.chunk_id),
                "research_round":research_round(row.chunk_id),
                "assets": [
                {"asset_id": item.asset_id, "chunk_id": item.chunk_id, "kind": item.kind,
                 "provider": item.provider, "title": item.title, "rights_state": item.rights_state,
                 "orientation": item.orientation, "source_page":item.source_page, "preview_status":item.preview_status, "license_name":item.license_name,"license_url":item.license_url,"attribution":item.attribution,"shot_id":item.shot_id,"matched_query":item.matched_query,"score":item.score,"source_url":item.source_page,
                 "source_start_seconds":item.source_start_seconds,"source_end_seconds":item.source_end_seconds,
                 "quality_state":item.quality_state,"quality_reasons":list(item.quality_reasons),
                 "envato_full_ready": bool(item.provider == "envato" and item.local_asset_path and item.local_asset_path != item.preview_path and Path(item.local_asset_path).is_file()),
                 "selectable":_candidate_can_be_selected(item),
                 "download_url": f"/api/curation/projects/{project_id}/media/{item.asset_id}/download" if item.kind=="video" and item.preview_status=="ready" and item.clip_verified and item.preview_path and Path(item.preview_path).is_file() else None,
                 "preview_url": item.preview_url or f"/api/curation/projects/{project_id}/media/{item.asset_id}/preview",
                 "poster_url": f"/api/curation/projects/{project_id}/media/{item.asset_id}/poster"}
                for item in (*row.video_candidates, *row.image_candidates)
            ]} for row in run.chunks],
            "selection_plan": saved,
            "resolve_calls": 0,
        }

    @app.get("/", response_class=HTMLResponse)
    @app.get("/debug", response_class=HTMLResponse)
    async def page() -> str:
        return render_debug_page()

    @app.get("/curation", response_class=HTMLResponse)
    async def professional_curation_page() -> HTMLResponse:
        token = os.environ.get("RAMBLA_BUILD_TOKEN", "development")
        return HTMLResponse(render_curation_page(token), headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache", "Expires": "0",
        })

    @app.post("/api/curation/projects", status_code=201)
    async def create_project(request: ProjectCreateRequest) -> dict[str, Any]:
        return _project_payload(projects.create(request.name))

    @app.get("/api/curation/projects/{project_id}")
    async def get_project(project_id: str) -> dict[str, Any]:
        payload = _project_payload(load_project(project_id))
        payload["audio_input_kind"] = projects.source_input(project_id).get("input_kind")
        return payload

    @app.post("/api/curation/projects/{project_id}/source/local")
    async def register_project_source(project_id: str, request: LocalSourceRequest) -> dict[str, Any]:
        load_project(project_id)
        source = allowed_source(Path(request.path))
        try:
            return _project_payload(select_default_guide(projects.register_local_video(project_id, source)))
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="source video non trovato") from None

    @app.put("/api/curation/projects/{project_id}/source/upload")
    async def upload_project_source(project_id: str, request: Request, filename: str = "source-video.mp4") -> dict[str, Any]:
        load_project(project_id)
        try:
            project = projects.write_uploaded_video(project_id, filename, [await request.body()])
        except ValueError as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        return _project_payload(select_default_guide(project))

    @app.put("/api/curation/projects/{project_id}/source/audio")
    async def upload_primary_audio(project_id: str, request: Request, filename: str = "source-audio") -> dict[str, Any]:
        load_project(project_id)
        try:
            project = projects.write_primary_audio(
                project_id, filename, [await request.body()], command_runner=guide_command_runner,
            )
        except ValueError as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        except (RuntimeError, subprocess.CalledProcessError) as exc:
            raise HTTPException(status_code=422, detail=f"audio source preparation failed: {exc}") from exc
        payload = _project_payload(project)
        payload["audio_input_kind"] = projects.source_input(project_id).get("input_kind")
        return payload

    @app.put("/api/curation/projects/{project_id}/source/text")
    async def upload_text_source(project_id: str, request: TextSourceRequest) -> dict[str, Any]:
        load_project(project_id)
        try:
            project = projects.write_text_source(
                project_id, request.text, command_runner=guide_command_runner,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except (RuntimeError, subprocess.CalledProcessError) as exc:
            raise HTTPException(status_code=422, detail=f"text timeline preparation failed: {exc}") from exc
        return _project_payload(project)

    @app.post("/api/curation/projects/{project_id}/guide/original")
    async def use_original_guide(project_id: str) -> dict[str, Any]:
        load_project(project_id)
        try:
            projects.extract_source_audio(project_id, command_runner=guide_command_runner)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _project_payload(projects.load(project_id))

    @app.put("/api/curation/projects/{project_id}/guide/upload")
    async def upload_guide(project_id: str, request: Request, filename: str = "guide-audio") -> dict[str, Any]:
        load_project(project_id)
        projects.write_external_guide_audio(project_id, filename, [await request.body()], command_runner=guide_command_runner)
        return _project_payload(projects.load(project_id))

    social_media_slots = asyncio.Semaphore(2)
    social_media_locks = {}

    @app.post("/api/curation/projects/{project_id}/social-media/{asset_id}/{mode}")
    async def prepare_social_media(project_id: str, asset_id: str, mode: str):
        from .social_media import prepare_media, media_path
        candidate = project_run(project_id).candidate_index.get(asset_id)
        if candidate is None or candidate.provider not in {'tiktok','instagram','youtube_shorts'} or mode not in {'preview','full','hover'}:
            raise HTTPException(status_code=404, detail='Social video not found')
        root = project_run_root(project_id)
        key=(project_id,asset_id,mode)
        lock=social_media_locks.setdefault(key,asyncio.Lock())
        try:
            async with lock, social_media_slots:
                cookies=[]
                profiles=getattr(app.state,'social_profiles',None)
                if candidate.provider == 'tiktok' and getattr(app.state,'tiktok_cookie_reader',None):
                    cookies=await app.state.tiktok_cookie_reader(candidate.source_page)
                elif profiles and candidate.provider in {'tiktok','instagram'} and profiles.status()[candidate.provider].get('connection_ready'):
                    async def read_session(page,context):
                        return await context.cookies([candidate.source_page])
                    cookies=await profiles.run_in_profile(candidate.provider,read_session)
                path=await asyncio.to_thread(prepare_media,candidate.source_page,candidate.provider,root,mode,cookies=cookies)
            return {'url':f'/api/curation/projects/{project_id}/social-media/{asset_id}/{mode}', 'verified':False}
        except (ValueError,RuntimeError) as exc:
            raise HTTPException(status_code=502,detail=str(exc)) from None

    @app.get("/api/curation/projects/{project_id}/social-media/{asset_id}/{mode}")
    async def get_social_media(project_id: str, asset_id: str, mode: str):
        from .social_media import media_path
        candidate=project_run(project_id).candidate_index.get(asset_id)
        if candidate is None:
            raise HTTPException(status_code=404,detail='Social video not found')
        try:
            root=project_run_root(project_id)
            path=media_path(candidate.source_page,candidate.provider,root,mode)
            path.resolve().relative_to(root.resolve())
        except ValueError:
            raise HTTPException(status_code=404,detail='Invalid media') from None
        if not path.is_file():
            raise HTTPException(status_code=404,detail='Media not prepared')
        return FileResponse(path, filename=f'{candidate.provider}-video.mp4') if mode=='full' else FileResponse(path)

    @app.get("/api/curation/projects/{project_id}/media/{asset_id}/{variant}")
    async def get_project_media(project_id: str, asset_id: str, variant: str) -> FileResponse:
        project = load_project(project_id)
        if asset_id == "source-video" and variant == "source" and project.source_video is not None:
            source = allowed_source(Path(project.source_video.path))
            if not source.is_file():
                raise HTTPException(status_code=404, detail="media non disponibile")
            return FileResponse(source)
        if asset_id == "source-audio" and variant == "source" and project.guide_audio is not None:
            source = Path(project.guide_audio.path).resolve()
            try:
                source.relative_to(project_root.resolve())
            except ValueError:
                raise HTTPException(status_code=403, detail="audio fuori dal project store") from None
            if not source.is_file():
                raise HTTPException(status_code=404, detail="audio non disponibile")
            return FileResponse(source)
        run_root = project_run_root(project_id)
        candidate = project_run(project_id).candidate_index.get(asset_id)
        if candidate is None or variant not in {"preview", "poster", "download"}:
            raise HTTPException(status_code=404, detail="asset non trovato")
        if variant == "download" and not (candidate.kind == "video" and candidate.preview_status == "ready" and candidate.clip_verified):
            raise HTTPException(status_code=404, detail="clip scaricabile non disponibile")
        path = candidate.preview_path if variant in {"preview", "download"} else candidate.poster_path
        if variant == "preview" and candidate.preview_url:
            return RedirectResponse(candidate.preview_url)
        if not path or not Path(path).is_file():
            raise HTTPException(status_code=404, detail="media non disponibile")
        try:
            Path(path).resolve().relative_to(run_root.resolve())
        except ValueError:
            raise HTTPException(status_code=403, detail="media fuori dalla run") from None
        return FileResponse(path, filename=Path(path).name) if variant == "download" else FileResponse(path)

    @app.get("/api/curation/projects/{project_id}/curation")
    async def get_project_curation(project_id: str) -> dict[str, Any]:
        load_project(project_id)
        return curation_payload(project_id)

    @app.post("/api/curation/projects/{project_id}/analyze")
    async def analyze_project(project_id: str) -> dict[str, Any]:
        project = load_project(project_id)
        run_root = project_run_root(project_id)
        marker = _read_json(run_root / "analysis-signature.json", {})
        from .analysis_reuse import ensure_analysis_ready
        if ensure_analysis_ready(run_root,project):
            return {"status": "reused", "resolve_calls": 0}
        if project.source_video is None:
            raise HTTPException(status_code=422, detail="source video required")
        active = RUNS.get(project_runs.get(project_id, ""))
        if active and active.status in {"QUEUED", "RUNNING"}:
            raise HTTPException(status_code=409, detail="analysis already running")
        state = RunState(uuid.uuid4().hex[:12], Path(project.source_video.path), run_root, guide_audio=Path(project.guide_audio.path) if project.guide_audio else None, analysis_signature=project.analysis_signature, stage_type="analyze")
        RUNS[state.run_id] = state
        project_runs[project_id] = state.run_id
        asyncio.create_task(_run(state))
        return {"status": "started", "run_id": state.run_id, "resolve_calls": 0}

    def start_sourcing(project_id: str, stage_type: str) -> dict[str, Any]:
        project = load_project(project_id); run_root = project_run_root(project_id)
        if not (run_root / "semantic-chunks.json").is_file():
            raise HTTPException(status_code=422, detail="analysis required before sourcing")
        approved_plan(project_id)
        from .transcript_corrections import require_current_editorial
        try: require_current_editorial(run_root)
        except ValueError as exc: raise HTTPException(status_code=409,detail=str(exc)) from exc
        active = RUNS.get(project_runs.get(project_id, ""))
        if active and active.status in {"QUEUED", "RUNNING"}:
            raise HTTPException(status_code=409, detail="project stage already running")
        state = RunState(uuid.uuid4().hex[:12], Path(project.source_video.path), run_root,
            guide_audio=Path(project.guide_audio.path) if project.guide_audio else None,
            analysis_signature=project.analysis_signature, stage_type=stage_type)
        RUNS[state.run_id] = state; project_runs[project_id] = state.run_id
        asyncio.create_task(_run(state))
        return {"status": "started", "run_id": state.run_id, "stage": stage_type, "resolve_calls": 0}

    @app.post("/api/curation/projects/{project_id}/source/videos")
    async def source_project_videos(project_id: str) -> dict[str, Any]:
        return start_sourcing(project_id, "videos")

    @app.post("/api/curation/projects/{project_id}/source/images")
    async def source_project_images(project_id: str) -> dict[str, Any]:
        return start_sourcing(project_id, "images")

    @app.get("/api/curation/projects/{project_id}/transcript")
    async def get_project_transcript(project_id: str) -> dict[str, Any]:
        path = project_run_root(project_id) / "transcript-raw.json"
        if (path.parent/'transcript-corrections.json').is_file():
            from .editorial_import import normalized_chunks
            return {"segments":normalized_chunks(path.parent),"manually_corrected":True}
        return _read_json(path, {"segments": [], "status": "pending"})

    @app.put("/api/curation/projects/{project_id}/curation/chunks/{chunk_id}/selection")
    async def put_project_selection(project_id: str, chunk_id: str, request: ProjectSelectionRequest) -> dict[str, Any]:
        load_project(project_id)
        try:
            changed = project_selection_store(project_id).set_chunk_selection(chunk_id, request.asset_ids, no_broll=request.no_broll)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"selection": changed, "resolve_calls": 0}

    @app.get("/api/curation/run/default/media/{asset_id}/{variant}")
    async def get_asset_media(asset_id: str, variant: str) -> FileResponse:
        candidate = load_curation_run(Path(DEFAULT_OUTPUT)).candidate_index.get(asset_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail="asset non trovato")
        path = candidate.poster_path if variant == "poster" else candidate.preview_path
        if not path or not Path(path).is_file():
            raise HTTPException(status_code=404, detail="preview non disponibile")
        root = Path(DEFAULT_OUTPUT).resolve()
        try:
            Path(path).resolve().relative_to(root)
        except ValueError as exc:
            raise HTTPException(status_code=403, detail="media fuori dalla run") from exc
        return FileResponse(path)

    @app.get("/api/curation/run/default")
    async def get_curation() -> dict[str, Any]:
        run = load_curation_run(Path(DEFAULT_OUTPUT))
        return {"chunks": [{"id": row.chunk_id, "text": row.text, "assets": [
            {"asset_id": item.asset_id, "chunk_id": item.chunk_id, "kind": item.kind, "provider": item.provider,
             "title": item.title, "rights_state": item.rights_state, "orientation": item.orientation,
             "preview_url": f"/api/curation/run/default/media/{item.asset_id}/preview",
             "poster_url": f"/api/curation/run/default/media/{item.asset_id}/poster"}
            for item in (*row.video_candidates, *row.image_candidates)]} for row in run.chunks], "resolve_calls": 0}

    @app.put("/api/curation/run/default/selection")
    async def put_curation_selection(request: CurationSelectionRequest) -> dict[str, Any]:
        if any(value != "NO_BROLL" and not value.strip() for value in request.selections.values()):
            raise HTTPException(status_code=422, detail="selezione non valida")
        output = Path(DEFAULT_OUTPUT)
        _write_selection(output, request.selections)
        return {"selections": request.selections, "resolve_calls": 0}

    @app.post("/v1/debug/runs")
    async def create_run(request: RunRequest) -> dict[str, Any]:
        video = Path(request.video_path)
        if not video.is_file():
            raise HTTPException(status_code=422, detail=f"video non trovato: {video}")
        state = RunState(uuid.uuid4().hex[:12], video, Path(request.output_dir))
        RUNS[state.run_id] = state
        asyncio.create_task(_run(state))
        return state.snapshot()

    @app.get("/v1/debug/runs/{run_id}")
    async def get_run(run_id: str) -> dict[str, Any]:
        if run_id not in RUNS:
            raise HTTPException(status_code=404, detail="run non trovata")
        return RUNS[run_id].snapshot()

    @app.post("/v1/debug/runs/{run_id}/cancel")
    async def cancel_run(run_id: str) -> dict[str, Any]:
        if run_id not in RUNS:
            raise HTTPException(status_code=404, detail="run non trovata")
        state = RUNS[run_id]
        if state.status not in {"QUEUED", "RUNNING"}:
            return state.snapshot()
        state.status = "CANCELLED"
        if state.process is not None and state.process.returncode is None:
            await _stop_worker(state.process)
        await _emit(state, DebugEvent("cancelled", "Run annullata", data=state.snapshot()))
        return state.snapshot()

    @app.get("/v1/debug/runs/{run_id}/metrics")
    async def get_metrics(run_id: str) -> dict[str, Any]:
        if run_id not in RUNS:
            raise HTTPException(status_code=404, detail="run non trovata")
        return _metrics(RUNS[run_id])

    @app.get("/v1/debug/runs/{run_id}/events")
    async def events(run_id: str) -> StreamingResponse:
        if run_id not in RUNS:
            raise HTTPException(status_code=404, detail="run non trovata")
        state = RUNS[run_id]

        async def stream() -> AsyncIterator[str]:
            queue: asyncio.Queue[DebugEvent] = asyncio.Queue()
            state.subscribers.append(queue)
            try:
                for event in state.events:
                    yield "data: " + json.dumps(event.as_dict(), ensure_ascii=False) + "\n\n"
                while True:
                    try:
                        event = await asyncio.wait_for(queue.get(), 0.75)
                        yield "data: " + json.dumps(event.as_dict(), ensure_ascii=False) + "\n\n"
                    except asyncio.TimeoutError:
                        pass
                    yield "data: " + json.dumps({"stage": "snapshot", "message": "snapshot", "progress": None, "data": state.snapshot()}, ensure_ascii=False) + "\n\n"
                    if state.status in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                        return
            finally:
                if queue in state.subscribers:
                    state.subscribers.remove(queue)

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/health")
    async def health() -> dict[str, Any]:
        from .runtime_mode import uses_api_runtime
        return {
            "status": "ok",
            "debug_runner": True,
            "runtime_mode": os.environ.get("RAMBLA_RUNTIME_MODE", "local"),
            "local_gpu_required": not uses_api_runtime(),
            "build_token": os.environ.get("RAMBLA_BUILD_TOKEN", "development"),
            "server_pid": os.getpid(),
            "resolve_calls": 0,
        }

    return app


app = create_app()


def main() -> None:
    import uvicorn
    uvicorn.run("backend.app.debug_server:app", host="127.0.0.1", port=8765, reload=False)


if __name__ == "__main__":
    main()
