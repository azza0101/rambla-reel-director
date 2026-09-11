"""Frozen Run persistence model for contract v1."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .common import ArtifactManifestEntry, ArtifactRef, ClientId, ContractModel, EditControls, ProjectId, RunId, SCHEMA_VERSION, StepLease, UtcTimestamp
from .errors import TypedError


class StepState(ContractModel):
    state: Literal["pending", "running", "succeeded", "failed", "skipped", "stale"]
    attempt: Annotated[int, Field(ge=0)]
    lease: StepLease | None
    started_at: UtcTimestamp | None
    finished_at: UtcTimestamp | None
    error: TypedError | None
    selected_output_refs: list[ArtifactRef]


class Run(ContractModel):
    schema_version: Literal[SCHEMA_VERSION]
    id: RunId
    client_id: ClientId
    project_id: ProjectId
    status: Literal["CREATED", "ANALYZING", "REVIEW", "APPROVED", "APPLYING", "APPLIED", "FAILED", "CANCELLED"]
    created_at: UtcTimestamp
    updated_at: UtcTimestamp
    source_timeline_snapshot_ref: ArtifactRef | None
    style_snapshot_ref: ArtifactRef | None
    policy_snapshot_ref: ArtifactRef
    controls_snapshot: EditControls
    provider_profile: str
    steps: dict[str, StepState]
    artifacts: list[ArtifactManifestEntry]
