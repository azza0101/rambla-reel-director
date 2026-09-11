"""Frozen Edit Plan and editorial decision models for contract v1."""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field, model_validator

from .common import (
    ArtifactRef,
    AssetId,
    Confidence,
    ContractModel,
    DecisionId,
    FrameIndex,
    FrameRange,
    JsonObject,
    PlanId,
    RunId,
    SCHEMA_VERSION,
    Sha256,
    UtcTimestamp,
    Uuid,
)


class BrollParameters(ContractModel):
    fit: Literal["COVER", "CONTAIN"]
    crop_anchor: Literal["CENTER", "FACE_SAFE", "CUSTOM"]
    custom_anchor: "Anchor | None"
    source_offset_frame: Annotated[FrameIndex, Field(ge=0)]
    opacity: Confidence = 1

    @model_validator(mode="after")
    def custom_anchor_matches_crop_choice(self) -> "BrollParameters":
        if (self.crop_anchor == "CUSTOM") != (self.custom_anchor is not None):
            raise ValueError("custom_anchor is required exactly when crop_anchor is CUSTOM")
        return self


class EditorialInsertParameters(ContractModel):
    presentation: Literal["FULL_FRAME", "CARD"]
    fit: Literal["COVER", "CONTAIN"]
    background: Literal["AUTO", "TRANSPARENT", "SOLID"]
    opacity: Confidence


class PunchInParameters(ContractModel):
    scale: Annotated[float, Field(ge=1.02, le=1.35)]
    anchor_x: Confidence
    anchor_y: Confidence
    easing: Literal["CUT", "EASE_IN_OUT"]


class Anchor(ContractModel):
    x: Confidence
    y: Confidence


class StickerParameters(ContractModel):
    position: Anchor
    scale: Annotated[float, Field(gt=0)]
    rotation_deg: float
    opacity: Confidence
    safe_zone: Literal["TOP", "CENTER", "BOTTOM", "CUSTOM"]


class CaptionEmphasisParameters(ContractModel):
    style_token: str
    emphasis: Literal["COLOR", "WEIGHT", "SCALE", "BACKGROUND"]
    keyword_text: str
    alignment_word_ids: list[Uuid]


DecisionParameters = Union[
    BrollParameters,
    EditorialInsertParameters,
    PunchInParameters,
    StickerParameters,
    CaptionEmphasisParameters,
]


class EditDecision(ContractModel):
    id: DecisionId
    action: Literal["BROLL", "EDITORIAL_INSERT", "PUNCH_IN", "STICKER", "CAPTION_EMPHASIS"]
    range: FrameRange | None
    frame: FrameIndex | None
    intent: str
    reason: str
    confidence: Confidence
    queries: list[str]
    candidate_refs: list[AssetId]
    selected_asset_ref: AssetId | None
    parameters: DecisionParameters
    review_state: Literal["PROPOSED", "APPROVED", "MODIFIED", "DISABLED", "NEEDS_REPLACEMENT"]
    provenance: JsonObject

    @model_validator(mode="after")
    def obeys_action_shape(self) -> "EditDecision":
        if self.range is None or self.frame is not None:
            raise ValueError("v1 editorial actions require range and forbid frame")
        parameter_by_action = {
            "BROLL": BrollParameters,
            "EDITORIAL_INSERT": EditorialInsertParameters,
            "PUNCH_IN": PunchInParameters,
            "STICKER": StickerParameters,
            "CAPTION_EMPHASIS": CaptionEmphasisParameters,
        }
        if not isinstance(self.parameters, parameter_by_action[self.action]):
            raise ValueError("parameters must match action")
        if self.action in {"BROLL", "EDITORIAL_INSERT", "STICKER"} and self.selected_asset_ref is None:
            raise ValueError("asset-backed actions require selected_asset_ref")
        return self


class ApprovalRecord(ContractModel):
    actor: str
    approved_at: UtcTimestamp
    approved_plan_hash: Sha256


class EditPlan(ContractModel):
    schema_version: Literal[SCHEMA_VERSION]
    id: PlanId
    run_id: RunId
    version: Annotated[int, Field(ge=1)]
    status: Literal["DRAFT", "IN_REVIEW", "APPROVED", "APPLYING", "APPLIED", "FAILED", "SUPERSEDED"]
    source_timeline_snapshot_ref: ArtifactRef
    source_timeline_hash: Sha256
    style_snapshot_ref: ArtifactRef
    policy_snapshot_ref: ArtifactRef
    controls_snapshot: JsonObject
    provider_trace: list[JsonObject]
    decisions: list[EditDecision]
    validation: JsonObject
    approval: ApprovalRecord | None
    apply_result_ref: ArtifactRef | None
    content_hash: Sha256
