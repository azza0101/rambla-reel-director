"""Persistent, immutable handoffs between RAMBLA and the Resolve bridge."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from .atomic_io import write_json
import threading
import uuid
from typing import Any


SCHEMA = "rambla-resolve-handoff-1"
_TRANSITIONS = {
    "pending": {"applying", "discarded"},
    "applying": {"completed", "failed"},
    "failed": {"applying", "discarded"},
    "completed": set(),
    "discarded": set(),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    write_json(path, value)


def _read_json(path: Path) -> dict[str, Any]:
    for attempt in range(6):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(.025 * 2 ** attempt)


def _media_ready(row: dict[str, Any]) -> bool:
    raw = str(row.get("media_path") or "").strip()
    return bool(raw and Path(raw).is_file())


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    timed = list(payload.get("broll_clips") or [])
    generic = list(payload.get("generic_broll_clips") or [])
    timed_ready = sum(_media_ready(row) for row in timed)
    generic_ready = sum(_media_ready(row) for row in generic)
    unavailable = len(payload.get("broll_unavailable") or []) + len(timed) - timed_ready + len(generic) - generic_ready
    return {
        "duration_seconds": float(payload.get("duration_seconds") or 0),
        "title_count": len(payload.get("titles") or payload.get("segments") or []),
        "subtitle_count": len(payload.get("subtitles") or []),
        "broll_count": timed_ready,
        "generic_broll_count": generic_ready,
        "unavailable_count": unavailable,
    }


def _row_keys(payload: dict[str, Any], field: str) -> set[str]:
    return {str(row.get("asset_id") or row.get("provider_id") or row.get("source_page") or "") for row in payload.get(field) or [] if isinstance(row, dict)} - {""}


class ResolveHandoffStore:
    def __init__(self, projects_root: Path):
        self.projects_root = Path(projects_root)
        self._lock = threading.RLock()

    def _path(self, project_root: Path, package_id: str) -> Path:
        return Path(project_root) / "resolve-outbox" / package_id / "package.json"

    def prepare(self, project_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            package_id = f"handoff-{stamp}-{uuid.uuid4().hex[:8]}"
            created = _now()
            previous = []
            for old_path in (Path(project_root) / "resolve-outbox").glob("*/package.json"):
                try:
                    old=_read_json(old_path)
                    if old.get("status")=="completed": previous.append(old)
                except (OSError,json.JSONDecodeError): pass
            prior=max(previous,key=lambda row:row.get("created_at",""),default=None)
            prior_payload=(prior or {}).get("payload") or {}
            before=_row_keys(prior_payload,"broll_clips"); after=_row_keys(payload,"broll_clips")
            before_generic=_row_keys(prior_payload,"generic_broll_clips"); after_generic=_row_keys(payload,"generic_broll_clips")
            package = {
                "schema": SCHEMA, "package_id": package_id, "status": "pending",
                "created_at": created, "updated_at": created,
                "project_id": str(payload.get("project_id") or Path(project_root).name),
                "bridge_session_id": str(payload.get("bridge_session_id") or ""),
                "resolve_project": str(payload.get("source_project_name") or ""),
                "timeline_id": str(payload.get("source_timeline_id") or ""),
                "timeline_name": str(payload.get("source_timeline_name") or payload.get("source_timeline") or ""),
                "summary": _summary(payload), "progress": {"phase": "pending", "percent": 0},
                "revision": int((prior or {}).get("revision") or 0)+1,
                "supersedes": (prior or {}).get("package_id"),
                "change_summary": {"broll_added":len(after-before),"broll_removed":len(before-after),
                                   "generic_added":len(after_generic-before_generic),"generic_removed":len(before_generic-after_generic)},
                "payload": deepcopy(payload),
            }
            _atomic_json(self._path(project_root, package_id), package)
            return deepcopy(package)

    def read(self, project_root: Path, package_id: str) -> dict[str, Any]:
        path = self._path(project_root, package_id)
        if not path.is_file():
            raise FileNotFoundError(package_id)
        return _read_json(path)

    def pending(self, *, resolve_project: str, timeline_id: str, bridge_session_id: str = "") -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in self.projects_root.glob("*/resolve-outbox/*/package.json"):
            try:
                row = _read_json(path)
            except (OSError, json.JSONDecodeError):
                continue
            if row.get("status") not in {"pending", "applying", "failed"}:
                continue
            if resolve_project and row.get("resolve_project") != resolve_project:
                continue
            if bridge_session_id and row.get("bridge_session_id") not in {"", bridge_session_id}:
                continue
            rows.append(row)
        rows=sorted(rows, key=lambda row: row.get("created_at", ""), reverse=True)
        return [row for row in rows if not timeline_id or row.get("timeline_id")==timeline_id]

    def mark_received(self, project_root: Path, package_id: str, *, bridge_session_id: str) -> dict[str, Any]:
        with self._lock:
            package = self.read(project_root, package_id)
            if package.get("status") not in {"pending", "failed"}:
                return package
            assigned = str(package.get("bridge_session_id") or "")
            if assigned and bridge_session_id and assigned != bridge_session_id:
                raise ValueError("Pacchetto assegnato a un'altra sessione del bridge")
            package["bridge_session_id"] = bridge_session_id or assigned
            package["bridge_received_at"] = _now()
            package["updated_at"] = package["bridge_received_at"]
            package["progress"] = {"phase":"received", "percent":100,
                                   "message":"Pacchetto ricevuto dal bridge di Resolve"}
            _atomic_json(self._path(project_root, package_id), package)
            return deepcopy(package)

    def transition(self, project_root: Path, package_id: str, status: str, **updates: Any) -> dict[str, Any]:
        with self._lock:
            package = self.read(project_root, package_id)
            current = str(package.get("status") or "")
            if status != current and status not in _TRANSITIONS.get(current, set()):
                raise ValueError(f"Resolve handoff transition not allowed: {current} -> {status}")
            package.update(deepcopy(updates))
            package["status"] = status
            package["updated_at"] = _now()
            _atomic_json(self._path(project_root, package_id), package)
            return deepcopy(package)
