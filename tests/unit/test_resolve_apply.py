from __future__ import annotations

import json

import pytest

from backend.app.director_engine import build_edit_plan, validate_edit_plan
from backend.app.panel_service import canonical_plan_hash
from backend.app.resolve_apply import (
    ResolveApplyError,
    ResolvePreflightError,
    SafeResolveApplyTransport,
    compile_resolve_operations,
)


def _plan_with_broll() -> dict:
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
    plan = build_edit_plan(transcript, outline, [], client_id="client-a", source_frames=192)
    slot = plan["coverage_slots"][0]
    proposal = {
        "id": "youtube:abc123",
        "client_id": "client-a",
        "path": "/cache/evidence-42.mp4",
        "kind": "video",
        "source": "youtube",
        "source_page": "https://www.youtube.com/watch?v=abc123",
        "source_start_seconds": 42.0,
        "source_end_seconds": 45.5,
        "score": 0.91,
    }
    slot["proposal_A"] = proposal
    slot["selected_proposal_id"] = proposal["id"]
    slot["review_state"] = "SELECTED"
    plan["content_hash"] = canonical_plan_hash(plan)
    validate_edit_plan(plan)
    return plan


class FakeResolveAdapter:
    def __init__(self, *, preflight_ok: bool = True, fail_operation_index: int | None = None) -> None:
        self.preflight_ok = preflight_ok
        self.fail_operation_index = fail_operation_index
        self.events: list[tuple] = []
        self.names = {"REEL_MASTER"}
        self.applied = 0

    def preflight(self, source_timeline: str, operations: list[dict]) -> dict:
        self.events.append(("preflight", source_timeline, len(operations)))
        return {"ok": self.preflight_ok, "source_exists": source_timeline in self.names}

    def list_timeline_names(self) -> set[str]:
        self.events.append(("list",))
        return set(self.names)

    def duplicate_timeline(self, source_timeline: str, target_timeline: str) -> None:
        self.events.append(("duplicate", source_timeline, target_timeline))
        self.names.add(target_timeline)

    def apply_operation(self, target_timeline: str, operation: dict) -> dict:
        index = self.applied
        self.events.append(("apply", target_timeline, operation["kind"], operation["idempotency_key"]))
        self.applied += 1
        if self.fail_operation_index == index:
            raise RuntimeError("synthetic apply failure")
        return {"ok": True}

    def verify_operations(self, target_timeline: str, operations: list[dict]) -> dict:
        self.events.append(("verify", target_timeline, len(operations)))
        return {"ok": True, "operation_count": len(operations)}

    def discard_timeline(self, target_timeline: str) -> None:
        self.events.append(("discard", target_timeline))
        self.names.discard(target_timeline)


def _approval(plan: dict) -> dict:
    return {"status": "APPROVED", "approved_plan_hash": plan["content_hash"], "actor": "editor"}


def test_compile_operations_includes_slot_broll_punch_in_and_captions_deterministically() -> None:
    plan = _plan_with_broll()

    first = compile_resolve_operations(plan)
    second = compile_resolve_operations(json.loads(json.dumps(plan)))

    assert first == second
    kinds = [row["kind"] for row in first]
    assert "INSERT_BROLL" in kinds
    assert "PUNCH_IN" in kinds
    assert kinds.count("CAPTION") == len(plan["captions"])
    broll = next(row for row in first if row["kind"] == "INSERT_BROLL")
    slot = plan["coverage_slots"][0]
    assert broll["start_frame"] == slot["start_frame"]
    assert broll["end_frame"] == slot["end_frame"]
    assert broll["asset_path"] == "/cache/evidence-42.mp4"
    assert len({row["idempotency_key"] for row in first}) == len(first)


def test_preflight_failure_happens_before_any_resolve_mutation(tmp_path) -> None:
    plan = _plan_with_broll()
    adapter = FakeResolveAdapter(preflight_ok=False)
    transport = SafeResolveApplyTransport(adapter=adapter, result_root=tmp_path)

    with pytest.raises(ResolvePreflightError):
        transport.apply_approved_plan(plan, _approval(plan))

    assert [event[0] for event in adapter.events] == ["preflight"]


def test_successful_apply_is_two_phase_and_verifies_duplicate(tmp_path) -> None:
    plan = _plan_with_broll()
    adapter = FakeResolveAdapter()
    transport = SafeResolveApplyTransport(adapter=adapter, result_root=tmp_path)

    result = transport.apply_approved_plan(plan, _approval(plan))

    names = [event[0] for event in adapter.events]
    assert names[0:3] == ["preflight", "list", "duplicate"]
    assert names[-1] == "verify"
    assert result["status"] == "SUCCEEDED"
    assert result["source_timeline"] == "REEL_MASTER"
    assert result["target_timeline"] == "REEL_AI_v01"
    assert result["operation_count"] == len(compile_resolve_operations(plan))
    assert result["verification"]["ok"] is True
    assert result["idempotent_replay"] is False


def test_same_approved_plan_replays_cached_result_without_second_mutation(tmp_path) -> None:
    plan = _plan_with_broll()
    adapter = FakeResolveAdapter()
    transport = SafeResolveApplyTransport(adapter=adapter, result_root=tmp_path)

    first = transport.apply_approved_plan(plan, _approval(plan))
    event_count = len(adapter.events)
    second = transport.apply_approved_plan(plan, _approval(plan))

    assert first["target_timeline"] == second["target_timeline"]
    assert second["idempotent_replay"] is True
    assert len(adapter.events) == event_count


def test_apply_failure_discards_new_duplicate_and_returns_no_false_success(tmp_path) -> None:
    plan = _plan_with_broll()
    adapter = FakeResolveAdapter(fail_operation_index=1)
    transport = SafeResolveApplyTransport(adapter=adapter, result_root=tmp_path)

    with pytest.raises(ResolveApplyError, match="synthetic apply failure"):
        transport.apply_approved_plan(plan, _approval(plan))

    assert any(event[0] == "discard" for event in adapter.events)
    assert adapter.names == {"REEL_MASTER"}
    assert list(tmp_path.glob("*.json")) == []
