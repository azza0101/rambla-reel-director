"""Small, versioned backups of RAMBLA editorial state (never source media)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import uuid
import zipfile


STATE_SUFFIXES = {".json", ".srt", ".txt", ".csv", ".xml"}
SKIP_PARTS = {"resolve-media", "media", "source-video", "source-audio", "previews", "cache"}


def backup_project_state(project_root: Path, backup_root: Path, *, keep: int = 20) -> Path:
    project_root = Path(project_root).resolve()
    if not project_root.is_dir():
        raise FileNotFoundError(project_root)
    target_dir = Path(backup_root).resolve() / project_root.name
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    target = target_dir / f"{stamp}-{uuid.uuid4().hex[:8]}.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(project_root.rglob("*")):
            relative = path.relative_to(project_root)
            if (not path.is_file() or path.suffix.casefold() not in STATE_SUFFIXES
                    or any(part.casefold() in SKIP_PARTS for part in relative.parts)
                    or path.stat().st_size > 10 * 1024 * 1024):
                continue
            archive.write(path, relative.as_posix())
    archives = sorted(target_dir.glob("*.zip"), key=lambda path: path.stat().st_mtime_ns, reverse=True)
    for stale in archives[max(1, keep):]:
        stale.unlink(missing_ok=True)
    return target
