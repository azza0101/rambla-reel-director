"""Bounded acquisition helpers for long online video sources.

The acquisition layer is deliberately provider-agnostic at the plan boundary:
it receives an explicit source URL and time range, fetches a slightly wider
window when needed, and lets a local FFmpeg pass trim precisely enough for the
editorial slot.  Raw command output/URLs are never included in durable errors.
"""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit


ProcessRunner = Callable[[list[str]], None]


class AcquisitionError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"acquisition:{code}: {message}")


@dataclass(frozen=True, slots=True)
class AcquisitionRequest:
    source_url: str
    start_seconds: float
    end_seconds: float
    margin_seconds: float = 2.0
    mode: str = "video_window"

    def __post_init__(self) -> None:
        try:
            parsed = urlsplit(self.source_url)
        except ValueError as exc:
            raise ValueError("source URL must be public http/https") from exc
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("source URL must be public http/https")
        if self.start_seconds < 0 or self.end_seconds <= self.start_seconds:
            raise ValueError("acquisition time range is invalid")
        if self.margin_seconds < 0:
            raise ValueError("acquisition margin must be non-negative")
        if self.mode not in {"video_window", "still"}:
            raise ValueError("unsupported acquisition mode")


@dataclass(frozen=True, slots=True)
class AcquiredArtifact:
    path: Path
    kind: str
    source_start_seconds: float
    source_end_seconds: float
    sha256: str
    cache_hit: bool = False


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _default_runner(cmd: list[str]) -> None:
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except (OSError, subprocess.SubprocessError) as exc:
        raise AcquisitionError("process_failed", type(exc).__name__) from exc


class YtDlpAcquisitionAdapter:
    """Build and execute a bounded yt-dlp section request.

    The adapter intentionally does not ask yt-dlp for frame-perfect cuts.  It
    downloads a bounded window with margin; a later local FFmpeg trim can make
    the useful editorial range precise without fetching the entire source.
    """

    def __init__(self, *, runner: ProcessRunner | None = None, executable: str = "yt-dlp"):
        self.runner = runner or _default_runner
        self.executable = executable

    def build_command(self, request: AcquisitionRequest, output_path: Path) -> list[str]:
        if request.mode != "video_window":
            raise ValueError("yt-dlp bounded acquisition requires video_window mode")
        fetch_start = max(0.0, request.start_seconds - request.margin_seconds)
        fetch_end = request.end_seconds + request.margin_seconds
        section = f"*{fetch_start:.3f}-{fetch_end:.3f}"
        return [
            self.executable,
            "--no-playlist",
            "--download-sections",
            section,
            "--merge-output-format",
            "mp4",
            "-o",
            str(output_path),
            request.source_url,
        ]

    def acquire(self, request: AcquisitionRequest, output_path: Path) -> AcquiredArtifact:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.runner(self.build_command(request, output_path))
        except AcquisitionError:
            raise
        except Exception as exc:
            # Never propagate runner output or a potentially signed source URL.
            raise AcquisitionError("process_failed", type(exc).__name__) from exc
        if not output_path.is_file() or output_path.stat().st_size <= 0:
            raise AcquisitionError("output_missing", "bounded downloader produced no media")
        return AcquiredArtifact(
            path=output_path,
            kind="video_window",
            source_start_seconds=request.start_seconds,
            source_end_seconds=request.end_seconds,
            sha256=_sha256_file(output_path),
            cache_hit=False,
        )


def build_ffmpeg_trim_command(
    input_path: Path,
    output_path: Path,
    *,
    start_seconds: float,
    end_seconds: float,
    executable: str = "ffmpeg",
) -> list[str]:
    if start_seconds < 0 or end_seconds <= start_seconds:
        raise ValueError("trim time range is invalid")
    return [
        executable,
        "-y",
        "-ss",
        f"{start_seconds:.3f}",
        "-to",
        f"{end_seconds:.3f}",
        "-i",
        str(Path(input_path)),
        "-c",
        "copy",
        str(Path(output_path)),
    ]


def trim_with_ffmpeg(
    input_path: Path,
    output_path: Path,
    *,
    start_seconds: float,
    end_seconds: float,
    runner: ProcessRunner | None = None,
) -> Path:
    input_path = Path(input_path)
    output_path = Path(output_path)
    if not input_path.is_file():
        raise ValueError("trim input does not exist")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        (runner or _default_runner)(
            build_ffmpeg_trim_command(
                input_path,
                output_path,
                start_seconds=start_seconds,
                end_seconds=end_seconds,
            )
        )
    except AcquisitionError:
        raise
    except Exception as exc:
        raise AcquisitionError("trim_failed", type(exc).__name__) from exc
    if not output_path.is_file() or output_path.stat().st_size <= 0:
        raise AcquisitionError("trim_output_missing", "FFmpeg produced no media")
    return output_path
