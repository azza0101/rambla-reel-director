"""Resolve-panel domain service with a fail-closed Apply boundary.

The panel may review and approve persisted offline Edit Plans without importing
or connecting to Resolve. A transport is injected at the outer boundary and is
never invoked unless Apply has been explicitly enabled and the approved plan
hash still matches the current plan bytes semantically.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from .director_engine import validate_edit_plan


class ApplyTransport(Protocol):
    def apply_approved_plan(self, plan: dict[str, Any], approval: dict[str, Any]) -> dict[str, Any]: ...


class ApplyFrozenError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def canonical_plan_hash(plan: dict[str, Any]) -> str:
    payload = dict(plan)
    payload.pop("content_hash", None)
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_frozen_plan(plan: dict[str, Any]) -> str:
    validate_edit_plan(plan)
    expected = str(plan.get("content_hash") or "")
    actual = canonical_plan_hash(plan)
    if not expected or expected != actual:
        raise ValueError("plan content hash does not match current plan")
    return actual


class PanelService:
    def __init__(
        self,
        *,
        transport: ApplyTransport,
        approval_root: Path,
        apply_enabled: bool = False,
    ) -> None:
        self.transport = transport
        self.approval_root = Path(approval_root)
        self.apply_enabled = bool(apply_enabled)

    def review(self, plan: dict[str, Any]) -> dict[str, Any]:
        plan_hash = _validate_frozen_plan(plan)
        slots = list(plan.get("coverage_slots", []))
        selected_slots = sum(
            int(bool(slot.get("selected_proposal_id")))
            for slot in slots
            if isinstance(slot, dict)
        )
        review_required = sum(
            int(str(slot.get("review_state", "")).startswith("REVIEW_REQUIRED"))
            for slot in slots
            if isinstance(slot, dict)
        )
        return {
            "schema_version": "panel-review-1",
            "plan_hash": plan_hash,
            "plan_status": plan.get("status"),
            "client_id": plan.get("client_id"),
            "beat_count": len(plan.get("beats", [])),
            "coverage_slot_count": len(slots),
            "selected_slot_count": selected_slots,
            "review_required_count": review_required,
            "caption_count": len(plan.get("captions", [])),
            "apply_enabled": self.apply_enabled,
            "can_apply": False,
            "resolve_calls": 0,
        }

    def approve(self, plan: dict[str, Any], *, actor: str) -> dict[str, Any]:
        if not actor.strip():
            raise ValueError("approval actor is required")
        plan_hash = _validate_frozen_plan(plan)
        approval = {
            "status": "APPROVED",
            "actor": actor.strip(),
            "approved_at": _now(),
            "approved_plan_hash": plan_hash,
        }
        self.approval_root.mkdir(parents=True, exist_ok=True)
        path = self.approval_root / f"{plan_hash}.approval.json"
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(approval, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp.replace(path)
        return approval

    def apply(self, plan: dict[str, Any], approval: dict[str, Any]) -> dict[str, Any]:
        if not self.apply_enabled:
            raise ApplyFrozenError("Resolve Apply is frozen")
        if approval.get("status") != "APPROVED":
            raise ValueError("approved plan record is required")
        approved_hash = str(approval.get("approved_plan_hash") or "")
        actual_hash = canonical_plan_hash(plan)
        if not approved_hash or approved_hash != actual_hash or str(plan.get("content_hash") or "") != actual_hash:
            raise ValueError("approval hash does not match current plan")
        validate_edit_plan(plan)
        result = self.transport.apply_approved_plan(plan, approval)
        if not isinstance(result, dict):
            raise ValueError("Apply transport returned an invalid result")
        return result
