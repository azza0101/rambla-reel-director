"""Frozen Apply operation and report models for contract v1."""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field, model_validator

from .common import ApplyAttemptId, AssetId, Confidence, ContractModel, DecisionId, FrameRange, JsonObject, OperationId, PlanId, RunId, SCHEMA_VERSION, Sha256, UtcTimestamp, Uuid
from .errors import TypedError


class TimelineIdentity(ContractModel):
    project_ref: str
    timeline_ref: str
    observed_name: str


class OperationCondition(ContractModel):
    kind: str
    expected_hash: Sha256 | None


class DuplicateTimelinePayload(ContractModel):
    source_timeline_name: str
    target_timeline_name: str


class ImportAssetPayload(ContractModel):
    asset_id: AssetId
    content_hash: Sha256


class PlaceMediaPayload(ContractModel):
    asset_id: AssetId
    range: FrameRange
    target_track_role: str


class SetTransformPayload(ContractModel):
    range: FrameRange
    scale: Annotated[float, Field(ge=1.02, le=1.35)]
    anchor_x: Confidence
    anchor_y: Confidence
    easing: Literal["CUT", "EASE_IN_OUT"]


class PlaceOverlayPayload(ContractModel):
    asset_id: AssetId
    range: FrameRange
    position_x: Confidence
    position_y: Confidence
    scale: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    opacity: Confidence


class ApplyCaptionEmphasisPayload(ContractModel):
    range: FrameRange
    alignment_word_ids: list[Uuid]
    style_token: str
    emphasis: Literal["COLOR", "WEIGHT", "SCALE", "BACKGROUND"]


class VerifyPayload(ContractModel):
    operation_ids: list[OperationId]


class DiscardGeneratedTimelinePayload(ContractModel):
    actor: str
    confirmation_token: Uuid


ApplyPayload = Union[
    DuplicateTimelinePayload,
    ImportAssetPayload,
    PlaceMediaPayload,
    SetTransformPayload,
    PlaceOverlayPayload,
    ApplyCaptionEmphasisPayload,
    VerifyPayload,
    DiscardGeneratedTimelinePayload,
]


class ApplyOperation(ContractModel):
    schema_version: Literal[SCHEMA_VERSION]
    id: OperationId
    apply_attempt_id: ApplyAttemptId
    plan_id: PlanId
    decision_id: DecisionId | None
    kind: Literal[
        "DUPLICATE_TIMELINE",
        "IMPORT_ASSET",
        "PLACE_MEDIA",
        "SET_TRANSFORM",
        "PLACE_OVERLAY",
        "APPLY_CAPTION_EMPHASIS",
        "VERIFY",
        "DISCARD_GENERATED_TIMELINE",
    ]
    target_identity: TimelineIdentity | None
    precondition: OperationCondition
    payload: ApplyPayload
    expected_postcondition: OperationCondition

    @model_validator(mode="after")
    def payload_matches_kind(self) -> "ApplyOperation":
        expected_type = {
            "DUPLICATE_TIMELINE": DuplicateTimelinePayload,
            "IMPORT_ASSET": ImportAssetPayload,
            "PLACE_MEDIA": PlaceMediaPayload,
            "SET_TRANSFORM": SetTransformPayload,
            "PLACE_OVERLAY": PlaceOverlayPayload,
            "APPLY_CAPTION_EMPHASIS": ApplyCaptionEmphasisPayload,
            "VERIFY": VerifyPayload,
            "DISCARD_GENERATED_TIMELINE": DiscardGeneratedTimelinePayload,
        }[self.kind]
        if not isinstance(self.payload, expected_type):
            raise ValueError("payload must match kind")
        return self


class ApplyReport(ContractModel):
    schema_version: Literal[SCHEMA_VERSION]
    id: Uuid
    run_id: RunId
    plan_id: PlanId
    approved_plan_hash: Sha256
    apply_attempt_id: ApplyAttemptId
    started_at: UtcTimestamp
    finished_at: UtcTimestamp | None
    source_identity: JsonObject
    target_identity: JsonObject | None
    preflight: JsonObject
    operations: list[JsonObject]
    verification: JsonObject | None
    status: Literal["SUCCEEDED", "FAILED", "AMBIGUOUS", "CLEANED_UP"]
    error: TypedError | None
