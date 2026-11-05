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
    "applying": {"completed", "failed", "cancelled"},
    "failed": {"applying", "discarded"},
    "completed": {"applying", "discarded"},
    "cancelled": {"applying", "discarded"},
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
    summary = {
        "duration_seconds": float(payload.get("duration_seconds") or 0),
        "title_count": len(payload.get("titles") or payload.get("segments") or []),
        "subtitle_count": len(payload.get("subtitles") or []),
        "broll_count": timed_ready,
        "generic_broll_count": generic_ready,
        "unavailable_count": unavailable,
    }
    if payload.get('original_video'):
        original = payload['original_video']
        summary.update(original_video=True, fps=original['fps'],
                       width=original['width'], height=original['height'],
                       original_has_audio=bool(original['has_audio']))
    if payload.get('native_cut'):
        cut = payload['native_cut']
        summary.update(native_cut=True, cut_count=len(cut['segments']), fps=cut['fps'],
                       width=cut['width'], height=cut['height'])
    if payload.get('components') is not None:
        summary['components'] = deepcopy(payload['components'])
    return summary



def bind_standard_target(payload: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    """Bind a regular export to the Resolve timeline visible at SEND time.

    Native CUT and its reference are intentionally immutable and stay on
    their own stricter source timeline contract.
    """
    result = deepcopy(payload)
    if result.get("native_cut") or result.get("native_cut_reference") or not target.get("connected"):
        return result
    result.update(
        source_project_name=str(target["project"]),
        source_timeline_id=str(target["timeline_id"]),
        source_timeline_name=str(target["timeline"]),
        bridge_mark_in=int(target["mark_in"]),
    )
    return result


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
                "media_issues": deepcopy(payload.get("media_issues") or []),
                "revision": int((prior or {}).get("revision") or 0)+1,
                "supersedes": (prior or {}).get("package_id"),
                "change_summary": {"broll_added":len(after-before),"broll_removed":len(before-after),
                                   "generic_added":len(after_generic-before_generic),"generic_removed":len(before_generic-after_generic)},
                "payload": deepcopy(payload),
            }
            from .omnicut_handoff import build_handoff
            _atomic_json(self._path(project_root, package_id).with_name('omnicut.json'),
                         build_handoff(payload, project_root=project_root))
            _atomic_json(self._path(project_root, package_id), package)
            return deepcopy(package)

    def read(self, project_root: Path, package_id: str) -> dict[str, Any]:
        path = self._path(project_root, package_id)
        if not path.is_file():
            raise FileNotFoundError(package_id)
        return _read_json(path)

    def pending(self, *, resolve_project: str, timeline_id: str, bridge_session_id: str = "",
                native_only: bool = False) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in self.projects_root.glob("*/resolve-outbox/*/package.json"):
            try:
                row = _read_json(path)
            except (OSError, json.JSONDecodeError):
                continue
            if row.get("status") not in {"pending", "applying", "failed", "completed", "cancelled"}:
                continue
            if native_only:
                if not ((row.get('summary') or {}).get('native_cut')
                        and bridge_session_id
                        and row.get('bridge_session_id') == bridge_session_id):
                    continue
            native_session = bool((row.get('summary') or {}).get('native_cut') and bridge_session_id
                                  and row.get('bridge_session_id') == bridge_session_id)
            # Unbound standard exports are allowed only when explicitly
            # addressed to this live bridge session. Bound projects must still
            # match exactly, so no cross-project package can be applied.
            unbound_session = bool(
                not row.get("resolve_project") and bridge_session_id
                and row.get("bridge_session_id") == bridge_session_id
            )
            if resolve_project and row.get("resolve_project") != resolve_project and not (native_session or unbound_session):
                continue
            if bridge_session_id and row.get("bridge_session_id") not in {"", bridge_session_id}:
                continue
            rows.append(row)
        rows=sorted(rows, key=lambda row: row.get("created_at", ""), reverse=True)
        return [row for row in rows if not timeline_id or row.get("timeline_id")==timeline_id
                or ((row.get('summary') or {}).get('native_cut') and bridge_session_id
                    and row.get('bridge_session_id') == bridge_session_id)]

    def reconnect(self, project_root: Path, package_id: str, *, bridge_session_id: str,
                  resolve_project: str, timeline_id: str) -> dict[str, Any]:
        """Reoffer the same pending package to a live session, without an apply."""
        with self._lock:
            package = self.read(project_root, package_id)
            if package.get('status') != 'pending':
                raise ValueError('Pacchetto non in attesa: controlla applicazione e diagnostica')
            if not bridge_session_id:
                raise ValueError('Bridge non collegato')
            expected = str(package.get('resolve_project') or '')
            if expected and expected != resolve_project:
                raise ValueError(f'Progetto Resolve diverso: atteso {expected}, aperto {resolve_project}')
            payload = package.get('payload') or {}
            if payload.get('native_cut_reference') and package.get('timeline_id') != timeline_id:
                raise ValueError('Apri la timeline CUT originale prima di ricollegare il pacchetto')
            if package.get('bridge_session_id') != bridge_session_id:
                package['bridge_session_id'] = bridge_session_id
                package['bridge_received_at'] = None
                package['progress'] = {'phase':'pending','percent':0,'message':'Attendo ricezione dal bridge'}
                package['updated_at'] = _now()
                _atomic_json(self._path(project_root, package_id), package)
            return deepcopy(package)

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

    def update_payload(self, project_root: Path, package_id: str, **updates: Any) -> dict[str, Any]:
        """Refresh mutable execution choices without rebuilding the whole handoff."""
        with self._lock:
            package = self.read(project_root, package_id)
            payload = deepcopy(package.get("payload") or {})
            payload.update(deepcopy(updates))
            package["payload"] = payload
            package["updated_at"] = _now()
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
