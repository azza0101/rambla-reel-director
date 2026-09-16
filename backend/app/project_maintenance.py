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
