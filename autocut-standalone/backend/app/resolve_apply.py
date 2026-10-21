"""Two-phase Resolve Apply orchestration behind an injected adapter.

There is intentionally no Resolve/MCP/native implementation in this module.
Tests use a fake adapter, and the live transport can only exist once the user
explicitly re-enables Resolve mutation and an adapter is wired at the boundary.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Protocol

from .director_engine import validate_edit_plan
from .panel_service import canonical_plan_hash


class ResolveMutationAdapter(Protocol):
    def preflight(self, source_timeline: str, operations: list[dict[str, Any]]) -> dict[str, Any]: ...

    def list_timeline_names(self) -> set[str]: ...

    def duplicate_timeline(self, source_timeline: str, target_timeline: str) -> None: ...

    def apply_operation(self, target_timeline: str, operation: dict[str, Any]) -> dict[str, Any]: ...

    def verify_operations(self, target_timeline: str, operations: list[dict[str, Any]]) -> dict[str, Any]: ...

    def discard_timeline(self, target_timeline: str) -> None: ...


class ResolvePreflightError(RuntimeError):
    pass


class ResolveApplyError(RuntimeError):
    pass


def allocate_target_name(existing: set[str], *, prefix: str = "REEL_AI_v") -> str:
    for number in range(1, 10_000):
        candidate = f"{prefix}{number:02d}"
        if candidate not in existing:
            return candidate
    raise ResolveApplyError("unable to allocate generated timeline name")


def _selected_slot_proposal(slot: dict[str, Any]) -> dict[str, Any] | None:
    selected_id = slot.get("selected_proposal_id")
    if selected_id is None:
        return None
    for key in ("proposal_A", "proposal_B", "proposal_C"):
        proposal = slot.get(key)
        if isinstance(proposal, dict) and str(proposal.get("id")) == str(selected_id):
            return proposal
    return None


def _asset_path(asset: dict[str, Any]) -> str:
    path = str(asset.get("acquired_path") or asset.get("path") or "").strip()
    if not path:
        raise ValueError("selected visual has no local asset path")
    return path


def _operation_key(plan_hash: str, index: int, operation: dict[str, Any]) -> str:
    material = json.dumps(operation, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(f"{plan_hash}:{index}:{material}".encode("utf-8")).hexdigest()


def compile_resolve_operations(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Compile a frozen offline Edit Plan into deterministic adapter operations."""

    validate_edit_plan(plan)
    plan_hash = canonical_plan_hash(plan)
    if str(plan.get("content_hash") or "") != plan_hash:
        raise ValueError("plan content hash does not match current plan")

    operations: list[dict[str, Any]] = []
    slotted_beats: set[str] = set()

    for slot in plan.get("coverage_slots", []):
        if not isinstance(slot, dict):
            continue
        proposal = _selected_slot_proposal(slot)
        if proposal is None:
            continue
        slotted_beats.add(str(slot.get("beat_id")))
        operations.append(
            {
                "kind": "INSERT_BROLL",
                "start_frame": int(slot["start_frame"]),
                "end_frame": int(slot["end_frame"]),
                "beat_id": str(slot.get("beat_id") or ""),
                "coverage_slot_id": str(slot.get("id") or ""),
                "asset_id": str(proposal.get("id") or ""),
                "asset_path": _asset_path(proposal),
                "source_start_seconds": proposal.get("source_start_seconds"),
                "source_end_seconds": proposal.get("source_end_seconds"),
                "fit": "COVER",
            }
        )

    for beat in plan.get("beats", []):
        action = str(beat.get("action") or "")
        beat_id = str(beat.get("id") or "")
        if action == "TALKING_HEAD":
            continue
        if action == "PUNCH_IN":
            scale = float((beat.get("parameters") or {}).get("scale", 1.08))
            if scale <= 1.0:
                raise ValueError("PUNCH_IN scale must be greater than 1")
            operations.append(
                {
                    "kind": "PUNCH_IN",
                    "start_frame": int(beat["start_frame"]),
                    "end_frame": int(beat["end_frame"]),
                    "beat_id": beat_id,
                    "scale": scale,
                }
            )
            continue
        if action == "BROLL":
            if beat_id in slotted_beats:
                continue
            selected = beat.get("selected_asset")
            if not isinstance(selected, dict):
                raise ValueError("BROLL beat has no selected asset")
            operations.append(
                {
                    "kind": "INSERT_BROLL",
                    "start_frame": int(beat["start_frame"]),
                    "end_frame": int(beat["end_frame"]),
                    "beat_id": beat_id,
                    "coverage_slot_id": None,
                    "asset_id": str(selected.get("id") or ""),
                    "asset_path": _asset_path(selected),
                    "source_start_seconds": selected.get("source_start_seconds"),
                    "source_end_seconds": selected.get("source_end_seconds"),
                    "fit": str((beat.get("parameters") or {}).get("fit", "COVER")),
                }
            )
            continue
        if action == "CAPTION_EMPHASIS":
            operations.append(
                {
                    "kind": "CAPTION_EMPHASIS",
                    "start_frame": int(beat["start_frame"]),
                    "end_frame": int(beat["end_frame"]),
                    "beat_id": beat_id,
                    "text": str(beat.get("caption_text") or ""),
                    "parameters": dict(beat.get("parameters") or {}),
                }
            )
            continue
        if action in {"STICKER", "EDITORIAL_INSERT"}:
            raise ValueError(f"{action} requires a concrete Resolve operation adapter before Apply")
        raise ValueError(f"unsupported editorial action for Resolve Apply: {action}")

    for index, caption in enumerate(plan.get("captions", [])):
        operations.append(
            {
                "kind": "CAPTION",
                "start_frame": int(caption["start_frame"]),
                "end_frame": int(caption["end_frame"]),
                "caption_index": index,
                "text": str(caption["text"]),
                "emphasis_candidates": list(caption.get("emphasis_candidates") or []),
            }
        )

    priority = {
        "INSERT_BROLL": 10,
        "PUNCH_IN": 20,
        "CAPTION_EMPHASIS": 30,
        "CAPTION": 40,
    }
    operations.sort(
        key=lambda row: (
            int(row.get("start_frame", 0)),
            priority.get(str(row.get("kind")), 99),
            int(row.get("end_frame", 0)),
            str(row.get("beat_id") or ""),
            str(row.get("coverage_slot_id") or ""),
            int(row.get("caption_index", -1)),
        )
    )
    for index, operation in enumerate(operations):
        operation["idempotency_key"] = _operation_key(plan_hash, index, operation)
    return operations


class SafeResolveApplyTransport:
    """Apply an approved plan using preflight, duplicate, mutate, verify, ledger."""

    def __init__(
        self,
        *,
        adapter: ResolveMutationAdapter,
        result_root: Path,
        source_timeline: str = "REEL_MASTER",
    ) -> None:
        if not source_timeline.strip():
            raise ValueError("source_timeline is required")
        self.adapter = adapter
        self.result_root = Path(result_root)
        self.source_timeline = source_timeline.strip()

    def _result_path(self, plan_hash: str) -> Path:
        return self.result_root / f"apply-{plan_hash}.json"

    def _cached_success(self, path: Path, plan_hash: str) -> dict[str, Any] | None:
        if not path.is_file():
            return None
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ResolveApplyError("cached Apply ledger is unreadable; refusing duplicate mutation") from exc
        if (
            not isinstance(row, dict)
            or row.get("status") != "SUCCEEDED"
            or row.get("plan_hash") != plan_hash
            or not row.get("target_timeline")
        ):
            raise ResolveApplyError("cached Apply ledger is invalid; refusing duplicate mutation")
        replay = dict(row)
        replay["idempotent_replay"] = True
        return replay

    def _write_result(self, path: Path, result: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp.replace(path)

    def apply_approved_plan(self, plan: dict[str, Any], approval: dict[str, Any]) -> dict[str, Any]:
        validate_edit_plan(plan)
        plan_hash = canonical_plan_hash(plan)
        if (
            str(plan.get("content_hash") or "") != plan_hash
            or approval.get("status") != "APPROVED"
            or str(approval.get("approved_plan_hash") or "") != plan_hash
        ):
            raise ValueError("approved plan hash does not match current plan")

        result_path = self._result_path(plan_hash)
        cached = self._cached_success(result_path, plan_hash)
        if cached is not None:
            return cached

        operations = compile_resolve_operations(plan)
        try:
            preflight = self.adapter.preflight(self.source_timeline, operations)
        except Exception as exc:
            raise ResolvePreflightError(str(exc)) from exc
        if not isinstance(preflight, dict) or not preflight.get("ok") or not preflight.get("source_exists"):
            raise ResolvePreflightError("Resolve preflight rejected the source timeline or operation set")

        duplicated = False
        target = ""
        try:
            existing = self.adapter.list_timeline_names()
            if self.source_timeline not in existing:
                raise ResolvePreflightError("source timeline disappeared after preflight")
            target = allocate_target_name(existing)
            self.adapter.duplicate_timeline(self.source_timeline, target)
            duplicated = True
            for operation in operations:
                response = self.adapter.apply_operation(target, operation)
                if not isinstance(response, dict) or response.get("ok") is False:
                    raise RuntimeError(f"adapter rejected {operation['kind']}")
            verification = self.adapter.verify_operations(target, operations)
            if not isinstance(verification, dict) or not verification.get("ok"):
                raise RuntimeError("Resolve verification failed")
        except ResolvePreflightError:
            if duplicated and target:
                try:
                    self.adapter.discard_timeline(target)
                except Exception:
                    pass
            raise
        except Exception as exc:
            if duplicated and target:
                try:
                    self.adapter.discard_timeline(target)
                except Exception as rollback_exc:
                    raise ResolveApplyError(
                        f"{exc}; rollback also failed: {rollback_exc}"
                    ) from exc
            raise ResolveApplyError(str(exc)) from exc

        result = {
            "status": "SUCCEEDED",
            "plan_hash": plan_hash,
            "source_timeline": self.source_timeline,
            "target_timeline": target,
            "operation_count": len(operations),
            "verification": verification,
            "idempotent_replay": False,
        }
        self._write_result(result_path, result)
        return result
