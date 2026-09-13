from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.director_engine import build_edit_plan
from backend.app.main import create_app
from backend.app.panel_service import PanelService


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[dict, dict]] = []

    def apply_approved_plan(self, plan: dict, approval: dict) -> dict:
        self.calls.append((plan, approval))
        return {"status": "SUCCEEDED", "target": "REEL_AI_v01"}


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
            {
                "id": "beat-1",
                "start_seconds": 0.0,
                "end_seconds": 4.0,
                "intent": "hook iniziale",
                "broll_queries": [],
            },
            {
                "id": "beat-2",
                "start_seconds": 4.0,
                "end_seconds": 8.0,
                "intent": "conclusione",
                "broll_queries": [],
            },
        ]
    }
    return build_edit_plan(
        transcript,
        outline,
        [],
        client_id="client-a",
        source_frames=192,
    )


def test_panel_home_is_safe_and_does_not_expose_live_resolve_buttons(tmp_path) -> None:
    transport = FakeTransport()
    service = PanelService(transport=transport, approval_root=tmp_path)
    client = TestClient(create_app(panel_service=service))

    response = client.get("/")

    assert response.status_code == 200
    assert "RAMBLA Reel Director" in response.text
    assert "APPLY FROZEN" in response.text
    assert "Load Edit Plan" in response.text
    assert "Probe Resolve" not in response.text
    assert "Dry Run PUNCH_IN" not in response.text
    assert transport.calls == []


def test_panel_review_and_approve_are_offline(tmp_path) -> None:
    transport = FakeTransport()
    service = PanelService(transport=transport, approval_root=tmp_path)
    client = TestClient(create_app(panel_service=service))
    plan = _plan()

    review = client.post("/v1/panel/review", json={"plan": plan})
    approval = client.post("/v1/panel/approve", json={"plan": plan, "actor": "editor"})

    assert review.status_code == 200
    assert review.json()["resolve_calls"] == 0
    assert review.json()["plan_hash"] == plan["content_hash"]
    assert approval.status_code == 200
    assert approval.json()["approved_plan_hash"] == plan["content_hash"]
    assert transport.calls == []


def test_panel_apply_is_http_locked_while_frozen_and_never_calls_transport(tmp_path) -> None:
    transport = FakeTransport()
    service = PanelService(transport=transport, approval_root=tmp_path)
    client = TestClient(create_app(panel_service=service))
    plan = _plan()
    approval = service.approve(plan, actor="editor")

    response = client.post("/v1/panel/apply", json={"plan": plan, "approval": approval})

    assert response.status_code == 423
    assert "frozen" in response.json()["detail"].lower()
    assert transport.calls == []


def test_legacy_live_resolve_routes_are_not_registered(tmp_path) -> None:
    client = TestClient(
        create_app(panel_service=PanelService(transport=FakeTransport(), approval_root=tmp_path))
    )

    assert client.post("/v1/resolve/probe").status_code == 404
    assert client.post("/v1/resolve/dry-run").status_code == 404
    assert client.post("/v1/resolve/apply", json={"plan_id": "anything"}).status_code == 404
