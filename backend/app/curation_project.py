from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class SourceVideoInfo:
    path: str
    duration: float
    fps: float
    width: int
    height: int
    has_audio: bool
    signature: str


@dataclass(frozen=True, slots=True)
class GuideAudioInfo:
    path: str
    mode: str
    source_signature: str
    signature: str = ""
    duration: float = 0.0


@dataclass(frozen=True, slots=True)
class CurationProject:
    project_id: str
    name: str
    source_video: SourceVideoInfo | None = None
    guide_audio: GuideAudioInfo | None = None

    @property
    def analysis_signature(self) -> str:
        source = self.source_video.signature if self.source_video else ""
        guide = self.guide_audio.signature if self.guide_audio else ""
        return hashlib.sha256(f"{source}|{guide}".encode()).hexdigest()

    @property
    def guide_duration_warning(self) -> str | None:
        if not self.source_video or not self.guide_audio or not self.guide_audio.duration:
            return None
        difference = abs(self.source_video.duration - self.guide_audio.duration)
        if difference <= max(0.5, self.source_video.duration * 0.02):
            return None
        return f"Guide audio differs from source timeline by {difference:.2f}s"


class ProjectStore:
    def __init__(self, root: Path, *, probe_runner: Callable[[Path], dict[str, Any]], audio_probe_runner: Callable[[Path], float] | None = None) -> None:
        self.root, self.probe_runner = root, probe_runner
        self.audio_probe_runner = audio_probe_runner or _probe_audio_duration

    def create(self, name: str) -> CurationProject:
        project = CurationProject(uuid.uuid4().hex[:12], name.strip() or "New Reel")
        self._save(project)
        return project

    def load(self, project_id: str) -> CurationProject:
        raw = json.loads(self._path(project_id).read_text(encoding="utf-8"))
        source = SourceVideoInfo(**raw["source_video"]) if raw.get("source_video") else None
        guide = GuideAudioInfo(**raw["guide_audio"]) if raw.get("guide_audio") else None
        return CurationProject(raw["project_id"], raw["name"], source, guide)

    def register_local_video(self, project_id: str, source: Path) -> CurationProject:
        source = source.resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        data = self.probe_runner(source)
        stat = source.stat()
        signature = hashlib.sha256(f"{source}|{stat.st_size}|{stat.st_mtime_ns}".encode()).hexdigest()
        current = self.load(project_id)
        guide = current.guide_audio
        if guide and guide.mode == "original" and guide.source_signature != signature:
            guide = None
        project = CurationProject(current.project_id, current.name, SourceVideoInfo(str(source), float(data["duration"]), float(data["fps"]), int(data["width"]), int(data["height"]), bool(data["has_audio"]), signature), guide)
        self._save(project)
        return project

    def extract_source_audio(self, project_id: str, *, command_runner: Callable[[list[str]], Any] = subprocess.run) -> GuideAudioInfo:
        project = self.load(project_id)
        if project.source_video is None or not project.source_video.has_audio:
            raise ValueError("source audio unavailable")
        target = self.root / project_id / "source" / "guide-audio.wav"
        if project.guide_audio and project.guide_audio.mode == "original" and project.guide_audio.source_signature == project.source_video.signature and target.is_file():
            return project.guide_audio
        target.parent.mkdir(parents=True, exist_ok=True)
        command_runner(["ffmpeg", "-y", "-i", project.source_video.path, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(target)])
        signature = hashlib.sha256(f"original|{project.source_video.signature}".encode()).hexdigest()
        guide = GuideAudioInfo(str(target), "original", project.source_video.signature, signature, self.audio_probe_runner(target))
        self._save(CurationProject(project.project_id, project.name, project.source_video, guide))
        return guide

    def write_uploaded_video(self, project_id: str, filename: str, chunks: Any, *, max_bytes: int = 5 * 1024**3) -> CurationProject:
        safe = Path(filename).name or "source-video"
        target = self.root / project_id / "source" / safe
        target.parent.mkdir(parents=True, exist_ok=True)
        total = 0
        with target.open("wb") as handle:
            for chunk in chunks:
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError("source upload exceeds 5 GiB")
                handle.write(chunk)
        return self.register_local_video(project_id, target)

    def write_external_guide_audio(self, project_id: str, filename: str, chunks: Any, *, command_runner: Callable[[list[str]], Any] = subprocess.run) -> GuideAudioInfo:
        project = self.load(project_id)
        source = self.root / project_id / "source" / ("external-" + (Path(filename).name or "guide-audio"))
        source.parent.mkdir(parents=True, exist_ok=True)
        with source.open("wb") as handle:
            for chunk in chunks:
                handle.write(chunk)
        target = source.parent / "guide-audio.wav"
        command_runner(["ffmpeg", "-y", "-i", str(source), "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(target)])
        stat = source.stat()
        signature = hashlib.sha256(f"external|{source.name}|{stat.st_size}|{stat.st_mtime_ns}".encode()).hexdigest()
        guide = GuideAudioInfo(str(target), "external", project.source_video.signature if project.source_video else "", signature, self.audio_probe_runner(target))
        self._save(CurationProject(project.project_id, project.name, project.source_video, guide))
        return guide

    def _path(self, project_id: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{12}", project_id):
            raise ValueError("invalid project id")
        return self.root / project_id / "project.json"

    def _save(self, project: CurationProject) -> None:
        path = self._path(project.project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(project), indent=2), encoding="utf-8")


def _probe_audio_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(result.stdout.strip())
