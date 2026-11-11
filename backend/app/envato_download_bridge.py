"""Associate user-initiated Envato downloads with RAMBLA candidates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
from typing import Any
import zipfile


VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm", ".mxf"}
DOWNLOAD_SUFFIXES = VIDEO_SUFFIXES | {".zip"}


def default_downloads_dir() -> Path:
    configured = str(__import__("os").environ.get("RAMBLA_DOWNLOADS_DIR") or "").strip()
    return Path(configured) if configured else Path.home() / "Downloads"


def capture_snapshot(downloads: Path) -> dict[str, tuple[int, int]]:
    root = Path(downloads)
    if not root.is_dir():
        return {}
    output: dict[str, tuple[int, int]] = {}
    for path in root.iterdir():
        if not path.is_file() or path.suffix.casefold() not in DOWNLOAD_SUFFIXES:
            continue
        try:
            stat = path.stat()
            output[str(path.resolve())] = (int(stat.st_size), int(stat.st_mtime_ns))
        except OSError:
            continue
    return output


def _new_downloads(downloads: Path, baseline: dict[str, tuple[int, int]]) -> list[Path]:
    rows = []
    for raw, facts in capture_snapshot(downloads).items():
        path = Path(raw)
        if facts[0] <= 0 or baseline.get(raw) == facts:
            continue
        rows.append(path)
    return sorted(rows, key=lambda path: path.stat().st_mtime_ns, reverse=True)


def _safe_video_members(package: Path) -> list[zipfile.ZipInfo]:
    with zipfile.ZipFile(package) as archive:
        rows = []
        for member in archive.infolist():
            parts = PurePosixPath(member.filename).parts
            if member.is_dir() or not parts or any(part in {"", ".", ".."} for part in parts):
                continue
            if PurePosixPath(member.filename).suffix.casefold() in VIDEO_SUFFIXES:
                rows.append(member)
        return sorted(rows, key=lambda row: row.file_size, reverse=True)


def _materialize(source: Path, destination_dir: Path) -> Path | None:
    destination_dir.mkdir(parents=True, exist_ok=True)
    if source.suffix.casefold() in VIDEO_SUFFIXES:
        target = destination_dir / ("original" + source.suffix.casefold())
        shutil.copy2(source, target)
        return target
    if source.suffix.casefold() == ".zip":
        members = _safe_video_members(source)
        if not members:
            return None
        member = members[0]
        target = destination_dir / ("original" + PurePosixPath(member.filename).suffix.casefold())
        with zipfile.ZipFile(source) as archive, archive.open(member) as incoming, target.open("wb") as outgoing:
            shutil.copyfileobj(incoming, outgoing)
        return target
    return None


def load_registry(run_root: Path) -> dict[str, Any]:
    path = Path(run_root) / "envato-downloads.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        payload = {}
    assets = payload.get("assets") if isinstance(payload, dict) else None
    return {"schema_version": "rambla-envato-downloads-1", "assets": assets if isinstance(assets, dict) else {}}


def adopt_new_download(
    downloads: Path,
    baseline: dict[str, tuple[int, int]],
    run_root: Path,
    asset_id: str,
) -> dict[str, Any]:
    candidates = _new_downloads(Path(downloads), baseline)
    if not candidates:
        return {"status": "waiting", "asset_id": asset_id}
    token = hashlib.sha256(str(asset_id).encode("utf-8")).hexdigest()[:20]
    for source in candidates:
        try:
            target = _materialize(source, Path(run_root) / "envato-media" / token)
        except (OSError, zipfile.BadZipFile):
            continue
        if target is None or not target.is_file() or target.stat().st_size <= 0:
            continue
        from .envato_light_media import prepare_light_media
        from .atomic_io import write_json
        try:
            light = prepare_light_media(target, Path(run_root) / "envato-media" / token)
        except Exception as exc:
            return {"status": "error", "asset_id": asset_id, "detail": "Impossibile creare la copia leggera Envato: " + str(exc)[:250]}
        registry = load_registry(run_root)
        registry["assets"][str(asset_id)] = {
            "media_path": str(light.resolve()),
            "download_source": str(source.resolve()),
        }
        write_json(Path(run_root) / "envato-downloads.json", registry)
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
        return {"status": "ready", "asset_id": asset_id, "media_path": str(light.resolve())}
    return {"status": "waiting", "asset_id": asset_id}
