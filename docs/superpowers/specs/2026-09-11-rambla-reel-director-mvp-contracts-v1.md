# RAMBLA Reel Director — MVP Contracts v1

Date: 2026-09-11
Status: **normative completion supplement for the MVP technical specification**

This document closes the seven open technical-contract blockers recorded in section 25 of `2026-09-11-rambla-reel-director-mvp-design.md`. Where this document is more specific than the design document, this document governs. Resolve capability values explicitly marked `TBD_BY_SPIKE` remain capability-gated by Slice 0 and are not implementation freedom.

## 1. Versioning and common types

All persisted JSON uses `schema_version: "1.0"` unless otherwise stated. Version compatibility follows semantic rules: unknown major versions are rejected; additive compatible minor fields may be preserved but must not alter behavior silently.

Common scalar types:

- `Uuid`: lowercase canonical UUID string.
- `UtcTimestamp`: RFC 3339 UTC timestamp ending in `Z`.
- `Sha256`: `sha256:<64 lowercase hex>`.
- `ClientId`, `ProjectId`, `RunId`, `PlanId`, `DecisionId`, `AssetId`, `OperationId`: `Uuid` aliases.
- `FrameIndex`: signed 64-bit integer.
- `FrameRange`: `{ "start_frame": int64, "end_frame": int64 }`, half-open, with `start_frame < end_frame`.
- `Timebase`: `{ "num": int32, "den": int32, "drop_frame": bool, "start_timecode": string }`, with positive reduced rational `num/den`.
- `Confidence`: JSON number in `[0,1]`.
- `PathRef`: logical path identifier; persisted domain objects must not depend on absolute filesystem paths for semantic identity.

Every top-level persisted entity is a closed object with `additionalProperties=false` in the checked-in JSON Schema. Extension fields require a schema minor-version bump.

## 2. Frozen v1 persisted schemas

The implementation must encode these shapes as checked-in JSON Schema files before production adapters are written. The field names, required/optional status, enum values, and nesting below are frozen for v1.

### 2.1 Run

Required:

```text
schema_version: "1.0"
id: RunId
client_id: ClientId
project_id: ProjectId
status: CREATED | ANALYZING | REVIEW | APPROVED | APPLYING | APPLIED | FAILED | CANCELLED
created_at: UtcTimestamp
updated_at: UtcTimestamp
source_timeline_snapshot_ref: ArtifactRef | null
style_snapshot_ref: ArtifactRef | null
policy_snapshot_ref: ArtifactRef
controls_snapshot: EditControls
provider_profile: string
steps: map<string, StepState>
artifacts: ArtifactManifestEntry[]
```

`StepState` is a closed object:

```text
state: pending | running | succeeded | failed | skipped | stale
attempt: int >= 0
lease: StepLease | null
started_at: UtcTimestamp | null
finished_at: UtcTimestamp | null
error: TypedError | null
selected_output_refs: ArtifactRef[]
```

### 2.2 TimelineSnapshot

Required:

```text
schema_version: "1.0"
id: Uuid
run_id: RunId
captured_at: UtcTimestamp
resolve_context: ResolveContext
source_identity: SourceTimelineIdentity
timebase: Timebase
timeline_start_frame: FrameIndex
timeline_end_frame: FrameIndex
tracks: TimelineTrack[]
media_items: TimelineMediaItem[]
content_hash: Sha256
```

`TimelineTrack` contains `track_id`, `kind: VIDEO|AUDIO|SUBTITLE|OTHER`, `index`, `name`, and ordered `items` references.

`TimelineMediaItem` contains stable/compound Resolve identity, track reference, timeline `FrameRange`, source-media reference, source in/out frame mapping, playback-rate rational, enabled state, and transform summary needed by the MVP. Variable-frame-rate source mappings must include explicit normalization provenance.

### 2.3 Transcript

Required:

```text
schema_version: "1.0"
id: Uuid
run_id: RunId
language: string
provider: ProviderTrace
segments: TranscriptSegment[]
content_hash: Sha256
```

`TranscriptSegment`:

```text
id: Uuid
range: FrameRange
text: string
confidence: Confidence | null
speaker: string | null
```

### 2.4 Alignment

Required:

```text
schema_version: "1.0"
id: Uuid
run_id: RunId
transcript_ref: ArtifactRef
provider: ProviderTrace
words: AlignedWord[]
content_hash: Sha256
```

`AlignedWord` contains `segment_id`, `token_index`, `text`, `range: FrameRange`, `confidence`, and `source: FORCED_ALIGNER|ASR_NATIVE`.

### 2.5 StyleDNA

Required:

```text
schema_version: "1.0"
id: Uuid
client_id: ClientId
name: string
version: int >= 1
status: CANDIDATE | APPROVED | RETIRED
editorial: EditorialDNA
visual: VisualDNA
content: ContentDNA
sound: SoundDNA | null
evidence: StyleEvidence[]
approved_by: string | null
approved_at: UtcTimestamp | null
content_hash: Sha256
```

Approved Style DNA is immutable. A revision creates a new integer version.

### 2.6 VisualAsset

Required:

```text
schema_version: "1.0"
id: AssetId
type: VIDEO | IMAGE | DOCUMENT | SCREENSHOT | STICKER | GRAPHIC | MEME | ARCHIVAL | GENERATED
source: CLIENT_LOCAL | PEXELS | PIXABAY | GENERATED
ownership_scope: CLIENT | REMOTE | GENERATED
client_id: ClientId | null
source_identifier: string
media: AssetMedia
semantic_tags: string[]
license: LicenseRecord
attribution: AttributionRecord
safe_crop: SafeCropRecord | null
content_hash: Sha256 | null
cache_state: MISSING | PREVIEW | SELECTED | MATERIALIZED | QUARANTINED
provenance: ProvenanceRecord
```

`CLIENT` ownership requires non-null `client_id`; cross-client access is invalid even if the asset ID/path is known.

### 2.7 PolicySnapshot

Required:

```text
schema_version: "1.0"
id: Uuid
client_id: ClientId
run_id: RunId
allowed_asset_sources: string[]
cloud: CloudPolicy
generation_allowed: bool
logging: LoggingPolicy
retention_policy_version: string
content_hash: Sha256
```

`CloudPolicy` is deny-by-default and stores allowed providers plus independently allowed data classes: `TRANSCRIPT`, `FRAMES`, `AUDIO`, `FILENAMES`, `ASSET_METADATA`, `STYLE_METADATA`.

### 2.8 EditPlan

Required:

```text
schema_version: "1.0"
id: PlanId
run_id: RunId
version: int >= 1
status: DRAFT | IN_REVIEW | APPROVED | APPLYING | APPLIED | FAILED | SUPERSEDED
source_timeline_snapshot_ref: ArtifactRef
source_timeline_hash: Sha256
style_snapshot_ref: ArtifactRef
policy_snapshot_ref: ArtifactRef
controls_snapshot: EditControls
provider_trace: ProviderTrace[]
decisions: EditDecision[]
validation: PlanValidation
approval: ApprovalRecord | null
apply_result_ref: ArtifactRef | null
content_hash: Sha256
```

`EditDecision`:

```text
id: DecisionId
action: BROLL | EDITORIAL_INSERT | PUNCH_IN | STICKER | CAPTION_EMPHASIS
range: FrameRange | null
frame: FrameIndex | null
intent: string
reason: string
confidence: Confidence
queries: string[]
candidate_refs: AssetId[]
selected_asset_ref: AssetId | null
parameters: action-specific closed object
review_state: PROPOSED | APPROVED | MODIFIED | DISABLED | NEEDS_REPLACEMENT
provenance: ProvenanceRecord
```

Exactly one of `range` or `frame` is set according to action semantics in section 5.

Approval uses RFC 8785 canonical JSON + SHA-256 exactly as defined in the design document. Approved plans are immutable.

### 2.9 ApplyOperation

Required:

```text
schema_version: "1.0"
id: OperationId
apply_attempt_id: Uuid
plan_id: PlanId
decision_id: DecisionId | null
kind: DUPLICATE_TIMELINE | IMPORT_ASSET | PLACE_MEDIA | SET_TRANSFORM | PLACE_OVERLAY | APPLY_CAPTION_EMPHASIS | VERIFY | DISCARD_GENERATED_TIMELINE
target_identity: TargetTimelineIdentity | null
precondition: OperationCondition
payload: closed kind-specific object
expected_postcondition: OperationCondition
```

### 2.10 ApplyReport

Required:

```text
schema_version: "1.0"
id: Uuid
run_id: RunId
plan_id: PlanId
approved_plan_hash: Sha256
apply_attempt_id: Uuid
started_at: UtcTimestamp
finished_at: UtcTimestamp | null
source_identity: SourceTimelineIdentity
target_identity: TargetTimelineIdentity | null
preflight: PreflightResult
operations: OperationJournalEntry[]
verification: VerificationResult | null
status: SUCCEEDED | FAILED | AMBIGUOUS | CLEANED_UP
error: TypedError | null
```

### 2.11 Artifact manifest

`run.json.artifacts[]` entries are:

```text
logical_name: string
version: int >= 1
artifact_ref: ArtifactRef
schema_version: string
sha256: Sha256
producer_step: string
producer_attempt: int >= 1
dependency_hashes: map<string,Sha256>
created_at: UtcTimestamp
state: CURRENT | STALE
```

### 2.12 TypedError

Required:

```text
schema_version: "1.0"
code: string
category: VALIDATION | CAPABILITY | PROVIDER | NETWORK | TIMEOUT | CANCELLED | CONFLICT | SECURITY | STORAGE | RESOLVE | INTERNAL
retryable: bool
message: string
diagnostic_id: Uuid
details: object | null
```

Vendor exception text, secrets, credentials, raw media, and raw transcript content must not appear in `message` or logs by default.

## 3. Frozen HTTP API and SSE contract

Base path: `/v1`. JSON request/response bodies use `application/json; charset=utf-8`.

All mutating requests require `Idempotency-Key` (opaque string 16–128 chars). Reusing a key with byte-equivalent canonical request data returns the original result; reusing it with different canonical request data returns `409 IDEMPOTENCY_CONFLICT`.

### 3.1 Resources and commands

```text
POST   /v1/runs
GET    /v1/runs/{run_id}
POST   /v1/runs/{run_id}/analyze
POST   /v1/runs/{run_id}/cancel
GET    /v1/runs/{run_id}/plans
GET    /v1/plans/{plan_id}
PATCH  /v1/plans/{plan_id}/decisions/{decision_id}
POST   /v1/plans/{plan_id}/validate
POST   /v1/plans/{plan_id}/dry-run
POST   /v1/plans/{plan_id}/freeze
POST   /v1/plans/{plan_id}/apply
POST   /v1/apply-attempts/{apply_attempt_id}/cleanup
GET    /v1/apply-attempts/{apply_attempt_id}
GET    /v1/runs/{run_id}/events
```

`POST /runs` snapshots client/project/style/policy/control identifiers and returns `201` with the new Run.

`POST /runs/{id}/analyze` returns `202`; it may resume from valid artifacts. It never calls Resolve mutation methods.

`PATCH /plans/.../decisions/...` accepts an optimistic `plan_version` and returns a new draft plan version. Editing an approved plan returns `409 PLAN_IMMUTABLE`.

`POST /plans/{id}/freeze` requires a successful validation for that exact plan version and terminal review state for each enabled decision; returns `200` with approval hash or `409`.

`POST /plans/{id}/apply` accepts only an approved plan. It returns `202` with `apply_attempt_id`; concurrent apply for the same Resolve project returns `409 APPLY_CONFLICT`.

### 3.2 Status mapping

- `200`: successful read/command completed synchronously.
- `201`: resource created.
- `202`: command accepted for asynchronous execution.
- `400`: malformed request.
- `403`: policy/security denial.
- `404`: unknown resource within current client scope.
- `409`: version/idempotency/lease/state conflict.
- `422`: semantically invalid plan/input.
- `424`: required provider/capability dependency unavailable.
- `429`: provider/rate/resource admission limit.
- `500`: unexpected internal failure with diagnostic ID.
- `503`: backend/Resolve/provider temporarily unavailable.

Error responses contain only `TypedError`.

### 3.3 SSE

Endpoint: `GET /v1/runs/{run_id}/events`.

Event envelope:

```json
{
  "event_id": 42,
  "run_id": "<uuid>",
  "timestamp": "<UTC RFC3339>",
  "type": "STEP_STARTED",
  "step": "transcribe",
  "payload": {}
}
```

`event_id` is monotonically increasing per run. Clients reconnect using standard `Last-Event-ID`; server replays retained events strictly after that ID. If the requested cursor predates retained event history, server sends `type: SNAPSHOT_REQUIRED` then closes; the client refreshes `GET /runs/{id}` and reconnects from the latest advertised event ID. Heartbeat comments are sent at least every 15 seconds while connected. SSE is progress/notification only; state is read from resources, never inferred solely from the event stream.

## 4. Frozen MVP port contracts

All methods receive `RequestContext { request_id, run_id, client_id, deadline_at, cancellation_token_ref }` and return `Result<T, TypedError>`.

### 4.1 TranscriptionProvider

```text
transcribe(ctx, AudioArtifactRef, TranscriptionOptions) -> Transcript
health(ctx) -> ProviderHealth
```

### 4.2 AlignmentProvider

```text
align(ctx, AudioArtifactRef, TranscriptRef, AlignmentOptions) -> Alignment
health(ctx) -> ProviderHealth
```

### 4.3 DirectorProvider

```text
direct(ctx, TimelineSnapshotRef, TranscriptRef, AlignmentRef, StyleDNARef, PolicySnapshotRef, EditControls) -> DirectorDecisionSet
health(ctx) -> ProviderHealth
```

Director output contains semantic decisions only and cannot contain local filesystem mutation instructions.

### 4.4 EmbeddingProvider

```text
embed_text(ctx, TextEmbeddingRequest[]) -> TextEmbedding[]
embed_visual(ctx, VisualEmbeddingRequest[]) -> VisualEmbedding[]
model_identity(ctx) -> ModelIdentity
```

Embedding vectors are referenced by artifact/record IDs; persisted domain decisions must not depend on process-local tensor addresses or model cache paths.

### 4.5 RerankProvider

```text
rerank(ctx, RerankQuery, RerankCandidate[]) -> RankedCandidate[]
model_identity(ctx) -> ModelIdentity
```

### 4.6 VisualJudgeProvider

Optional in MVP runtime but its contract is frozen:

```text
judge(ctx, VisualJudgeRequest) -> VisualJudgeResult
model_identity(ctx) -> ModelIdentity
```

No call is made unless confidence-gating policy explicitly enables it.

### 4.7 AssetSource

```text
search(ctx, AssetSearchRequest) -> AssetSearchPage
get_metadata(ctx, RemoteAssetRef) -> VisualAsset
materialize_selected(ctx, RemoteAssetRef, ClientRunNamespace) -> VisualAsset
```

Search requests include client ID, policy snapshot hash, locale, queries, asset-type constraints, aspect/crop constraints, page cursor, and request ID.

### 4.8 ArtifactStore

```text
write_immutable(ctx, ArtifactWriteRequest) -> ArtifactRef
read(ctx, ArtifactRef) -> bytes
exists(ctx, ArtifactRef) -> bool
mark_stale(ctx, ArtifactRef, reason) -> void
list_manifest(ctx, RunId) -> ArtifactManifestEntry[]
```

`write_immutable` must use same-filesystem temporary write + flush + atomic rename and must reject replacement of an existing immutable artifact path.

### 4.9 ResolveAdapter

The minimum surface in the design is frozen with these result objects:

```text
capabilities(ctx) -> ResolveCapabilities
inspect_context(ctx) -> ResolveContext
capture_timeline(ctx, TimelineRef) -> TimelineSnapshot
extract_analysis_media(ctx, TimelineRef, ExtractionRequest) -> MediaArtifact
preflight_apply(ctx, ApprovedPlanRef, TimelineSnapshotHash) -> PreflightResult
duplicate_timeline(ctx, SourceTimelineIdentity, AllocatedTargetName, OperationId) -> TargetTimelineIdentity
apply_operation(ctx, TargetTimelineIdentity, ApplyOperation, OperationId) -> OperationResult
verify_apply(ctx, TargetTimelineIdentity, ExpectedTimelineState) -> VerificationResult
discard_generated_timeline(ctx, TargetTimelineIdentity, OperationId) -> OperationResult
```

Mutating methods must reject source identity, stale/mismatched preflight, and target identity not registered to the active apply attempt.

## 5. Frozen semantics for the five MVP editorial actions

General rules:

- Action placement is frame-based.
- Every enabled decision has exactly one verification postcondition.
- Overlap is rejected unless explicitly permitted below.
- Asset-backed actions require selected asset content hash before freeze.
- Review edits create a new plan version.

### 5.1 BROLL

Purpose: temporarily replace or cover the talking-head visual while original timeline audio continues unless explicitly muted by an out-of-scope future feature.

Required:

```text
range: FrameRange
selected_asset_ref: AssetId
parameters.fit: COVER | CONTAIN
parameters.crop_anchor: CENTER | FACE_SAFE | CUSTOM
parameters.custom_anchor: {x:0..1,y:0..1} | null
parameters.source_offset_frame: int64 >= 0
parameters.opacity: 0..1, default 1
```

Layer policy: dedicated AI B-roll video track above A-roll, below stickers/callouts.

Collision: BROLL may not overlap another enabled BROLL or EDITORIAL_INSERT range. It may overlap caption emphasis and stickers. Punch-in on underlying A-roll is retained semantically but not visually relevant during the covered frames.

Postcondition: expected asset hash occupies exactly the target range on the allocated B-roll track with expected fit/crop/source trim.

### 5.2 EDITORIAL_INSERT

Purpose: full-frame or card-like editorial evidence such as screenshot, article, document, archival image, or still.

Required:

```text
range: FrameRange
selected_asset_ref: AssetId
parameters.presentation: FULL_FRAME | CARD
parameters.fit: COVER | CONTAIN
parameters.background: AUTO | TRANSPARENT | SOLID
parameters.opacity: 0..1
```

Layer policy: same visual-interruption lane as BROLL.

Collision: mutually exclusive with BROLL and another EDITORIAL_INSERT over the same frame range. May overlap stickers only when `presentation=CARD` and validation confirms non-overlapping safe zones.

Postcondition: expected asset hash and presentation parameters match the target range.

### 5.3 PUNCH_IN

Purpose: scale/reframe talking-head A-roll without replacing it.

Required:

```text
range: FrameRange
parameters.scale: number, v1 allowed [1.02,1.35]
parameters.anchor_x: 0..1
parameters.anchor_y: 0..1
parameters.easing: CUT | EASE_IN_OUT
```

Layer policy: transform on the duplicated A-roll item(s), never source timeline items.

Collision: overlapping punch-ins are forbidden. Punch-in may temporally overlap BROLL/EDITORIAL_INSERT but validation flags the overlap as visually masked; no nested scale multiplication occurs.

Postcondition: target duplicate has expected transform over the exact frame range within adapter tolerance frozen by the Resolve spike.

### 5.4 STICKER

Purpose: short overlay/callout graphic synchronized to speech.

Required:

```text
range: FrameRange
selected_asset_ref: AssetId
parameters.position: {x:0..1,y:0..1}
parameters.scale: number > 0
parameters.rotation_deg: number
parameters.opacity: 0..1
parameters.safe_zone: TOP | CENTER | BOTTOM | CUSTOM
```

Layer policy: dedicated overlay track above B-roll/editorial inserts and below any system review/debug overlay.

Collision: sticker ranges may overlap each other only if bounding-box safe-zone validation proves non-intersection; otherwise later/lower-confidence proposal is invalidated for review. Caption safe area must remain unobstructed.

Postcondition: expected asset hash, range, transform, and track role are present.

### 5.5 CAPTION_EMPHASIS

Purpose: visually emphasize an already aligned word/span; it does not create a second transcription truth source.

Required:

```text
range: FrameRange
parameters.style_token: string
parameters.emphasis: COLOR | WEIGHT | SCALE | BACKGROUND
parameters.keyword_text: string
parameters.alignment_word_ids: Uuid[]
```

The decision range must be derived from referenced alignment words and may expand only by the schema-defined display padding. Arbitrary free-floating timing is invalid.

Layer policy: implemented only through the caption/title capability proven by Slice 0. If the installed Resolve build cannot support deterministic emphasis, this action is excluded before freeze rather than approximated silently.

Collision: overlapping caption-emphasis decisions may coexist only when they reference disjoint word IDs or resolve to an explicitly composable style; otherwise validation requires user resolution.

Postcondition: referenced word span and style token are observable in the generated target timeline representation supported by the adapter.

## 6. Dry Run — one deterministic meaning

`Dry Run` is a product command with exactly one terminal behavior:

1. execute Analyze through `validate_plan`;
2. produce a valid `DRAFT` EditPlan and `dry_run_report.json`;
3. do not enter user review wait state;
4. do not freeze/approve the plan;
5. do not invoke `preflight_apply`, duplication, cleanup, or any Resolve mutating method;
6. terminate run command state as `DRY_RUN_COMPLETE` while the Run resource itself remains available for later review.

`dry_run_report.json` contains run ID, plan ID/version/hash, validation summary, candidate/selection summary, provider/model timing, policy decisions, warnings, and a boolean `resolve_mutations_performed` which must always be `false`.

Review, Freeze, and Apply are separate commands after Dry Run. Tests must prove no Resolve mutating adapter method is reachable from the Dry Run command graph.

## 7. Retention, deletion, and cleanup policy v1

Policy identifier: `retention-v1`.

### 7.1 Never automatically deleted

Until explicit user deletion of the owning client/project/run:

- approved Style DNA versions;
- approved Edit Plans;
- Apply reports and operation journals;
- project/client configuration;
- provenance/license records required to justify an applied edit.

### 7.2 Run artifacts

Non-approved run artifacts are retained for 30 days after last run activity by default. The user may pin a run, which disables automatic run-artifact deletion. Deletion removes local payload files but retains a minimal tombstone containing IDs, hashes, deletion timestamp, reason, and audit actor.

### 7.3 Temporary/quarantine data

- failed/incomplete same-filesystem temp files: eligible after 24 hours;
- quarantined invalid downloads: delete after 24 hours unless diagnostic pin exists;
- unselected remote previews/downloads: 7 days after last access;
- derived embedding/previews/cache entries: 30 days after last access, LRU cleanup allowed under storage pressure.

Cache eviction is never semantic deletion; cacheable data must be reproducible from retained source/provenance.

### 7.4 Logs and cloud-request records

Structured operational logs: 30 days by default.

Cloud-request audit records: 90 days by default, storing provider, data-class list, purpose, policy decision, timestamps, request/response hashes, token/cost metadata when available, and diagnostic IDs; raw transmitted content is not retained in the audit record.

### 7.5 Resolve generated timelines

Generated duplicate timelines are never auto-deleted. Cleanup requires explicit user approval, target identity verification, and an Apply journal proving the timeline belongs to that apply attempt. Ambiguous identity blocks deletion.

### 7.6 Client deletion

Deleting a client is a distinct destructive command with explicit confirmation. It removes client-scoped local artifacts/caches/assets owned by the application after dependency checks. Shared/global concepts are outside MVP. Audit tombstones contain no raw client media or transcript content.

## 8. Benchmark protocol and MVP sign-off rule

Protocol identifier: `benchmark-v1`.

### 8.1 Fixture set

Minimum benchmark corpus before MVP sign-off:

- at least 10 consented 9:16 talking-head reels;
- at least 100 reviewed editorial decisions total;
- at least 10 reviewed decisions for each action type that is enabled by the Resolve capability matrix;
- varied speaking pace, duration, lighting, and availability of client-local/online visuals;
- fixture provenance and consent recorded.

The same frozen fixture revisions are used for provider/model A/B comparisons.

### 8.2 Measurement procedure

Record:

- exact git commit and schema/metric versions;
- Windows, Resolve, GPU driver, CUDA/PyTorch/provider versions;
- CPU, RAM, GPU, VRAM;
- model IDs/precision/quantization;
- cold-load and warm runs separately;
- per-stage latency;
- peak VRAM/RAM where measurable;
- remote request count/cost where applicable;
- raw review outcome counts by action type;
- failure and retry counts.

Each performance profile runs each fixture at least once cold and three times warm; report median and p95 where sample size permits.

### 8.3 Quality metrics

Primary:

`acceptance_rate = kept_without_material_change / reviewed_decisions`

Also mandatory:

- modification rate;
- replacement rate;
- disable rate;
- per-action breakdown;
- asset-selection acceptance distinct from timing/action acceptance.

A material change uses the versioned definition in the design specification.

### 8.4 Hard sign-off gates

MVP sign-off requires all of:

1. zero source-timeline mutation failures in the full safety test suite;
2. zero cross-client leakage failures in adversarial isolation tests;
3. zero unapproved cloud transmissions in policy tests;
4. zero non-idempotent duplicate mutations in crash/retry Apply tests;
5. all enabled action types pass Resolve contract/postcondition tests for the capability matrix in use;
6. no benchmark run ends with an unclassified/untombstoned destructive state.

### 8.5 Editorial threshold authority

Because editorial quality is product taste, numeric quality thresholds are not hard-coded before a measured baseline. After the first `benchmark-v1` baseline, the user is the approval authority for a checked-in `benchmark-gate-v1` record containing the minimum overall acceptance rate and any per-action minimums. Once approved, the gate is immutable for that MVP release candidate and A/B comparisons must use the same corpus and metric definition.

This closes the protocol decision without inventing an unmeasured quality target: implementation must produce the baseline evidence, and MVP release cannot be signed off until the user approves the versioned gate.

Performance is reported and compared but does not override the hard safety gates or editorial gate. A faster provider/model that reduces approved editorial quality below the approved benchmark gate cannot become the default.

## 9. Final consistency disposition

The seven section-25 blockers are resolved by this supplement:

1. v1 persisted schemas — frozen above;
2. HTTP/SSE contracts — frozen above;
3. MVP port contracts — frozen above;
4. five action semantics — frozen above;
5. Dry Run semantics — frozen above;
6. retention/deletion/cleanup — frozen above;
7. benchmark protocol/sign-off — frozen above.

Remaining `TBD_BY_SPIKE` values are limited to installed-Resolve capability facts explicitly allowed by D-018/D-019, such as stable timeline identifiers, exact transform/title primitives, and adapter tolerances. They must be resolved in Slice 0 before dependent implementation proceeds.

No unresolved technical-contract decision remains that requires invention during the implementation plan. The technical specification is therefore ready for explicit human approval. Product implementation remains forbidden until that approval is recorded and the implementation plan is subsequently written and approved.
