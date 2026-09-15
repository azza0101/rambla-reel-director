import json
import shutil
import uuid
from pathlib import Path

from backend.app.debug_run_cli import analysis_input_signature, editorial_artifacts_match, invalidate_stale_analysis_outputs, persist_analysis_signature


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


def test_changed_guide_cannot_reuse_or_rebless_stale_downstream_artifacts():
    root = workspace_dir()
    try:
        for name in ("online-candidates.json", "image-candidates.json", "edit-plan.json", "review.html"):
            (root / name).write_text("old", encoding="utf-8")
        (root / "analysis-signature.json").write_text('{"analysis_signature":"run-a"}', encoding="utf-8")

        assert editorial_artifacts_match(root, "run-b") is False
        invalidate_stale_analysis_outputs(root, "run-b")
        assert not any((root / name).exists() for name in ("online-candidates.json", "image-candidates.json", "edit-plan.json", "review.html", "analysis-signature.json"))
        persist_analysis_signature(root, "run-b")
        assert not (root / "analysis-signature.json").exists()
    finally:
        shutil.rmtree(root)


def test_main_uses_guide_for_asr_but_source_for_timeline(monkeypatch):
    import backend.app.debug_run_cli as cli
    root = workspace_dir(); captured = {}
    try:
        source = root / "source.mp4"; guide = root / "guide.wav"; output = root / "run"
        source.write_bytes(b"video"); guide.write_bytes(b"audio"); output.mkdir()
        for name in ("online-candidates.json", "edit-plan.json", "review.html"):
            (output / name).write_text("ok", encoding="utf-8")
        (output / "image-candidates.json").write_text('{"chunks":{"chunk-1":{"candidates":[{}]}}}', encoding="utf-8")
        (output / "analysis-signature.json").write_text('{"analysis_signature":"sig"}', encoding="utf-8")
        def asr(path, **kwargs):
            captured.update(path=path, **kwargs)
            return {"timeline_fps": kwargs["timeline_fps"], "segments": [{"words": [{"text": "hello", "start": 0, "end": 1}]}]}, "fresh"
        monkeypatch.setattr(cli, "_probe", lambda _: (10.0, 250))
        monkeypatch.setattr(cli, "run_asr_stage", asr)
        monkeypatch.setattr(cli, "DEFAULT_MODEL_CACHE", root / "models")
        monkeypatch.setattr("sys.argv", ["debug_run_cli", "--video", str(source), "--guide-audio", str(guide), "--output-dir", str(output), "--analysis-signature", "sig"])
        cli.main()
        assert captured["path"] == guide.resolve()
        assert captured["timeline_fps"] == 25
    finally:
        shutil.rmtree(root)
