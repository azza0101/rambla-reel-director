import json
import shutil
import uuid
from pathlib import Path

from backend.app.debug_run_cli import analysis_input_signature, persist_analysis_signature


def workspace_dir() -> Path:
    root = Path.cwd() / ".test-debug-cli" / uuid.uuid4().hex
    root.mkdir(parents=True)
    return root


def test_analysis_input_signature_tracks_source_and_guide_independently():
    root = workspace_dir()
    try:
        source = root / "source.mp4"; guide = root / "guide.wav"
        source.write_bytes(b"video"); guide.write_bytes(b"guide")
        signature = analysis_input_signature(source, guide)
        assert signature["source"]["video"] == str(source.resolve())
        assert signature["guide"]["video"] == str(guide.resolve())
    finally:
        shutil.rmtree(root)


def test_analysis_marker_is_written_only_after_required_success_artifacts():
    root = workspace_dir()
    try:
        persist_analysis_signature(root, "sig")
        assert not (root / "analysis-signature.json").exists()
        for name in ("semantic-chunks.json", "review.html", "edit-plan.json"):
            (root / name).write_text("ok", encoding="utf-8")
        persist_analysis_signature(root, "sig")
        assert json.loads((root / "analysis-signature.json").read_text(encoding="utf-8")) == {"analysis_signature": "sig"}
    finally:
        shutil.rmtree(root)
