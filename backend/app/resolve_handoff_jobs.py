"""Single-writer asynchronous Resolve handoff jobs."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import threading
import time
import traceback
from typing import Any, Callable

from .resolve_handoff import ResolveHandoffStore


class ResolveHandoffJobs:
    def __init__(self, store: ResolveHandoffStore, runner: Callable[[dict[str, Any]], dict[str, Any]]):
        self.store, self.runner = store, runner
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rambla-resolve")
        self._lock = threading.RLock()
        self._active: str | None = None

    def apply(self, project_root: Path, package_id: str, destination_mode: str, apply_scope: str = "all", *, current_project: str, current_timeline_id: str, current_mark_in: int | None = None) -> dict[str, Any]:
        if destination_mode not in {"new", "active"}:
            raise ValueError("destination_mode must be 'new' or 'active'")
        if apply_scope not in {"all", "titles", "subtitles", "media"}:
            raise ValueError("apply_scope must be 'all', 'titles', 'subtitles' or 'media'")
        if apply_scope != "all" and destination_mode != "active":
            raise ValueError("Selective Resolve updates require the active timeline")
        package = self.store.read(project_root, package_id)
        if package["status"] == "applying":
            return package
        if package.get("resolve_project") and package["resolve_project"] != current_project:
            raise ValueError("Resolve project changed after package preparation")
        with self._lock:
            if self._active:
                raise RuntimeError("Another Resolve apply is already running")
            self._active = package_id
            started = self.store.transition(
                project_root, package_id, "applying",
                application_count=int(package.get("application_count") or 0) + 1,
                destination_mode=destination_mode,
                apply_scope=apply_scope,
                destination_timeline_id=current_timeline_id if destination_mode == "active" else None,
                destination_mark_in=int(current_mark_in) if destination_mode == "active" and current_mark_in is not None else None,
                progress={"phase":"validate", "percent":5, "message":"Controllo pacchetto"}, error=None,
            )
            self._executor.submit(self._run, Path(project_root), package_id, destination_mode, apply_scope)
            return started

    def _run(self, project_root: Path, package_id: str, destination_mode: str, apply_scope: str) -> None:
        stop=threading.Event()
        progress_path=project_root / "resolve-outbox" / package_id / "progress.json"
        watcher=None
        started_at = time.time()
        phases = []
        last_progress = {"phase":"destination", "percent":18, "message":"Preparo la timeline di destinazione"}
        try:
            package = self.store.read(project_root, package_id)
            payload = dict(package["payload"])
            payload.update(destination_mode=destination_mode, apply_scope=apply_scope, package_id=package_id, handoff_progress_path=str(progress_path))
            if destination_mode == "active":
                payload["source_timeline_id"] = str(package.get("destination_timeline_id") or "")
                if package.get("destination_mark_in") is not None:
                    payload["bridge_mark_in"] = int(package["destination_mark_in"])
            self.store.transition(project_root, package_id, "applying", progress={"phase":"destination", "percent":18, "message":"Preparo la timeline di destinazione"})
            def watch_progress():
                nonlocal last_progress
                last=None
                while not stop.wait(.02):
                    try:
                        progress=json.loads(progress_path.read_text(encoding="utf-8"))
                        marker=(progress.get("phase"),progress.get("percent"))
                        if marker!=last:
                            last_progress = progress
                            phases.append({**progress, 'elapsed_seconds': round(time.time()-started_at, 1)})
                            self.store.transition(project_root,package_id,"applying",progress=progress); last=marker
                    except (OSError,json.JSONDecodeError): pass
            watcher=threading.Thread(target=watch_progress,daemon=True); watcher.start()
            result = self.runner(payload)
            if result.get('timeline_id'):
                from .resolve_project_links import link_project
                link_project(project_root.parent, project_root.name, result['timeline_id'])
            time.sleep(.04)
            stop.set()
            if watcher: watcher.join(timeout=1)
            self.store.transition(project_root, package_id, "completed", result=result,
                                  diagnostics={'elapsed_seconds':round(time.time()-started_at,1),'phases':phases},
                                  progress={"phase":"completed", "percent":100, "message":"Timeline pronta"})
        except Exception as exc:
            stop.set()
            if watcher: watcher.join(timeout=1)
            self.store.transition(project_root, package_id, "failed", error=str(exc),
                                  diagnostics={'elapsed_seconds':round(time.time()-started_at,1), 'last_progress':last_progress, 'phases':phases, 'traceback':traceback.format_exc(), 'helper_traceback':getattr(exc,'helper_traceback',None)},
                                  progress={"phase":"failed", "percent":last_progress.get('percent',0), "message":str(exc)})
        finally:
            stop.set()
            if watcher: watcher.join(timeout=.2)
            # Keep the last helper checkpoint for diagnosing partial TEMP builds.
            with self._lock:
                if self._active == package_id: self._active = None
