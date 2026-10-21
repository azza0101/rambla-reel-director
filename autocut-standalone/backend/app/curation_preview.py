from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .curation import CurationCandidate


@dataclass(frozen=True, slots=True)
class PreviewResult:
    status: str
    preview_path: str | None = None
    poster_path: str | None = None
    cache_hit: bool = False
    error: str | None = None


class CurationPreviewMaterializer:
    def __init__(self, cache_dir: Path, *, command_runner: Callable[[list[str]], object]) -> None:
        self.cache_dir, self.command_runner = cache_dir, command_runner

    def materialize(self, candidate: CurationCandidate) -> PreviewResult:
        if candidate.kind != "video" or not candidate.local_asset_path:
            return PreviewResult("error", error="preview_unavailable")
        key = hashlib.sha256(f"{candidate.asset_id}|{candidate.source_page}|0.1".encode()).hexdigest()
        preview = self.cache_dir / f"{key}.mp4"; poster = self.cache_dir / f"{key}.jpg"
        if preview.is_file() and poster.is_file(): return PreviewResult("ready", str(preview), str(poster), True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.command_runner(["ffmpeg","-y","-ss","0","-i",candidate.local_asset_path,"-t","3.5","-vf","scale='min(480,iw)':-2","-an","-c:v","libx264","-preset","veryfast","-crf","28","-movflags","+faststart",str(preview)])
            self.command_runner(["ffmpeg","-y","-ss","0.2","-i",str(preview),"-frames:v","1","-q:v","3",str(poster)])
            return PreviewResult("ready",str(preview),str(poster))
        except Exception:
            return PreviewResult("error",error="preview_unavailable")
