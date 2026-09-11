"""RFC 8785 canonical hashes for persisted contract values."""

from __future__ import annotations

import hashlib
from typing import Any

import rfc8785
from pydantic import BaseModel

from .plans import EditPlan


def _json_value(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def canonical_sha256(value: object) -> str:
    """Return the RFC 8785 canonical JSON SHA-256 digest with its required tag."""
    payload = rfc8785.dumps(_json_value(value))
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def edit_plan_approval_hash(plan: EditPlan) -> str:
    """Hash all plan semantics except approval and its later Apply result reference."""
    approval_input: dict[str, Any] = plan.model_dump(
        mode="json", exclude={"approval", "apply_result_ref"}
    )
    return canonical_sha256(approval_input)
