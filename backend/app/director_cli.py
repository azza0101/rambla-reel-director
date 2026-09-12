"""Persist a Resolve-independent Director run from explicit local artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .director_engine import FasterWhisperArtifact, build_edit_plan
from .director_preview import render_report


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def run_from_artifacts(transcript_path: Path, outline_path: Path, manifest_path: Path,
                       output_dir: Path, *, source_frames: int) -> dict[str, Any]:
    transcript = FasterWhisperArtifact(transcript_path).load()
    outline = json.loads(outline_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    client_id = manifest["client_id"]
    if not client_id or not isinstance(manifest["assets"], list):
        raise ValueError("client-scoped asset manifest required")
    for asset in manifest["assets"]:
        if asset["client_id"] != client_id:
            raise ValueError("manifest mixes client assets")
        if not Path(asset["path"]).is_file():
            raise ValueError(f"manifest asset does not exist: {asset['id']}")
    normalized = dict(transcript)
    normalized["segments"] = [dict(segment, text=" ".join(segment["text"].split())) for segment in transcript["segments"]]
    plan = build_edit_plan(normalized, outline, manifest["assets"], client_id=client_id, source_frames=source_frames)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "transcript-raw.json", transcript)
    _write_json(output_dir / "transcript-normalized.json", normalized)
    _write_json(output_dir / "semantic-beats.json", outline)
    _write_json(output_dir / "edit-plan.json", plan)
    (output_dir / "review.html").write_text(render_report(plan), encoding="utf-8")
    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a complete offline RAMBLA Director plan")
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--outline", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-frames", type=int, required=True)
    args = parser.parse_args()
    plan = run_from_artifacts(args.transcript, args.outline, args.manifest, args.output, source_frames=args.source_frames)
    print(json.dumps({"plan_hash": plan["content_hash"], "beats": len(plan["beats"]), "captions": len(plan["captions"]),
                      "duration_frames": plan["source"]["duration_frames"]}))


if __name__ == "__main__":
    main()
