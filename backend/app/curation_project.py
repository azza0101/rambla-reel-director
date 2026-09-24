from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable


PROJECT_MANIFEST_VERSION = "rambla-project-1"
PROJECT_MANIFEST_NAME = "project.rambla.json"


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
        self.root, self.probe_runner = Path(root), probe_runner
        self.audio_probe_runner = audio_probe_runner or _probe_audio_duration

    def create(self, name: str) -> CurationProject:
        project = CurationProject(uuid.uuid4().hex[:12], name.strip() or "New Reel")
        self._save(project)
        return project

    def load(self, project_id: str) -> CurationProject:
        raw = json.loads(self._path(project_id).read_text(encoding="utf-8"))
        source = SourceVideoInfo(**raw["source_video"]) if raw.get("source_video") else None
        guide = GuideAudioInfo(**raw["guide_audio"]) if raw.get("guide_audio") else None
        project = CurationProject(raw["project_id"], raw["name"], source, guide)
        # Opening any pre-manifest project upgrades it in place without touching
        # transcript/retrieval artifacts or starting analysis.
        manifest = self.manifest_path(project.project_id)
        if not manifest.is_file():
            from .atomic_io import write_json
            write_json(manifest, self.manifest_payload(project))
        return project

    def manifest_path(self, project_id: str) -> Path:
        # Reuse the same validation as project.json so a crafted manifest cannot
        # escape the configured local project store.
        return self._path(project_id).parent / PROJECT_MANIFEST_NAME

    def manifest_payload(self, project: CurationProject) -> dict[str, Any]:
        project_dir = self._path(project.project_id).parent.resolve()
        return {
            "schema_version": PROJECT_MANIFEST_VERSION,
            "project_id": project.project_id,
            "name": project.name,
            "analysis_signature": project.analysis_signature,
            "project_dir": str(project_dir),
            "run_dir": str(project_dir / "run"),
            "source_video_path": project.source_video.path if project.source_video else None,
            "guide_audio_path": project.guide_audio.path if project.guide_audio else None,
        }

    def open_project_payload(self, raw: dict[str, Any]) -> tuple[CurationProject, bool]:
        """Open either the current RAMBLA manifest or a legacy project.json payload.

        The payload never creates a new project and never trusts its filesystem paths.
        It resolves only an already-saved project id from this ProjectStore, verifies
        available signatures against the authoritative local project, and writes the
        modern manifest when migrating a legacy payload.
        """
        if not isinstance(raw, dict):
            raise ValueError("unsupported RAMBLA project file")
        schema = raw.get("schema_version")
        if schema not in {None, PROJECT_MANIFEST_VERSION}:
            raise ValueError("unsupported RAMBLA project file")
        project_id = str(raw.get("project_id") or "")
        if not project_id:
            raise ValueError("RAMBLA project id is missing")
        manifest_existed = self.manifest_path(project_id).is_file()
        project = self.load(project_id)

        if schema == PROJECT_MANIFEST_VERSION:
            expected = str(raw.get("analysis_signature") or "")
            if expected and expected != project.analysis_signature:
                raise ValueError("RAMBLA project file does not match the saved local project state")
            return project, False

        # Legacy project.json: verify the strongest stable identities available.
        legacy_source = raw.get("source_video") if isinstance(raw.get("source_video"), dict) else None
        if legacy_source and project.source_video:
            expected_source_signature = str(legacy_source.get("signature") or "")
            if expected_source_signature and expected_source_signature != project.source_video.signature:
                raise ValueError("RAMBLA project file does not match the saved local project state")
        legacy_guide = raw.get("guide_audio") if isinstance(raw.get("guide_audio"), dict) else None
        if legacy_guide and project.guide_audio:
            expected_guide_signature = str(legacy_guide.get("signature") or "")
            if expected_guide_signature and expected_guide_signature != project.guide_audio.signature:
                raise ValueError("RAMBLA project file does not match the saved local project state")
        return project, not manifest_existed

    def load_manifest(self, path: Path) -> CurationProject:
        path = Path(path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        project, _migrated = self.open_project_payload(raw)
        return project

    def list_recent(self, *, limit: int = 12) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        if not self.root.exists():
            return []
        rows: list[tuple[int, dict[str, Any]]] = []
        for manifest in self.root.glob(f"*/{PROJECT_MANIFEST_NAME}"):
            try:
                raw = json.loads(manifest.read_text(encoding="utf-8"))
                if raw.get("schema_version") != PROJECT_MANIFEST_VERSION:
                    continue
                project_id = str(raw.get("project_id") or "")
                self._path(project_id)  # validate id/path
                rows.append((manifest.stat().st_mtime_ns, {**raw, "manifest_path": str(manifest.resolve())}))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
        rows.sort(key=lambda pair: pair[0], reverse=True)
        return [payload for _, payload in rows[:limit]]

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
        project = self.register_local_video(project_id, target)
        self._write_source_input(project_id, {"kind": "video", "filename": safe, "path": str(target)})
        return project

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


    def _write_source_input(self, project_id: str, payload: dict[str, Any]) -> None:
        from .atomic_io import write_json
        target = self.root / project_id / "source" / "source-input.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        write_json(target, payload)

    def source_input(self, project_id: str) -> dict[str, Any]:
        path = self.root / project_id / "source" / "source-input.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            return {"kind": "video"}
        return value if isinstance(value, dict) else {"kind": "video"}

    @staticmethod
    def _timeline_duration_for_text(text: str) -> float:
        words = re.findall(r"\\S+", str(text or ""))
        if not words:
            raise ValueError("transcript text is empty")
        return max(2.0, len(words) / 2.5)

    def _render_placeholder_video(
        self,
        target: Path,
        duration: float,
        *,
        command_runner: Callable[[list[str]], Any] = subprocess.run,
    ) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        command_runner([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"color=c=black:s=360x640:r=25:d={max(0.5, float(duration)):.3f}",
            "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(target),
        ])
        if not target.is_file():
            raise RuntimeError("ffmpeg did not create the synthetic timeline video")

    def write_primary_audio(
        self,
        project_id: str,
        filename: str,
        chunks: Any,
        *,
        command_runner: Callable[[list[str]], Any] = subprocess.run,
    ) -> CurationProject:
        self.load(project_id)
        safe = Path(filename).name or "source-audio"
        source = self.root / project_id / "source" / ("audio-" + safe)
        source.parent.mkdir(parents=True, exist_ok=True)
        total = 0
        with source.open("wb") as handle:
            for chunk in chunks:
                total += len(chunk)
                if total > 1024**3:
                    raise ValueError("audio upload exceeds 1 GiB")
                handle.write(chunk)
        guide_path = source.parent / "guide-audio.wav"
        command_runner([
            "ffmpeg", "-y", "-i", str(source),
            "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(guide_path),
        ])
        duration = float(self.audio_probe_runner(guide_path))
        timeline = source.parent / "audio-timeline.mp4"
        self._render_placeholder_video(timeline, duration, command_runner=command_runner)
        project = self.register_local_video(project_id, timeline)
        stat = source.stat()
        guide_signature = hashlib.sha256(
            f"primary-audio|{source.name}|{stat.st_size}|{stat.st_mtime_ns}".encode()
        ).hexdigest()
        guide = GuideAudioInfo(
            str(guide_path), "external", project.source_video.signature if project.source_video else "",
            guide_signature, duration,
        )
        project = CurationProject(project.project_id, project.name, project.source_video, guide)
        self._save(project)
        self._write_source_input(project_id, {
            "kind": "audio",
            "filename": safe,
            "original_path": str(source),
            "duration": duration,
        })
        return project

    def write_text_source(
        self,
        project_id: str,
        text: str,
        *,
        command_runner: Callable[[list[str]], Any] = subprocess.run,
    ) -> CurationProject:
        clean = " ".join(str(text or "").split())
        if not clean:
            raise ValueError("transcript text is empty")
        if len(clean) > 500_000:
            raise ValueError("transcript text exceeds 500,000 characters")
        source_dir = self.root / project_id / "source"
        source_dir.mkdir(parents=True, exist_ok=True)
        text_path = source_dir / "source-text.txt"
        text_path.write_text(clean, encoding="utf-8")
        duration = self._timeline_duration_for_text(clean)
        timeline = source_dir / "text-timeline.mp4"
        self._render_placeholder_video(timeline, duration, command_runner=command_runner)
        project = self.register_local_video(project_id, timeline)
        self._write_source_input(project_id, {
            "kind": "text",
            "filename": "source-text.txt",
            "text_path": str(text_path),
            "duration": duration,
        })
        return project

    def _path(self, project_id: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{12}", project_id):
            raise ValueError("invalid project id")
        return self.root / project_id / "project.json"

    def _save(self, project: CurationProject) -> None:
        path = self._path(project.project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        from .atomic_io import write_json
        write_json(path, asdict(project))
        write_json(self.manifest_path(project.project_id), self.manifest_payload(project))


def _probe_audio_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(result.stdout.strip())
