"""Validated local library for DaVinci Resolve Fusion Title packages."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from typing import BinaryIO
import zipfile


DEFAULT_MAX_BYTES = 64 * 1024 * 1024


class TemplateValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ResolveTitleTemplate:
    template_id: str
    display_name: str
    resolve_name: str
    original_filename: str
    size_bytes: int
    sha256: str
    setting_path: str
    source_path: Path
    bundled: bool = False


@dataclass(frozen=True)
class InstallResult:
    status: str
    destination: Path


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def inspect_drfx(path: Path, *, bundled: bool = False) -> ResolveTitleTemplate:
    path = Path(path)
    try:
        with zipfile.ZipFile(path) as archive:
            settings = []
            for info in archive.infolist():
                raw = info.filename.replace("\\", "/")
                member = PurePosixPath(raw)
                if raw.startswith("/") or re.match(r"^[A-Za-z]:", raw) or ".." in member.parts:
                    raise TemplateValidationError("DRFX contains an unsafe path")
                if len(member.parts) >= 4 and member.parts[:2] == ("Edit", "Titles") and raw.casefold().endswith(".setting"):
                    settings.append(raw)
    except TemplateValidationError:
        raise
    except (OSError, zipfile.BadZipFile) as exc:
        raise TemplateValidationError("file is not a valid DRFX package") from exc
    if len(settings) != 1:
        raise TemplateValidationError("DRFX must contain exactly one Fusion Title setting")
    digest = _digest(path)
    resolve_name = PurePosixPath(settings[0]).stem
    return ResolveTitleTemplate(
        template_id=f"sha256-{digest}",
        display_name=resolve_name.replace("_", " "),
        resolve_name=resolve_name,
        original_filename=path.name,
        size_bytes=path.stat().st_size,
        sha256=digest,
        setting_path=settings[0],
        source_path=path,
        bundled=bundled,
    )


def template_library(root: Path, bundled_root: Path) -> list[ResolveTitleTemplate]:
    rows: dict[str, ResolveTitleTemplate] = {}
    for folder, bundled in ((Path(bundled_root), True), (Path(root), False)):
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.drfx")):
            try:
                row = inspect_drfx(path, bundled=bundled)
            except TemplateValidationError:
                continue
            rows.setdefault(row.template_id, row)
    return sorted(rows.values(), key=lambda row: (not row.bundled, row.display_name.casefold()))


def store_uploaded_drfx(
    source: BinaryIO,
    filename: str,
    root: Path,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> ResolveTitleTemplate:
    safe_name = Path(filename or "template.drfx").name
    if not safe_name.casefold().endswith(".drfx"):
        raise TemplateValidationError("upload must be a .drfx file")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    handle, raw_temp = tempfile.mkstemp(prefix=".upload-", suffix=".drfx", dir=root)
    temp = Path(raw_temp)
    total = 0
    try:
        with os.fdopen(handle, "wb") as output:
            while True:
                block = source.read(1024 * 1024)
                if not block:
                    break
                total += len(block)
                if total > max_bytes:
                    raise TemplateValidationError("DRFX upload is too large")
                output.write(block)
        inspected = inspect_drfx(temp)
        destination = root / safe_name
        if destination.exists() and _digest(destination) != inspected.sha256:
            destination = root / f"{Path(safe_name).stem}-{inspected.sha256[:12]}.drfx"
        os.replace(temp, destination)
        return inspect_drfx(destination)
    finally:
        temp.unlink(missing_ok=True)


def install_template(template: ResolveTitleTemplate, resolve_root: Path) -> InstallResult:
    if not template.source_path.is_file():
        raise TemplateValidationError("template library file is missing")
    resolve_root = Path(resolve_root)
    resolve_root.mkdir(parents=True, exist_ok=True)
    destination = resolve_root / template.original_filename
    if destination.exists():
        if _digest(destination) == template.sha256:
            pass
        else:
            destination = resolve_root / f"{Path(template.original_filename).stem}-{template.sha256[:12]}.drfx"
    package_ready = destination.is_file() and _digest(destination) == template.sha256
    if not package_ready:
        handle, raw_temp = tempfile.mkstemp(prefix=".install-", suffix=".drfx", dir=resolve_root)
        os.close(handle)
        temp = Path(raw_temp)
        try:
            shutil.copyfile(template.source_path, temp)
            os.replace(temp, destination)
        finally:
            temp.unlink(missing_ok=True)

    relative_folder = Path(*PurePosixPath(template.setting_path).parent.parts)
    extracted = resolve_root / relative_folder
    marker = extracted / ".rambla-template-sha256"
    extracted_ready = (
        (resolve_root / Path(*PurePosixPath(template.setting_path).parts)).is_file()
        and marker.is_file()
        and marker.read_text(encoding="ascii").strip() == template.sha256
    )
    if extracted_ready:
        return InstallResult("installed", destination)

    staging = Path(tempfile.mkdtemp(prefix=".extract-", dir=resolve_root))
    try:
        with zipfile.ZipFile(template.source_path) as archive:
            archive.extractall(staging)
        staged_title = staging / relative_folder
        if not (staging / Path(*PurePosixPath(template.setting_path).parts)).is_file():
            raise TemplateValidationError("DRFX title setting disappeared during extraction")
        extracted.parent.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(extracted, ignore_errors=True)
        shutil.copytree(staged_title, extracted)
        marker.write_text(template.sha256, encoding="ascii")
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return InstallResult("restart_required", destination)


def template_install_status(template: ResolveTitleTemplate, resolve_root: Path) -> str:
    """Report file-level installation; Resolve runtime readiness is verified separately."""
    resolve_root = Path(resolve_root)
    direct = resolve_root / template.original_filename
    digest_name = resolve_root / f"{Path(template.original_filename).stem}-{template.sha256[:12]}.drfx"
    package_ready = False
    for candidate in (direct, digest_name):
        try:
            if candidate.is_file() and _digest(candidate) == template.sha256:
                package_ready = True
                break
        except OSError:
            continue
    relative_setting = Path(*PurePosixPath(template.setting_path).parts)
    extracted = resolve_root / relative_setting
    marker = extracted.parent / ".rambla-template-sha256"
    try:
        extracted_ready = extracted.is_file() and marker.read_text(encoding="ascii").strip() == template.sha256
    except OSError:
        extracted_ready = False
    return "installed" if package_ready and extracted_ready else "not_installed"
