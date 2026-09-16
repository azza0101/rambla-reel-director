"""Safe local project-library and storage maintenance helpers.

This module owns recursive filesystem operations so API/UI code never performs
ad-hoc deletion or disk accounting. All paths are derived from a validated
ProjectStore project id and are constrained to the configured project root.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
from typing import Any

from .curation_project import CurationProject, ProjectStore


def _project_dir(store: ProjectStore, project_id: str) -> Path:
    # ProjectStore._path is the authoritative id validator (12 lowercase hex).
    directory = store._path(project_id).parent.resolve()
    root = store.root.resolve()
    if directory == root or not directory.is_relative_to(root):
        raise ValueError("project path escapes project root")
    return directory


def _walk_stats(root: Path) -> tuple[int, int, int]:
    """Return bytes, file count and newest mtime_ns without following symlinks."""
    total = 0
    files = 0
    newest = 0
    if not root.exists():
        return total, files, newest
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    try:
                        stat = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    newest = max(newest, int(stat.st_mtime_ns))
                    if entry.is_symlink():
                        files += 1
                        total += int(stat.st_size)
                    elif entry.is_dir(follow_symlinks=False):
                        stack.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        files += 1
                        total += int(stat.st_size)
        except OSError:
            continue
    return total, files, newest


def _candidate_count(project_dir: Path) -> int:
    count = 0
    run = project_dir / "run"
    if not run.is_dir():
        return 0
    for path in run.rglob("online-candidates.json"):
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(rows, list):
                count += sum(len(row.get("candidates") or []) for row in rows if isinstance(row, dict))
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    for path in run.rglob("image-candidates.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            chunks = payload.get("chunks", {}) if isinstance(payload, dict) else {}
            count += sum(len(row.get("candidates") or []) for row in chunks.values() if isinstance(row, dict))
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    return count


def project_library_rows(store: ProjectStore) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not store.root.exists():
        return rows
    for directory in store.root.iterdir():
        if not directory.is_dir() or directory.is_symlink():
            continue
        project_id = directory.name
        try:
            project = store.load(project_id)
            project_dir = _project_dir(store, project_id)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
        size_bytes, file_count, newest_ns = _walk_stats(project_dir)
        run = project_dir / "run"
        source_filename = Path(project.source_video.path).name if project.source_video else None
        rows.append({
            "project_id": project.project_id,
            "name": project.name,
            "source_filename": source_filename,
            "size_bytes": size_bytes,
            "file_count": file_count,
            "modified_at": datetime.fromtimestamp(newest_ns / 1_000_000_000, tz=timezone.utc).isoformat() if newest_ns else None,
            "modified_ns": newest_ns,
            "has_transcript": (run / "transcript-raw.json").is_file(),
            "has_editorial_plan": (run / "visual-plan.json").is_file(),
            "retrieved_media_count": _candidate_count(project_dir),
        })
    rows.sort(key=lambda row: (int(row.get("modified_ns") or 0), str(row["project_id"])), reverse=True)
    for row in rows:
        row.pop("modified_ns", None)
    return rows


def rename_project(store: ProjectStore, project_id: str, name: str) -> CurationProject:
    clean = " ".join(str(name or "").split())
    if not clean:
        raise ValueError("project name must not be empty")
    if len(clean) > 120:
        raise ValueError("project name must be at most 120 characters")
    current = store.load(project_id)
    renamed = CurationProject(current.project_id, clean, current.source_video, current.guide_audio)
    store._save(renamed)
    return renamed


def delete_project_tree(store: ProjectStore, project_id: str) -> dict[str, Any]:
    directory = _project_dir(store, project_id)
    # Requiring the authoritative project.json prevents deletion of arbitrary
    # 12-hex directories that merely happen to live below the root.
    store.load(project_id)
    deleted_bytes, deleted_files, _ = _walk_stats(directory)
    shutil.rmtree(directory)
    return {
        "project_id": project_id,
        "deleted_bytes": deleted_bytes,
        "deleted_files": deleted_files,
        "resolve_calls": 0,
    }


_RETRIEVAL_FILES = {
    "online-candidates.json",
    "video-sourcing-diagnostics.json",
    "image-candidates.json",
    "video-retrieval-plan.json",
    "image-retrieval-plan.json",
    "online-sourcing-benchmark.json",
    "candidate-metrics.json",
    "coverage-metrics.json",
    "video-sourcing.json",
    "image-sourcing.json",
    "edit-plan.json",
    "review.html",
    "transcript-normalized.json",  # retrieval-root copy, not run-level source of truth
    "semantic-beats.json",         # retrieval-root copy
    "transcript-raw.json",        # retrieval-root copy
}
_RETRIEVAL_DIRS = {
    "asset-cache", "image-cache", "quality-clips", "preview-cache", "media-cache"
}


def _remove_owned(path: Path) -> tuple[int, int, str | None]:
    """Remove one owned retrieval path and report files/bytes/error."""
    try:
        if path.is_symlink() or path.is_file():
            try:
                size = int(path.lstat().st_size)
            except OSError:
                size = 0
            path.unlink()
            return 1, size, None
        if path.is_dir():
            size, files, _ = _walk_stats(path)
            shutil.rmtree(path)
            return files, size, None
        return 0, 0, None
    except OSError as exc:
        return 0, 0, f"{path}: {type(exc).__name__}: {exc}"


def _clear_selection_assets(selection_path: Path) -> tuple[int, int]:
    if not selection_path.is_file():
        return 0, 0
    try:
        payload = json.loads(selection_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return 0, 0
    chunks = payload.get("chunks") if isinstance(payload, dict) else None
    if not isinstance(chunks, dict):
        return 0, 0
    cleared = 0
    preserved = 0
    for row in chunks.values():
        if not isinstance(row, dict):
            continue
        if row.get("no_broll") is True or row.get("action") == "CONTINUE_PREVIOUS_VISUAL":
            preserved += 1
            continue
        selected = row.get("selected_assets")
        if isinstance(selected, list) and selected:
            cleared += len(selected)
            row["selected_assets"] = []
    from .atomic_io import write_json
    write_json(selection_path, payload)
    return cleared, preserved


def _clean_editorial_root(root: Path, *, active: bool) -> tuple[int, int, list[str], int, int]:
    deleted_files = 0
    deleted_bytes = 0
    failures: list[str] = []
    cleared = 0
    preserved = 0
    if not root.is_dir():
        return deleted_files, deleted_bytes, failures, cleared, preserved
    if active:
        cleared, preserved = _clear_selection_assets(root / "selection-plan.json")
    # Editorial digest roots contain an immutable imported-plan snapshot plus
    # disposable retrieval products. Preserve selection-plan after sanitizing it.
    for child in list(root.iterdir()):
        if child.name in {"imported-plan.json", "selection-plan.json"}:
            continue
        files, size, error = _remove_owned(child)
        deleted_files += files
        deleted_bytes += size
        if error:
            failures.append(error)
    return deleted_files, deleted_bytes, failures, cleared, preserved


def clean_project_media(run_root: Path, retrieval_root: Path) -> dict[str, Any]:
    """Delete regenerable retrieval media while preserving analysis/editorial state.

    Imported-plan digest directories are cleaned wholesale except for their plan
    snapshot and sanitized selection plan. If no imported-plan root is active,
    only a strict retrieval allowlist is removed from the run root.
    """
    run_root = Path(run_root).resolve()
    retrieval_root = Path(retrieval_root).resolve()
    if retrieval_root != run_root and not retrieval_root.is_relative_to(run_root):
        raise ValueError("retrieval root escapes project run")

    deleted_files = 0
    deleted_bytes = 0
    failures: list[str] = []
    cleared = 0
    preserved = 0

    editorial_parent = run_root / "editorial"
    if retrieval_root != run_root:
        roots: list[Path] = []
        if editorial_parent.is_dir():
            roots.extend(path for path in editorial_parent.iterdir() if path.is_dir() and not path.is_symlink())
        if retrieval_root not in roots:
            roots.append(retrieval_root)
        for root in roots:
            files, size, errors, c, p = _clean_editorial_root(root, active=root == retrieval_root)
            deleted_files += files; deleted_bytes += size; failures.extend(errors)
            cleared += c; preserved += p
    else:
        cleared, preserved = _clear_selection_assets(run_root / "selection-plan.json")
        for name in sorted(_RETRIEVAL_FILES | _RETRIEVAL_DIRS):
            path = run_root / name
            files, size, error = _remove_owned(path)
            deleted_files += files; deleted_bytes += size
            if error:
                failures.append(error)

    return {
        "deleted_files": deleted_files,
        "deleted_bytes": deleted_bytes,
        "cleared_selections": cleared,
        "preserved_decisions": preserved,
        "partial_failures": failures,
        "resolve_calls": 0,
    }
