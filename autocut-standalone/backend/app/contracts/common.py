"""Shared closed models and constrained scalar values for contract v1."""

from __future__ import annotations

from datetime import datetime
from math import gcd, isfinite
from typing import Annotated, Literal, TypeAlias

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, model_validator


SCHEMA_VERSION = "1.0"
_UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
_UTC_TIMESTAMP_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$"

Uuid: TypeAlias = Annotated[str, StringConstraints(pattern=_UUID_PATTERN)]
ClientId: TypeAlias = Uuid
ProjectId: TypeAlias = Uuid
RunId: TypeAlias = Uuid
PlanId: TypeAlias = Uuid
DecisionId: TypeAlias = Uuid
AssetId: TypeAlias = Uuid
OperationId: TypeAlias = Uuid
ApplyAttemptId: TypeAlias = Uuid
Sha256: TypeAlias = Annotated[str, StringConstraints(pattern=_SHA256_PATTERN)]


def _valid_utc_timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError("timestamp must be UTC")
    return value


UtcTimestamp: TypeAlias = Annotated[
    str,
    StringConstraints(pattern=_UTC_TIMESTAMP_PATTERN),
    AfterValidator(_valid_utc_timestamp),
]
ActionName: TypeAlias = Literal["BROLL", "EDITORIAL_INSERT", "PUNCH_IN", "STICKER", "CAPTION_EMPHASIS"]
FrameIndex: TypeAlias = Annotated[int, Field(ge=-(2**63), le=2**63 - 1)]
Confidence: TypeAlias = Annotated[float, Field(ge=0, le=1)]
ArtifactRef: TypeAlias = Annotated[str, StringConstraints(min_length=1)]
PathRef: TypeAlias = Annotated[str, StringConstraints(min_length=1)]
JsonObject: TypeAlias = dict[str, object]


class ContractModel(BaseModel):
    """Base for persisted/transport objects: no silent extension fields."""

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def contains_only_finite_json_values(cls, value: object) -> object:
        def check(item: object) -> None:
            if isinstance(item, BaseModel):
                return
            if item is None or isinstance(item, (str, bool, int)):
                return
            if isinstance(item, float):
                if not isfinite(item):
                    raise ValueError("JSON numbers must be finite")
                return
            if isinstance(item, list):
                for child in item:
                    check(child)
                return
            if isinstance(item, dict):
                if not all(isinstance(key, str) for key in item):
                    raise ValueError("JSON object keys must be strings")
                for child in item.values():
                    check(child)
                return
            raise ValueError(f"value is not JSON-compatible: {type(item).__name__}")

        check(value)
        return value


class FrameRange(ContractModel):
    start_frame: FrameIndex
    end_frame: FrameIndex

    @model_validator(mode="after")
    def has_positive_half_open_duration(self) -> "FrameRange":
        if self.start_frame >= self.end_frame:
            raise ValueError("start_frame must be less than end_frame")
        return self


class Timebase(ContractModel):
    num: Annotated[int, Field(ge=1, le=2**31 - 1)]
    den: Annotated[int, Field(ge=1, le=2**31 - 1)]
    drop_frame: bool
    start_timecode: str

    @model_validator(mode="after")
    def is_reduced_rational(self) -> "Timebase":
        if gcd(self.num, self.den) != 1:
            raise ValueError("num and den must be a reduced rational")
        return self


class ArtifactManifestEntry(ContractModel):
    logical_name: str
    version: Annotated[int, Field(ge=1)]
    artifact_ref: ArtifactRef
    schema_version: str
    sha256: Sha256
    producer_step: str
    producer_attempt: Annotated[int, Field(ge=1)]
    dependency_hashes: dict[str, Sha256]
    created_at: UtcTimestamp
    state: Literal["CURRENT", "STALE"]


class StepLease(ContractModel):
    owner_id: Uuid
    acquired_at: UtcTimestamp
    heartbeat_at: UtcTimestamp
    expires_at: UtcTimestamp


class EditControls(ContractModel):
    density: Confidence
    allowed_sources: list[str]
    allowed_actions: list[ActionName]
    max_decisions: Annotated[int, Field(ge=1)]


class ProviderTrace(ContractModel):
    provider: str
    model: str
    model_version: str | None
    request_id: Uuid
    started_at: UtcTimestamp
    finished_at: UtcTimestamp
    input_hashes: list[Sha256]
    policy_decision_id: Uuid | None


class ProvenanceRecord(ContractModel):
    source_kind: str
    source_id: str
    acquired_at: UtcTimestamp | None = None
    content_hash: Sha256 | None = None
    license_ref: str | None = None
    attribution: str | None = None
