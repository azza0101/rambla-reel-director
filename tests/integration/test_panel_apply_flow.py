from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.director_engine import build_edit_plan
from backend.app.main import create_app
from backend.app.panel_service import PanelService
from backend.app.resolve_apply import SafeResolveApplyTransport


def _plan() -> dict:
    transcript = {
        "source": "reel.mp4",
        "language": "it",
        "timeline_fps": 24,
        "segments": [
            {"start": 0.0, "end": 4.0, "text": "Questo è il primo punto."},
            {"start": 4.0, "end": 8.0, "text": "Qui arriva la conclusione."},
        ],
    }
    outline = {
        "beats": [
            {"id": "beat-1", "start_seconds": 0.0, "end_seconds": 4.0, "intent": "hook iniziale", "broll_queries": []},
            {"id": "beat-2", "start_seconds": 4.0, "end_seconds": 8.0, "intent": "conclusione", "broll_queries": []},
        ]
    }
    return build_edit_plan(transcript, outline, [], client_id="client-a", source_frames=192)


class FakeResolveMutationAdapter:
    def __init__(self) -> None:
        self.names = {"REEL_MASTER"}
        self.events: list[tuple] = []

    def preflight(self, source_timeline: str, operations: list[dict]) -> dict:
        self.events.append(("preflight", source_timeline, len(operations)))
        return {"ok": True, "source_exists": source_timeline in self.names}

    def list_timeline_names(self) -> set[str]:
        self.events.append(("list",))
        return set(self.names)

    def duplicate_timeline(self, source_timeline: str, target_timeline: str) -> None:
        self.events.append(("duplicate", source_timeline, target_timeline))
        self.names.add(target_timeline)

    def apply_operation(self, target_timeline: str, operation: dict) -> dict:
        self.events.append(("apply", target_timeline, operation["kind"]))
        return {"ok": True}

    def verify_operations(self, target_timeline: str, operations: list[dict]) -> dict:
        self.events.append(("verify", target_timeline, len(operations)))
        return {"ok": True, "operation_count": len(operations)}

    def discard_timeline(self, target_timeline: str) -> None:
        self.events.append(("discard", target_timeline))
        self.names.discard(target_timeline)


def test_http_review_approval_apply_flow_reaches_only_injected_transport(tmp_path) -> None:
    adapter = FakeResolveMutationAdapter()
    transport = SafeResolveApplyTransport(adapter=adapter, result_root=tmp_path / "apply-results")
    service = PanelService(
        transport=transport,
        approval_root=tmp_path / "approvals",
        apply_enabled=True,
    )
    client = TestClient(create_app(panel_service=service))
    plan = _plan()

    status = client.get("/v1/panel/status")
    review = client.post("/v1/panel/review", json={"plan": plan})
    approval = client.post("/v1/panel/approve", json={"plan": plan, "actor": "editor"})
    applied = client.post(
        "/v1/panel/apply",
        json={"plan": plan, "approval": approval.json()},
    )

    assert status.status_code == 200
    assert status.json()["apply_enabled"] is True
    assert review.status_code == 200
    assert review.json()["resolve_calls"] == 0
    assert approval.status_code == 200
    assert applied.status_code == 200
    assert applied.json()["status"] == "SUCCEEDED"
    assert applied.json()["target_timeline"] == "REEL_AI_v01"
    assert [event[0] for event in adapter.events][0:3] == ["preflight", "list", "duplicate"]
    assert adapter.events[-1][0] == "verify"


def test_http_replay_same_approval_is_idempotent_and_does_not_mutate_twice(tmp_path) -> None:
    adapter = FakeResolveMutationAdapter()
    transport = SafeResolveApplyTransport(adapter=adapter, result_root=tmp_path / "apply-results")
    service = PanelService(
        transport=transport,
        approval_root=tmp_path / "approvals",
        apply_enabled=True,
    )
    client = TestClient(create_app(panel_service=service))
    plan = _plan()
    approval = client.post("/v1/panel/approve", json={"plan": plan, "actor": "editor"}).json()

    first = client.post("/v1/panel/apply", json={"plan": plan, "approval": approval})
    event_count = len(adapter.events)
    second = client.post("/v1/panel/apply", json={"plan": plan, "approval": approval})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["idempotent_replay"] is True
    assert len(adapter.events) == event_count
