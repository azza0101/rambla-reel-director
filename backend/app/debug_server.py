from __future__ import annotations

import asyncio
import json
import os
import shlex
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict

from .curation_artifacts import load_curation_run
from .curation_project import CurationProject, ProjectStore
from .curation_selection import SelectionStore
from .curation_ui import render_curation_page

DEFAULT_VIDEO = r"Z:\APP REEL TEST\VIDEO BASE\KURA_Finto etico_draft 1.mp4"
DEFAULT_OUTPUT = r"Z:\APP REEL TEST\qwen-embedding-smoke\kura-finto-etico-smoke\run"
DEFAULT_PROFILE = r"Z:\APP REEL TEST\qwen-embedding-smoke\debug-runner-command.json"
STAGES = (
    ("prepare", "Preparazione", 3.0),
    ("asr", "ASR / trascrizione", 12.0),
    ("semantic_chunking", "Chunk semantici", 9.0),
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


class ArtifactProgressTracker:
    ARTIFACTS = (
        ("asr", ("transcript-raw.json", "transcript.json"), "Trascrizione pronta"),
        ("semantic_chunking", ("semantic-chunks.json", "semantic-beats.json"), "Chunk semantici pronti"),
        ("coverage", ("coverage-metrics.json",), "Coverage planning disponibile"),
        ("online_search", ("online-candidates.json", "candidate-metrics.json"), "Candidati online disponibili"),
        ("edit_plan", ("edit-plan.json",), "Edit Plan scritto"),
        ("review", ("review.html",), "Review HTML pronta"),
    )

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.seen: set[str] = set()

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


class ProjectSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_ids: list[str] = []
    no_broll: bool = False


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

    def total(self) -> float:
        total_weight = sum(WEIGHTS.values())
        done = sum(WEIGHTS[key] * self.progress.get(key, 0.0) / 100.0 for key in WEIGHTS)
        return round(done * 100.0 / total_weight, 2) if total_weight else 0.0

    def snapshot(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "video_path": str(self.video_path),
            "output_dir": str(self.output_dir),
            "status": self.status,
            "return_code": self.return_code,
            "stage_progress": self.progress,
            "total_progress": self.total(),
            "last_message": self.last_message,
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


def _write_selection(output_dir: Path, selections: dict[str, str]) -> None:
    target = _selection_path(output_dir)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps({"schema_version": "curation-selection-0.1", "selections": selections}, indent=2), encoding="utf-8")
    temporary.replace(target)


def _command(state: RunState) -> list[str]:
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
    values = {"video": str(state.video_path), "output": str(state.output_dir)}
    return [item.format_map(values) for item in payload]


async def _emit(state: RunState, event: DebugEvent) -> None:
    state.events.append(event)
    state.last_message = event.message
    if event.stage in WEIGHTS and event.progress is not None:
        state.progress[event.stage] = max(state.progress.get(event.stage, 0.0), event.progress)
    for queue in list(state.subscribers):
        await queue.put(event)


async def _run(state: RunState) -> None:
    state.status = "RUNNING"
    state.output_dir.mkdir(parents=True, exist_ok=True)
    tracker = ArtifactProgressTracker(state.output_dir)
    await _emit(state, DebugEvent("prepare", "Run avviata", 100.0))
    try:
        command = _command(state)
        await _emit(state, DebugEvent("log", "Comando: " + " ".join(shlex.quote(x) for x in command)))
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(Path.cwd()),
        )

        async def watch() -> None:
            while process.returncode is None:
                for event in tracker.scan():
                    await _emit(state, event)
                await asyncio.sleep(0.35)

        watcher = asyncio.create_task(watch())
        assert process.stdout is not None
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            await _emit(state, parse_worker_line(line.decode("utf-8", errors="replace")))
        state.return_code = await process.wait()
        watcher.cancel()
        try:
            await watcher
        except asyncio.CancelledError:
            pass
        for event in tracker.scan():
            await _emit(state, event)
        state.status = "SUCCEEDED" if state.return_code == 0 else "FAILED"
        await _emit(state, DebugEvent("review" if state.status == "SUCCEEDED" else "error", state.status, 100.0 if state.status == "SUCCEEDED" and (state.output_dir / "review.html").exists() else None, state.snapshot()))
    except Exception as exc:
        state.status = "FAILED"
        await _emit(state, DebugEvent("error", str(exc), data=state.snapshot()))


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
<div class="card row"><div class="grow"><label>Video</label><input id="video"></div><div class="grow"><label>Output</label><input id="out"></div><button id="run">ESEGUI</button></div>
<div class="card"><div class="head"><b>Barra totale</b><span id="totalText">0%</span></div><div class="total"><div id="total" class="fill"></div></div><div id="msg" class="muted">In attesa.</div></div>
<div class="card"><div id="stages" class="stages"></div></div>
<div class="card metrics"><div class="metric"><span class="muted">Run</span><b id="rid">—</b></div><div class="metric"><span class="muted">A/B certificate</span><b id="ab">—</b></div><div class="metric"><span class="muted">NO_BROLL</span><b id="nb">—</b></div><div class="metric"><span class="muted">Download bytes</span><b id="bytes">—</b></div><div class="metric"><span class="muted">Tempo</span><b id="secs">—</b></div></div>
<div class="card split"><div><div class="muted" style="margin-bottom:6px">Log live</div><pre id="log"></pre></div><div><div class="muted" style="margin-bottom:6px">Eventi / dati</div><div id="events"></div></div></div>
<div class="card muted" id="links">Gli output appariranno qui a fine run.</div>
<script>const DEF_VIDEO={video},DEF_OUT={output},STAGES={stages};const nodes={{}};let es=null;const $=id=>document.getElementById(id);$('video').value=DEF_VIDEO;$('out').value=DEF_OUT;function esc(v){{return String(v??'').replace(/[&<>\"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]))}}function init(){{$('stages').innerHTML='';STAGES.forEach(s=>{{const n=document.createElement('div');n.className='stage';n.innerHTML=`<div class="head"><b>${{esc(s.label)}}</b><span>0%</span></div><div class="bar"><div class="fill"></div></div>`;$('stages').appendChild(n);nodes[s.id]=n}})}}function setStage(k,v){{const n=nodes[k];if(!n)return;v=Math.max(0,Math.min(100,Number(v)||0));n.querySelector('span').textContent=v.toFixed(0)+'%';n.querySelector('.fill').style.width=v+'%';n.classList.toggle('done',v>=100)}}function snap(s){{$('rid').textContent=s.run_id||'—';$('totalText').textContent=(s.total_progress||0).toFixed(1)+'%';$('total').style.width=(s.total_progress||0)+'%';$('msg').textContent=s.last_message||'';Object.entries(s.stage_progress||{{}}).forEach(([k,v])=>setStage(k,v))}}async function metrics(id){{try{{const m=await (await fetch(`/v1/debug/runs/${{id}}/metrics`)).json();$('ab').textContent=m.certified_ab_pairs??'—';$('nb').textContent=m.no_broll_count??'—';$('bytes').textContent=m.downloaded_bytes??'—';$('secs').textContent=m.total_seconds==null?'—':m.total_seconds+'s'}}catch(_){{}}}}function ev(e){{const d=document.createElement('div');d.className='event';d.innerHTML=`<b>${{esc(e.stage)}}</b> · ${{esc(e.message)}}`;if(e.data&&Object.keys(e.data).length)d.innerHTML+=`<pre style="height:auto;margin-top:6px">${{esc(JSON.stringify(e.data,null,2))}}</pre>`;$('events').prepend(d);$('log').textContent+=`[${{e.stage}}] ${{e.message}}\n`;$('log').scrollTop=$('log').scrollHeight;if(e.progress!=null)setStage(e.stage,e.progress)}}async function run(){{if(es)es.close();$('run').disabled=true;$('log').textContent='';$('events').innerHTML='';init();$('status').textContent='AVVIO…';try{{const r=await fetch('/v1/debug/runs',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{video_path:$('video').value,output_dir:$('out').value}})}});const s=await r.json();if(!r.ok)throw new Error(s.detail||JSON.stringify(s));snap(s);es=new EventSource(`/v1/debug/runs/${{s.run_id}}/events`);es.onmessage=async x=>{{const e=JSON.parse(x.data);if(e.stage==='snapshot'){{snap(e.data);await metrics(e.data.run_id);if(['SUCCEEDED','FAILED'].includes(e.data.status)){{$('status').textContent=e.data.status;$('status').className=e.data.status==='SUCCEEDED'?'good':'bad';$('run').disabled=false;if(e.data.status==='SUCCEEDED')$('links').innerHTML=`Review: <code>${{esc(e.data.review_path)}}</code><br>Edit Plan: <code>${{esc(e.data.edit_plan_path)}}</code>`}}}}else ev(e)}}}}catch(e){{$('status').textContent='ERRORE';$('status').className='bad';$('log').textContent+=String(e);$('run').disabled=false}}}}$('run').onclick=run;init();</script></main></body></html>'''


def _project_payload(project: CurationProject) -> dict[str, Any]:
    return {
        "project_id": project.project_id,
        "name": project.name,
        "source_video": None if project.source_video is None else {
            "path": project.source_video.path,
            "duration": project.source_video.duration,
            "fps": project.source_video.fps,
            "width": project.source_video.width,
            "height": project.source_video.height,
            "has_audio": project.source_video.has_audio,
        },
        "guide_audio": None if project.guide_audio is None else {"mode": project.guide_audio.mode},
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


def create_app(*, project_root: Path | None = None, curation_run_root: Path | None = None, allowed_media_roots: list[Path] | None = None, probe_runner: Any = None) -> FastAPI:
    app = FastAPI(title="RAMBLA Debug Runner", version="0.1.0")
    project_root = project_root or Path(DEFAULT_OUTPUT).parent / "curation-projects"
    curation_run_root = curation_run_root or Path(DEFAULT_OUTPUT)
    allowed_roots = tuple(root.resolve() for root in (allowed_media_roots or [Path(DEFAULT_VIDEO).parent, project_root]))
    projects = ProjectStore(project_root, probe_runner=probe_runner or _probe_source_video)

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

    def project_run() -> Any:
        try:
            return load_curation_run(curation_run_root)
        except (OSError, ValueError, json.JSONDecodeError):
            raise HTTPException(status_code=404, detail="artifact di curation non disponibile") from None

    def project_selection_store() -> SelectionStore:
        run = project_run()
        return SelectionStore(
            curation_run_root,
            {asset_id: {"chunk_id": item.chunk_id} for asset_id, item in run.candidate_index.items()},
            [item.chunk_id for item in run.chunks],
        )

    def curation_payload(project_id: str) -> dict[str, Any]:
        run = project_run()
        saved = project_selection_store().load()
        return {
            "project_id": project_id,
            "chunks": [{"id": row.chunk_id, "text": row.text,
                "error": any(item.preview_error for item in (*row.video_candidates, *row.image_candidates)),
                "assets": [
                {"asset_id": item.asset_id, "chunk_id": item.chunk_id, "kind": item.kind,
                 "provider": item.provider, "title": item.title, "rights_state": item.rights_state,
                 "orientation": item.orientation,
                 "preview_url": f"/api/curation/projects/{project_id}/media/{item.asset_id}/preview",
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

    @app.get("/debug/curation", response_class=HTMLResponse)
    async def curation_page() -> str:
        return render_curation_page()

    @app.get("/curation", response_class=HTMLResponse)
    async def professional_curation_page() -> str:
        return render_curation_page()

    @app.post("/api/curation/projects", status_code=201)
    async def create_project(request: ProjectCreateRequest) -> dict[str, Any]:
        return _project_payload(projects.create(request.name))

    @app.get("/api/curation/projects/{project_id}")
    async def get_project(project_id: str) -> dict[str, Any]:
        return _project_payload(load_project(project_id))

    @app.post("/api/curation/projects/{project_id}/source/local")
    async def register_project_source(project_id: str, request: LocalSourceRequest) -> dict[str, Any]:
        load_project(project_id)
        source = allowed_source(Path(request.path))
        try:
            return _project_payload(projects.register_local_video(project_id, source))
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="source video non trovato") from None

    @app.put("/api/curation/projects/{project_id}/source/upload")
    async def upload_project_source(project_id: str, request: Request, filename: str = "source-video.mp4") -> dict[str, Any]:
        load_project(project_id)
        try:
            project = projects.write_uploaded_video(project_id, filename, [await request.body()])
        except ValueError as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        return _project_payload(project)

    @app.get("/api/curation/projects/{project_id}/media/{asset_id}/{variant}")
    async def get_project_media(project_id: str, asset_id: str, variant: str) -> FileResponse:
        project = load_project(project_id)
        if asset_id == "source-video" and variant == "source" and project.source_video is not None:
            source = allowed_source(Path(project.source_video.path))
            if not source.is_file():
                raise HTTPException(status_code=404, detail="media non disponibile")
            return FileResponse(source)
        candidate = project_run().candidate_index.get(asset_id)
        if candidate is None or variant not in {"preview", "poster"}:
            raise HTTPException(status_code=404, detail="asset non trovato")
        path = candidate.preview_path if variant == "preview" else candidate.poster_path
        if not path or not Path(path).is_file():
            raise HTTPException(status_code=404, detail="media non disponibile")
        try:
            Path(path).resolve().relative_to(curation_run_root.resolve())
        except ValueError:
            raise HTTPException(status_code=403, detail="media fuori dalla run") from None
        return FileResponse(path)

    @app.get("/api/curation/projects/{project_id}/curation")
    async def get_project_curation(project_id: str) -> dict[str, Any]:
        load_project(project_id)
        return curation_payload(project_id)

    @app.post("/api/curation/projects/{project_id}/analyze")
    async def analyze_project(project_id: str) -> dict[str, Any]:
        load_project(project_id)
        if (curation_run_root / "semantic-chunks.json").is_file():
            return {"status": "reused", "resolve_calls": 0}
        raise HTTPException(status_code=409, detail="analysis artifacts unavailable")

    @app.put("/api/curation/projects/{project_id}/curation/chunks/{chunk_id}/selection")
    async def put_project_selection(project_id: str, chunk_id: str, request: ProjectSelectionRequest) -> dict[str, Any]:
        load_project(project_id)
        try:
            changed = project_selection_store().set_chunk_selection(chunk_id, request.asset_ids, no_broll=request.no_broll)
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
                    if state.status in {"SUCCEEDED", "FAILED"}:
                        return
            finally:
                if queue in state.subscribers:
                    state.subscribers.remove(queue)

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "debug_runner": True, "resolve_calls": 0}

    return app


app = create_app()


def main() -> None:
    import uvicorn
    uvicorn.run("backend.app.debug_server:app", host="127.0.0.1", port=8765, reload=False)


if __name__ == "__main__":
    main()
