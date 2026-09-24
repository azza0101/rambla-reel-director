"""Safe project library, deletion, and disposable-media maintenance."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
from typing import Any

from .curation_project import CurationProject, ProjectStore


def _project_dir(store: ProjectStore, project_id: str) -> Path:
    directory = store._path(project_id).parent.resolve()
    root = store.root.resolve()
    if directory == root or not directory.is_relative_to(root):
        raise ValueError("project path escapes project root")
    return directory


def _walk_stats(root: Path) -> tuple[int, int, int]:
    total = files = newest = 0
    if not root.exists(): return 0, 0, 0
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            entries = list(os.scandir(directory))
        except OSError:
            continue
        for entry in entries:
            try: stat = entry.stat(follow_symlinks=False)
            except OSError: continue
            newest = max(newest, int(stat.st_mtime_ns))
            if entry.is_symlink(): files += 1; total += int(stat.st_size)
            elif entry.is_dir(follow_symlinks=False): stack.append(Path(entry.path))
            elif entry.is_file(follow_symlinks=False): files += 1; total += int(stat.st_size)
    return total, files, newest


def _candidate_count(project_dir: Path) -> int:
    count = 0; run = project_dir / "run"
    if not run.is_dir(): return 0
    for path in run.rglob("online-candidates.json"):
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(rows, list): count += sum(len(r.get("candidates") or []) for r in rows if isinstance(r, dict))
        except (OSError, json.JSONDecodeError, TypeError): pass
    for path in run.rglob("image-candidates.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8")); chunks = payload.get("chunks", {}) if isinstance(payload, dict) else {}
            count += sum(len(r.get("candidates") or []) for r in chunks.values() if isinstance(r, dict))
        except (OSError, json.JSONDecodeError, TypeError): pass
    return count


def project_library_rows(store: ProjectStore) -> list[dict[str, Any]]:
    rows = []
    if not store.root.exists(): return rows
    for directory in store.root.iterdir():
        if not directory.is_dir() or directory.is_symlink(): continue
        try:
            project = store.load(directory.name); project_dir = _project_dir(store, project.project_id)
        except (OSError, ValueError, TypeError, json.JSONDecodeError): continue
        size, files, newest = _walk_stats(project_dir); run = project_dir / "run"
        rows.append({
            "project_id": project.project_id, "name": project.name,
            "source_filename": Path(project.source_video.path).name if project.source_video else None,
            "size_bytes": size, "file_count": files,
            "modified_at": datetime.fromtimestamp(newest / 1_000_000_000, tz=timezone.utc).isoformat() if newest else None,
            "_modified_ns": newest,
            "has_transcript": (run / "transcript-raw.json").is_file(),
            "has_editorial_plan": (run / "visual-plan.json").is_file(),
            "retrieved_media_count": _candidate_count(project_dir),
        })
    rows.sort(key=lambda r: (int(r["_modified_ns"]), r["project_id"]), reverse=True)
    for row in rows: row.pop("_modified_ns", None)
    return rows


def rename_project(store: ProjectStore, project_id: str, name: str) -> CurationProject:
    clean = " ".join(str(name or "").split())
    if not clean: raise ValueError("project name must not be empty")
    if len(clean) > 120: raise ValueError("project name must be at most 120 characters")
    current = store.load(project_id)
    renamed = CurationProject(current.project_id, clean, current.source_video, current.guide_audio)
    store._save(renamed)
    return renamed


def delete_project_tree(store: ProjectStore, project_id: str) -> dict[str, Any]:
    directory = _project_dir(store, project_id); store.load(project_id)
    size, files, _ = _walk_stats(directory); shutil.rmtree(directory)
    return {"project_id": project_id, "deleted_bytes": size, "deleted_files": files, "resolve_calls": 0}


# Fallback/legacy retrieval shares the run root with durable analysis. Therefore
# this list is intentionally strict: transcript/semantic/visual-plan artifacts
# never belong here, even if newer imported-plan retrieval roots contain copies.
_RETRIEVAL_FILES = {
    "online-candidates.json", "video-sourcing-diagnostics.json", "image-candidates.json",
    "video-retrieval-plan.json", "image-retrieval-plan.json", "online-sourcing-benchmark.json",
    "candidate-metrics.json", "coverage-metrics.json", "video-sourcing.json", "image-sourcing.json",
    "edit-plan.json", "review.html", "image-sourcing-timings.json",
}
_RETRIEVAL_DIRS = {"asset-cache", "image-cache", "quality-clips", "preview-cache", "media-cache"}


def _remove_owned(path: Path) -> tuple[int, int, str | None]:
    try:
        if path.is_symlink() or path.is_file():
            try: size = int(path.lstat().st_size)
            except OSError: size = 0
            path.unlink(); return 1, size, None
        if path.is_dir():
            size, files, _ = _walk_stats(path); shutil.rmtree(path); return files, size, None
        return 0, 0, None
    except OSError as exc:
        return 0, 0, f"{path}: {type(exc).__name__}: {exc}"


def _clear_selection_assets(selection_path: Path) -> tuple[int, int]:
    if not selection_path.is_file(): return 0, 0
    try: payload = json.loads(selection_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError): return 0, 0
    chunks = payload.get("chunks") if isinstance(payload, dict) else None
    if not isinstance(chunks, dict): return 0, 0
    cleared = preserved = 0
    for row in chunks.values():
        if not isinstance(row, dict): continue
        if row.get("no_broll") is True or row.get("action") == "CONTINUE_PREVIOUS_VISUAL": preserved += 1; continue
        selected = row.get("selected_assets")
        if isinstance(selected, list) and selected:
            cleared += len(selected); row["selected_assets"] = []
    from .atomic_io import write_json
    write_json(selection_path, payload)
    return cleared, preserved


def _clean_editorial_root(root: Path, *, active: bool) -> tuple[int, int, list[str], int, int]:
    if not root.is_dir(): return 0, 0, [], 0, 0
    cleared, preserved = _clear_selection_assets(root / "selection-plan.json") if active else (0, 0)
    deleted_files = deleted_bytes = 0; failures = []
    for child in list(root.iterdir()):
        if child.name in {"imported-plan.json", "selection-plan.json"}: continue
        files, size, error = _remove_owned(child); deleted_files += files; deleted_bytes += size
        if error: failures.append(error)
    return deleted_files, deleted_bytes, failures, cleared, preserved


def clean_project_media(run_root: Path, retrieval_root: Path) -> dict[str, Any]:
    """Remove regenerable retrieval state without touching Analyze/editorial truth."""
    run_root = Path(run_root).resolve(); retrieval_root = Path(retrieval_root).resolve()
    if retrieval_root != run_root and not retrieval_root.is_relative_to(run_root):
        raise ValueError("retrieval root escapes project run")
    deleted_files = deleted_bytes = cleared = preserved = 0; failures: list[str] = []
    if retrieval_root != run_root:
        editorial_parent = run_root / "editorial"; roots: list[Path] = []
        if editorial_parent.is_dir(): roots += [p for p in editorial_parent.iterdir() if p.is_dir() and not p.is_symlink()]
        if retrieval_root not in roots: roots.append(retrieval_root)
        for root in roots:
            files, size, errors, c, p = _clean_editorial_root(root, active=root == retrieval_root)
            deleted_files += files; deleted_bytes += size; failures += errors; cleared += c; preserved += p
    else:
        cleared, preserved = _clear_selection_assets(run_root / "selection-plan.json")
        for name in sorted(_RETRIEVAL_FILES | _RETRIEVAL_DIRS):
            files, size, error = _remove_owned(run_root / name)
            deleted_files += files; deleted_bytes += size
            if error: failures.append(error)
    return {
        "deleted_files": deleted_files, "deleted_bytes": deleted_bytes,
        "cleared_selections": cleared, "preserved_decisions": preserved,
        "partial_failures": failures, "resolve_calls": 0,
    }

def clean_beat_media(run_root: Path, retrieval_root: Path, beat_id: str) -> dict[str, Any]:
    """Clear a beat's retrieval references, retaining shared downloads and analysis."""
    from .atomic_io import write_json
    from .beat_research import _target
    from .debug_run_cli import persist_video_diagnostics
    run = Path(run_root).resolve(); root = Path(retrieval_root).resolve()
    if root != run and not root.is_relative_to(run):
        raise ValueError('retrieval root escapes project run')
    def read(name, default):
        path = root / name
        if not path.resolve().is_relative_to(run):
            raise ValueError('artifact escapes project run')
        return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else default
    rows = read('online-candidates.json', [])
    retained = [r for r in rows if not _target(r, beat_id)]
    write_json(root / 'online-candidates.json', retained)
    for name in ('image-candidates.json', 'video-retrieval-plan.json', 'image-retrieval-plan.json'):
        payload = read(name, None)
        if not isinstance(payload, dict): continue
        chunks = payload.get('chunks')
        if isinstance(chunks, dict): chunks.pop(beat_id, None)
        elif isinstance(chunks, list): payload['chunks'] = [r for r in chunks if r.get('id') != beat_id and not _target(r, beat_id)]
        write_json(root / name, payload)
    selection = read('selection-plan.json', None)
    if isinstance(selection, dict):
        row = selection.get('chunks', {}).get(beat_id)
        if isinstance(row, dict): row['selected_assets'] = []
        write_json(root / 'selection-plan.json', selection)
    # Invalidate only this beat's shot-result cache. Shared provider/media caches stay.
    for path in root.rglob('verified-shots/*.json'):
        if not path.resolve().is_relative_to(run): continue
        try: cached = json.loads(path.read_text(encoding='utf-8')).get('value', {})
        except (ValueError, OSError): continue
        if isinstance(cached, dict) and _target(cached, beat_id): path.unlink()
    persist_video_diagnostics(root)
    return {'beat_id': beat_id, 'removed_video_rows': len(rows)-len(retained), 'shared_media_preserved': True}
