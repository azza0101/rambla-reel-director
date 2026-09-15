"""Offline FFmpeg adapter for inspectable, independently classified reel fingerprints."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Callable, Mapping

from .style_fingerprint import VisualInterval, build_style_fingerprint

Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]
Classifier = Callable[[Path, float, float], Mapping[str, object]]


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=True)


def analyze_reference(
    media: Path, output_dir: Path, *, exemplar_id: str,
    runner: Runner = _run, classifier: Classifier | None = None,
) -> dict:
    """Probe/cut locally; unknown states remain explicitly unclassified."""
    if not media.is_file():
        raise FileNotFoundError(media)
    output_dir.mkdir(parents=True, exist_ok=True)
    probe = runner([
        "ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height,r_frame_rate",
        "-of", "json", str(media),
    ])
    info = json.loads(probe.stdout)
    duration = float(info["format"]["duration"])
    if duration <= 0:
        raise ValueError("reference duration must be positive")
    cut_run = runner([
        "ffmpeg", "-hide_banner", "-i", str(media), "-vf", "select='gt(scene,0.30)',showinfo",
        "-an", "-f", "null", "-",
    ])
    cuts = sorted({float(value) for value in re.findall(r"pts_time:([0-9]+(?:\.[0-9]+)?)", cut_run.stderr)
                   if 0 < float(value) < duration})
    edges = [0.0, *cuts, duration]
    manifest = []
    intervals = []
    for index, (start, end) in enumerate(zip(edges, edges[1:])):
        frame = output_dir / f"frame-{index:04d}.jpg"
        runner([
            "ffmpeg", "-hide_banner", "-ss", str((start + end) / 2), "-i", str(media),
            "-frames:v", "1", "-y", str(frame),
        ])
        classified = classifier(frame, start, end) if classifier else {}
        interval = VisualInterval(
            start, end, str(classified.get("route") or "UNCLASSIFIED"),
            str(classified.get("presentation") or "UNCLASSIFIED"),
            str(classified.get("media_kind") or "video"),
            float(classified.get("confidence", 0.0)),
        )
        intervals.append(interval)
        manifest.append({"frame": str(frame), "start_seconds": start, "end_seconds": end,
                         "classification": classified})
    fingerprint = build_style_fingerprint(exemplar_id=exemplar_id, duration_seconds=duration,
                                          intervals=intervals)
    payload = fingerprint.to_dict()
    (output_dir / "style-fingerprint.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "representative-frames.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect one reference reel without modifying it")
    parser.add_argument("media", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--exemplar-id", required=True)
    args = parser.parse_args()
    analyze_reference(args.media, args.output_dir, exemplar_id=args.exemplar_id)


if __name__ == "__main__":
    main()
