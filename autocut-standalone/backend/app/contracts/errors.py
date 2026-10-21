"""Safe, typed API and persistence errors."""

from __future__ import annotations

from typing import Literal

from .common import ContractModel, JsonObject, SCHEMA_VERSION, Uuid


class TypedError(ContractModel):
    schema_version: Literal[SCHEMA_VERSION]
    code: str
    category: Literal[
        "VALIDATION",
        "CAPABILITY",
        "PROVIDER",
        "NETWORK",
        "TIMEOUT",
        "CANCELLED",
        "CONFLICT",
        "SECURITY",
        "STORAGE",
        "RESOLVE",
        "INTERNAL",
    ]
    retryable: bool
    message: str
    diagnostic_id: Uuid
    details: JsonObject | None
