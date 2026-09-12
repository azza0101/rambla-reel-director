import json

from backend.app.director_cli import run_from_artifacts
from backend.app.director_preview import render_report


def test_report_shows_every_beat_and_escapes_untrusted_transcript():
    plan = {
        "client_id": "rambla", "content_hash": "abc", "source": {"fps": 25, "duration_frames": 150},
        "beats": [
            {"id": "one", "start_frame": 0, "end_frame": 50, "transcript": "<script>alert(1)</script>",
             "action": "TALKING_HEAD", "rationale": "keep speaker", "broll_query": "", "selected_asset": None,
             "candidates": [], "caption_text": "hello"},
            {"id": "two", "start_frame": 50, "end_frame": 150, "transcript": "Workflow", "action": "BROLL",
             "rationale": "show proof", "broll_query": "workflow nodes", "selected_asset": {"id": "asset", "path": "C:/a.png", "score": 0.9},
             "candidates": [{"id": "asset", "score": 0.9, "reason": "metadata"}], "caption_text": "world"},
        ], "captions": [{"start_frame": 0, "end_frame": 150, "text": "hello world"}],
    }
    html = render_report(plan)
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html
    assert "workflow nodes" in html
    assert "TALKING_HEAD" in html and "BROLL" in html
    assert "C:/a.png" in html
    assert "hello world" in html


def test_runtime_cli_persists_complete_offline_artifacts(tmp_path):
    transcript = {"source": "clip.mov", "timeline_fps": 25, "segments": [
        {"start": 0, "end": 2, "text": "Ciao.", "words": []},
        {"start": 2, "end": 4, "text": "Nodi workflow.", "words": []},
    ]}
    outline = {"beats": [
        {"id": "intro", "start_seconds": 0, "end_seconds": 2, "intent": "intro", "broll_queries": []},
        {"id": "nodes", "start_seconds": 2, "end_seconds": 4, "intent": "workflow nodes", "broll_queries": ["workflow nodes"]},
    ]}
    manifest = {"client_id": "rambla", "assets": [{"id": "nodes", "client_id": "rambla", "path": str(tmp_path / "nodes.png"), "description": "workflow nodes", "tags": [], "kind": "image"}]}
    (tmp_path / "nodes.png").write_bytes(b"asset")
    for name, value in (("transcript.json", transcript), ("outline.json", outline), ("manifest.json", manifest)):
        (tmp_path / name).write_text(json.dumps(value), encoding="utf-8")
    output = tmp_path / "run"
    plan = run_from_artifacts(tmp_path / "transcript.json", tmp_path / "outline.json", tmp_path / "manifest.json", output, source_frames=100)
    assert plan["source"]["duration_frames"] == 100
    assert json.loads((output / "edit-plan.json").read_text(encoding="utf-8"))["content_hash"] == plan["content_hash"]
    assert (output / "transcript-raw.json").exists()
    assert (output / "transcript-normalized.json").exists()
    assert (output / "semantic-beats.json").exists()
    assert "Nodi workflow" in (output / "review.html").read_text(encoding="utf-8")
