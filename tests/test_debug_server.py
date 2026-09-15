from pathlib import Path
import json

from backend.app.debug_server import ArtifactProgressTracker, DebugEvent, RunState, parse_worker_line, render_debug_page


def test_parse_worker_line_accepts_structured_event():
    event = parse_worker_line('RAMBLA_EVENT {"stage":"qwen_final","progress":72,"message":"5 frames","data":{"candidate":"A"}}')
    assert event == DebugEvent("qwen_final", "5 frames", 72.0, {"candidate": "A"})


def test_artifact_tracker_reports_real_milestones_once(tmp_path: Path):
    tracker = ArtifactProgressTracker(tmp_path)
    assert tracker.scan() == []
    (tmp_path / "transcript-raw.json").write_text("{}", encoding="utf-8")
    assert [(e.stage, e.progress) for e in tracker.scan()] == [("asr", 100.0)]
    assert tracker.scan() == []
    (tmp_path / "semantic-beats.json").write_text("{}", encoding="utf-8")
    (tmp_path / "online-candidates.json").write_text("[]", encoding="utf-8")
    assert [(e.stage, e.progress) for e in tracker.scan()] == [("semantic_chunking", 100.0), ("online_search", 100.0)]


def test_weighted_total_progress_is_monotonic():
    state = RunState("r1", Path("input.mp4"), Path("run"))
    assert state.total() == 0.0
    state.progress["prepare"] = 100.0
    first = state.total()
    state.progress["asr"] = 50.0
    assert state.total() > first


def test_page_has_one_click_live_debug_ui():
    page = render_debug_page()
    assert "ESEGUI" in page
    assert "EventSource" in page
    assert "ASR / trascrizione" in page
    assert "EvidenceIntent" in page
    assert "Qwen final" in page
    assert "KURA_Finto etico_draft 1.mp4" in page
