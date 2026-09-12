from __future__ import annotations

import json

import pytest

from backend.app.director_engine import build_edit_plan
from backend.app.panel_service import ApplyFrozenError, PanelService


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


class FakeApplyTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[dict, dict]] = []

    def apply_approved_plan(self, plan: dict, approval: dict) -> dict:
        self.calls.append((plan, approval))
        return {"status": "SUCCEEDED", "target": "REEL_AI_v01"}


def test_review_is_offline_and_apply_is_frozen_by_default(tmp_path) -> None:
    transport = FakeApplyTransport()
    service = PanelService(transport=transport, approval_root=tmp_path)
    plan = _plan()

    review = service.review(plan)

    assert review["plan_hash"] == plan["content_hash"]
    assert review["beat_count"] == 2
    assert review["coverage_slot_count"] == len(plan["coverage_slots"])
    assert review["apply_enabled"] is False
    assert review["can_apply"] is False
    assert review["resolve_calls"] == 0
    assert transport.calls == []


def test_approval_freezes_current_plan_hash_and_persists_record(tmp_path) -> None:
    service = PanelService(transport=FakeApplyTransport(), approval_root=tmp_path)
    plan = _plan()

    approval = service.approve(plan, actor="editor")

    assert approval["approved_plan_hash"] == plan["content_hash"]
    assert approval["actor"] == "editor"
    assert approval["status"] == "APPROVED"
    saved = json.loads((tmp_path / f"{plan['content_hash']}.approval.json").read_text(encoding="utf-8"))
    assert saved == approval


def test_apply_fails_closed_without_calling_transport(tmp_path) -> None:
    transport = FakeApplyTransport()
    service = PanelService(transport=transport, approval_root=tmp_path)
    plan = _plan()
    approval = service.approve(plan, actor="editor")

    with pytest.raises(ApplyFrozenError, match="frozen"):
        service.apply(plan, approval)

    assert transport.calls == []


def test_enabled_apply_rejects_plan_changed_after_approval(tmp_path) -> None:
    transport = FakeApplyTransport()
    service = PanelService(transport=transport, approval_root=tmp_path, apply_enabled=True)
    plan = _plan()
    approval = service.approve(plan, actor="editor")
    tampered = json.loads(json.dumps(plan))
    tampered["beats"][0]["rationale"] = "changed after approval"

    with pytest.raises(ValueError, match="approval hash"):
        service.apply(tampered, approval)

    assert transport.calls == []


def test_enabled_apply_delegates_exactly_once_for_approved_unchanged_plan(tmp_path) -> None:
    transport = FakeApplyTransport()
    service = PanelService(transport=transport, approval_root=tmp_path, apply_enabled=True)
    plan = _plan()
    approval = service.approve(plan, actor="editor")

    result = service.apply(plan, approval)

    assert result["status"] == "SUCCEEDED"
    assert result["target"] == "REEL_AI_v01"
    assert len(transport.calls) == 1
