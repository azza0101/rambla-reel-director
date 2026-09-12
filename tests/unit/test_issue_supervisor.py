from pathlib import Path

from backend.app import issue_supervisor as supervisor


def test_watcher_records_new_actionable_state_once(monkeypatch, tmp_path: Path) -> None:
    comments = [
        {"id": 10, "body": "HANDOFF\nstage: FT3"},
        {"id": 11, "body": "CONTENT SPRINT — START NOW"},
    ]
    monkeypatch.setattr(supervisor, "gh_json", lambda *args: comments)
    state = tmp_path / "state.json"
    heartbeat = tmp_path / "heartbeat.json"

    first = supervisor.poll_once(state, heartbeat)
    second = supervisor.poll_once(state, heartbeat)

    assert first["status"] == "WATCHER_GREEN_EXECUTOR_BLOCKED"
    assert first["pending_comment_id"] == 11
    assert second["last_processed_comment_id"] == 11
    assert supervisor.load_state(state)["retry_count"] == 0


def test_handoff_is_not_actionable() -> None:
    assert not supervisor.actionable({"body": "HANDOFF\nstage: FT3"})
    assert supervisor.actionable({"body": "REVIEW\nverdict: FIX"})
