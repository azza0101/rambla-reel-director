# RAMBLA Reel Director — MVP Technical Design

Date: 2026-09-11
Status: **reviewed draft; approval blocked by the open specification decisions
in section 25; implementation is not yet authorized**

Normative language in this document uses **MUST**, **MUST NOT**, **SHOULD**, and
**MAY** in their ordinary requirements sense. Where an earlier descriptive
sentence conflicts with a normative requirement, the normative requirement
wins. Values marked `TBD_BY_SPIKE` are deliberately capability-gated and MUST
be resolved by Slice 0 before work depending on them begins; they are not
permission to guess during implementation.

## 1. Purpose

RAMBLA Reel Director is a local-first AI social-video editing system for 9:16 talking-head reels. It proposes and applies a coherent edit while preserving editorial control. The product is judged primarily by whether its decisions are worth keeping, not by how many operations it automates.

The MVP must prove one end-to-end flow:

`Analyze → Review → Approve → Duplicate Timeline → Apply → Verify`

The AI never mutates DaVinci Resolve while reasoning. Analysis produces a versioned Edit Plan; Apply accepts only an approved frozen plan and modifies only a duplicated timeline.

## 2. Scope

### In MVP

- Windows-first local backend.
- DaVinci Resolve Studio integration behind `ResolveAdapter`.
- 9:16 talking-head source timeline.
- Transcription and precise alignment.
- Approved Style DNA snapshot per run.
- Editorial decisions for:
  - B-roll
  - editorial inserts
  - punch-ins/reframes
  - stickers/callouts
  - caption emphasis
- Client-local asset lookup.
- Pexels and Pixabay adapters.
- Multimodal retrieval/ranking pipeline.
- Review and per-decision modification.
- Dry Run.
- Duplicate-and-apply workflow.
- Structured intermediate artifacts and logs.
- Local AI baseline.
- Provider interfaces for OpenAI and Claude; implementations may be added after the local vertical slice and benchmarked before MVP sign-off.
- Acceptance-rate telemetry.

### Explicitly deferred

- Music selection.
- Advanced sound design.
- Generated video.
- Automatic rough-cut editing beyond the decision types above.
- Horizontal and horizontal-to-vertical workflows.
- Global/cross-client asset library.
- Silent learning from corrections.
- Fine-tuning.
- Multi-user/cloud collaboration.
- Mobile app.
- Distributed local worker/service architecture unless profiling proves necessary.

## 3. Architecture

Use a **modular monolith with ports and adapters**.

One local backend process owns orchestration and domain logic. External systems are accessed through typed interfaces. Modules must be independently testable and must not import implementation details from sibling adapters.

### Runtime components

1. **Resolve Panel**
   - thin UI
   - no model inference
   - no editorial business logic
   - selects client/project/style/timeline/provider profile
   - starts analysis
   - shows progress
   - reviews decisions
   - approves/finalizes a plan
   - requests Apply

2. **Local API**
   - FastAPI
   - ordinary HTTP for commands/queries
   - Server-Sent Events for progress in v1
   - WebSocket deferred until bidirectional real-time behavior is required

3. **Run Orchestrator**
   - explicit step state machine
   - persists inputs/outputs
   - reruns individual steps from validated upstream artifacts
   - invalidates downstream artifacts when inputs change
   - never calls Apply during Analyze

4. **Domain services**
   - Project Manager
   - Style DNA Service
   - Transcript Service
   - Editorial Director
   - Query Planner
   - Asset Catalog
   - Retrieval Service
   - Ranking Service
   - Sticker Service
   - Plan Service
   - Apply Service
   - Benchmark Service
   - Provider Registry / Model Manager

5. **Adapters**
   - Resolve scripting adapter
   - local model adapters
   - OpenAI/Claude provider adapters
   - Pexels/Pixabay asset-source adapters
   - filesystem artifact store
   - optional future ComfyUI generation adapter (outside MVP delivery)

## 4. Repository layout

Recommended source layout:

```text
rambla-reel-director/
  AGENTS.md
  pyproject.toml                  # when implementation begins
  backend/
    app/
      api/
      orchestration/
      domain/
        projects/
        style_dna/
        transcript/
        director/
        assets/
        retrieval/
        stickers/
        plans/
        apply/
        benchmarks/
      ports/
      adapters/
        resolve/
        ai/
        asset_sources/
        generation/
        persistence/
      observability/
      schemas/
  resolve-panel/
  tests/
    unit/
    contract/
    integration/
    golden/
  docs/
    superpowers/specs/
    PROJECT_BRIEF.md
    ARCHITECTURE.md
    DECISIONS.md
    NEXT_TASK.md
  examples/
    config/
```

Runtime/client data is **not** stored inside tracked source directories.

Suggested configurable default data root on the user's SSD:

```text
Z:\RAMBLA-reel-data\
  clients\
  runs\
  cache\
  downloads\
  previews\
  logs\
  models\
```

This default must remain configurable.

## 5. Core persisted entities

All persisted objects include:

- `schema_version`
- stable `id`
- `created_at`
- `updated_at` where mutable
- provenance/source metadata
- content hash where freezing/replay matters

Persisted JSON MUST validate against a checked-in schema identified by
`schema_version`. Unknown major versions MUST be rejected; additive unknown
fields in a compatible minor version MAY be preserved but MUST NOT silently
change domain behavior. Migrations MUST be explicit, deterministic, preserve
the original artifact, and record source/target versions plus the migration
tool version. IDs are opaque UUIDs; timestamps are UTC RFC 3339 strings.

### 5.1 Client

Required fields:

```text
id
slug
display_name
status
default_style_id
asset_roots[]
library_roots[]
reference_roots[]
brand
policies
```

`brand` contains logical references to logos, fonts, palette, and usage rules. Binary assets remain local.

`policies` controls:

- permitted asset sources
- cloud-provider permission
- generation permission
- attribution/licensing constraints
- export/privacy constraints

### 5.2 Project

Required fields:

```text
id
client_id
name
status
resolve_project_ref
source_timeline_ref
style_dna_id
style_dna_version
provider_profile
edit_controls
run_ids[]
```

A Project references an approved Style DNA version but a run always snapshots the resolved style so later style changes do not alter historical runs.

### 5.3 StyleDNA

```text
id
client_id
name
version
status: candidate | approved | retired
editorial
visual
content
sound
evidence[]
approved_by
approved_at
```

#### Editorial DNA

Includes at least:

- pacing profile
- preferred shot-duration range
- B-roll density
- talking-head retention
- punch-in frequency/intensity
- visual-interruption frequency
- maximum consecutive B-roll duration
- hook/body/payoff rhythm rules

#### Visual DNA

Includes at least:

- typography family references
- weight hierarchy
- caption scale/position
- stroke/outline/shadow
- palette
- keyword-emphasis rules
- sticker language
- card/callout language
- transition preferences
- animation language
- visual hierarchy

Exact font identity from references is never assumed certain; inferred values include confidence and require user confirmation.

#### Content DNA

Weighted preferences for:

- real footage
- archival
- screenshots
- documents
- editorial stills
- generic stock
- memes
- generated visuals

#### Sound DNA

Schema may exist but advanced automation is deferred.

### 5.4 VisualAsset

```text
id
type
source
ownership_scope
client_id?
local_path?
remote_url?
preview_path?
duration?
width?
height?
aspect_ratio
safe_crop
semantic_tags[]
embedding_ref?
license
attribution
source_identifier
quality_score?
relevance_score?
confidence?
content_hash?
cache_state
```

Asset `type` supports:

`VIDEO | IMAGE | DOCUMENT | SCREENSHOT | STICKER | GRAPHIC | MEME | ARCHIVAL | GENERATED`

`ownership_scope` is at least:

`CLIENT | GLOBAL | REMOTE | GENERATED`

MVP disables `GLOBAL` lookup even though the schema permits it.

### 5.5 EditPlan

```text
id
run_id
version
status
source_timeline_snapshot
source_timeline_hash
target_timeline_name
style_snapshot_ref
controls_snapshot
provider_trace[]
decisions[]
validation
approval
apply_result?
```

Status:

`draft | in_review | approved | applying | applied | failed | superseded`

Each decision contains:

```text
id
start_time?
end_time?
time?
action
intent
reason
confidence
queries[]
candidate_refs[]
selected_asset_ref?
parameters
review_state
provenance
```

Initial actions:

`BROLL | EDITORIAL_INSERT | PUNCH_IN | STICKER | CAPTION_EMPHASIS`

Review state:

`proposed | approved | modified | disabled | needs_replacement`

Approval freezes the full semantic content of the plan and stores a
deterministic hash. The hash input is UTF-8 RFC 8785 canonical JSON of the
entire plan except `approval`, `apply_result`, and non-semantic storage
metadata (`created_at`, `updated_at`, and filesystem paths derived from the
artifact root). It includes `schema_version`, source/style/control snapshots,
decisions, validation results, selected-asset hashes, and policy snapshot. The
algorithm is SHA-256 and the stored form is `sha256:<lowercase-hex>`. Approval
MUST record actor, UTC timestamp, and hash. Any semantic edit creates a new
draft version and invalidates the prior approval; an approved artifact is
never edited in place.

## 6. Run artifacts

Every analysis run receives one stable `run_id`.

Recommended artifact tree:

```text
runs/<run_id>/
  run.json
  timeline_snapshot.json
  transcript.json
  alignment.json
  style_snapshot.json
  director_output.json
  queries.json
  candidate_assets.json
  ranking.json
  selected_assets.json
  edit_plan.v001.json
  edit_plan.approved.json
  apply_report.json
  benchmark.json
  logs.jsonl
```

Artifacts are immutable once written successfully. Writers MUST use a
temporary file in the same filesystem, flush it, then atomically rename it to
the final versioned path. A manifest in `run.json` records logical artifact
name, version, schema version, SHA-256, producing step attempt, and dependency
hashes. A rerun writes a new version and marks descendants stale in the
manifest; it never edits or deletes an earlier artifact. A consumer MUST reject
an artifact whose recorded dependency hashes no longer match current selected
upstream versions.

## 7. Orchestration state machine

Each step uses:

`pending | running | succeeded | failed | skipped | stale`

Allowed transitions are:

- `pending -> running | skipped`
- `running -> succeeded | failed`
- `failed -> running`
- `succeeded | skipped -> stale` when a selected input changes
- `stale -> running | skipped`

Each execution has a monotonic attempt number. At most one attempt for a given
`run_id` and step may be `running`; acquisition uses an atomic run lease with
owner, acquired time, heartbeat, and expiry. Recovery of an expired lease is
recorded, never inferred silently. A step becomes `succeeded` only after all
outputs are durably written and validated. Cancellation is represented as a
typed failure (`RUN_CANCELLED`) in MVP, not as an unrecorded process exit.

Initial pipeline:

1. `capture_timeline`
2. `extract_analysis_media`
3. `transcribe`
4. `align`
5. `resolve_style`
6. `direct`
7. `plan_queries`
8. `collect_candidates`
9. `rank_candidates`
10. `build_plan`
11. `validate_plan`
12. `review`
13. `freeze_plan`
14. `preflight_apply`
15. `duplicate_timeline`
16. `apply_operations`
17. `verify_apply`
18. `finalize_metrics`

Dry Run ends after `validate_plan` or user review/freeze, depending on UI mode, and never executes steps 14–17.

`review` is a user-controlled wait state, not a background compute step.
`freeze_plan` requires every enabled decision to have a terminal review state
and a successful validation against the exact plan version. `preflight_apply`
requires an approved hash and acquires the apply lease. No Analyze or Dry Run
command can enqueue or call steps 14–17.

## 8. Domain ports

Interfaces are capability-based rather than vendor-based.

All port calls MUST accept an operation/request ID and return a typed result or
typed error; adapters MUST NOT leak vendor exceptions into domain services.
Errors carry `code`, `category`, `retryable`, `message`, and redacted
`diagnostic_id`. Retrying a mutating call with the same operation ID MUST be
idempotent. Timeouts and cancellation are explicit inputs at adapter
boundaries. Concrete request/response schemas are frozen in Slice 0 before the
first real adapter is implemented and are exercised by the shared contract
suite.

### ResolveAdapter

Minimum MVP capabilities:

- inspect current project and timeline
- read timeline metadata/timebase
- enumerate relevant media items
- capture immutable timeline snapshot
- export/extract analysis audio/video where needed
- duplicate timeline
- create/identify tracks
- import local assets
- place/trim items at frame-accurate positions
- apply basic transforms/punch-ins
- apply supported titles/caption-emphasis primitives
- apply supported sticker/graphic overlays
- verify expected timeline state

Every capability is explicitly discoverable. Unsupported features fail preflight before mutation.

The minimum normative surface is:

```text
capabilities() -> ResolveCapabilities
inspect_context() -> ResolveContext
capture_timeline(TimelineRef) -> TimelineSnapshot
extract_analysis_media(TimelineRef, ExtractionRequest) -> MediaArtifact
preflight_apply(ApprovedPlanRef, TimelineSnapshotHash) -> PreflightResult
duplicate_timeline(SourceTimelineIdentity, AllocatedTargetName, OperationId) -> TargetTimelineIdentity
apply_operation(TargetTimelineIdentity, ApplyOperation, OperationId) -> OperationResult
verify_apply(TargetTimelineIdentity, ExpectedTimelineState) -> VerificationResult
discard_generated_timeline(TargetTimelineIdentity, OperationId) -> OperationResult
```

`SourceTimelineIdentity` and `TargetTimelineIdentity` use stable Resolve
identifiers when exposed by the compatibility spike. If Resolve exposes no
stable ID, the spike MUST define a compound identity and its collision/freshness
limits; name alone is forbidden. Every mutating method requires the target
identity returned by `duplicate_timeline`; the adapter MUST reject the captured
source identity and any target not registered to the current apply attempt.
Capability discovery is a persisted, versioned matrix, not a collection of
best-effort runtime guesses.

### AI/provider ports

- `TranscriptionProvider`
- `AlignmentProvider`
- `DirectorProvider`
- `EmbeddingProvider`
- `RerankProvider`
- `VisualJudgeProvider`

### AssetSource

- search
- fetch preview metadata
- fetch/download selected asset
- expose licensing/provenance

Search receives `client_id`, a frozen policy snapshot, locale, pagination
token, and request ID. Results MUST be normalized before ranking. Download
receives an already selected remote asset and writes only into the requesting
client/run namespace. Provider terms that do not yield sufficient license and
attribution evidence make the candidate ineligible rather than partially
populated.

Initial adapters:

- client-local
- Pexels
- Pixabay

### GenerationProvider

Optional. First planned implementation is ComfyUI, but no core flow depends on it.

## 9. Local AI baseline and benchmarking

Candidate stack to benchmark, not to assume:

- transcription: Qwen3-ASR-1.7B
- alignment: Qwen3-ForcedAligner-0.6B
- Director: Qwen3.5-4B
- quality Director candidate: Qwen3.5-9B
- retrieval embedding: Qwen3-VL-Embedding-2B
- reranking: Qwen3-VL-Reranker-2B
- visual judge: Qwen3.5-4B only when confidence gating justifies it

### Benchmark rule

No model is promoted to default solely because it is newer, larger, or quantized.

Measure:

- cold-load time
- warm latency
- VRAM peak
- RAM
- throughput
- result quality
- acceptance rate impact

Profiles:

- `LOCAL_FAST`
- `LOCAL_LOW_VRAM`
- `LOCAL_QUALITY`
- later `OPENAI`, `CLAUDE`, `AUTO`

Quantization is evaluated only after a precision baseline.

## 10. Editorial Director contract

The Director receives:

- transcript + aligned timings
- read-only timeline snapshot
- immutable Style DNA snapshot
- edit-control overrides
- allowed action types
- provider/client policies

The Director outputs semantic decisions only. It does **not** select final files and does **not** mutate Resolve.

Every decision must explain:

- what visual interruption is wanted
- why it belongs at that time
- what semantic intent it should communicate
- confidence
- one or more candidate search formulations when an external visual is needed

The Query Planner then converts intent into diverse concrete searches. This separation prevents retrieval limitations from contaminating editorial reasoning.

## 11. Retrieval and ranking

Candidate flow:

1. Client-local semantic lookup.
2. Pexels/Pixabay search when permitted.
3. Normalize results as `VisualAsset`.
4. Cheap filters:
   - licensing/policy
   - duration
   - aspect/crop feasibility
   - duplicates
   - obvious low-quality previews
5. Multimodal embedding shortlist.
6. Rerank shortlist.
7. Optional visual judge only when top results are ambiguous or confidence is below threshold.
8. Diversity/off-brand/repetition checks.
9. Download full-quality winner only after selection.

The system must retain ranking evidence so a rejected choice can be diagnosed.

## 12. Style DNA Analyzer

Inputs may include local reel references, screenshots, graphics, font files present locally, and other client references. Reference media is never committed.

Analyzer outputs a **Candidate Style DNA**, never an automatically approved style.

Extractable evidence may include:

- cut/shot-duration distributions
- face vs insert occupancy
- B-roll density
- caption position/size/color patterns
- keyword emphasis frequency
- punch-in cadence
- sticker/callout frequency
- insert categories
- framing tendencies
- hook/body/payoff pacing

Inferences that cannot be reliable—especially exact font identity, creative intent, or brand meaning—must carry confidence and be editable.

## 13. Apply safety model

Apply is a two-phase operation.

### Phase A — Preflight

Verify:

- approved plan hash is unchanged
- source timeline matches captured snapshot within defined tolerances
- required assets exist and hashes match
- Resolve capabilities needed by this plan are available
- source timeline is not the target of mutation
- target name can be allocated
- frame-rate/timebase conversions are valid

Any failure aborts before mutation.

Preflight is valid only for the approved plan hash, captured source identity
and hash, capability-matrix version, selected-asset hashes, and current Resolve
session observed at preflight. Any change forces a new preflight. Apply is
serialized per Resolve project and uses an expiring lease; concurrent apply
attempts for the same project are rejected.

### Phase B — Mutation and verification

1. Duplicate source timeline.
2. Rename target (`REEL_AI_v01`, with collision-safe incrementing).
3. Apply idempotent operations identified by operation IDs.
4. Verify expected items/transforms/tracks.
5. Persist apply report.

The first mutation permitted is duplication. After duplication, every mutation
MUST target the returned target identity. The operation journal is durably
written before and after each adapter call and records operation ID,
precondition, outcome, and postcondition. A retry reconciles the journal and
observed target state before issuing another mutation.

If an operation fails mid-apply, report partial state clearly. MVP does not
promise transactional rollback. Discarding the generated duplicate is a
separate, explicit user-approved cleanup command, MUST verify that the identity
belongs to this apply attempt, and MUST never be automatic after an ambiguous
adapter timeout. Until cleanup is approved, retry may resume only when
postconditions prove which operations completed; otherwise the attempt remains
failed and requires a new duplicate. The untouched source is always retained.

## 14. Time model

Internally, timeline operations are frame-based using the captured timeline timebase. Human-facing seconds/timecodes are derived representations.

The canonical interval is half-open `[start_frame, end_frame)` using signed
64-bit integer frame indices relative to the captured timeline start. A
timebase is the reduced rational `frames_per_second_num/frames_per_second_den`
plus drop-frame flag and timeline start timecode. Floating-point seconds MUST
NOT be used for placement, hashing, or collision checks. Conversion and
rounding rules are frozen in the timing schema and shared by validation and the
Resolve adapter.

Required invariants:

- no negative durations
- no out-of-range placement
- stable frame ↔ timecode conversion
- VFR source media must be normalized/mapped explicitly before frame-accurate assumptions
- speech alignment confidence is persisted
- `start_frame < end_frame` for ranged decisions
- point decisions use `frame`, never a zero-length interval
- all decision ranges lie within the captured timeline range
- overlapping decisions are accepted only by an explicit action/track policy
- source-media time mappings record source timebase, trims, speed changes, and
  normalization provenance

## 15. Panel behavior

MVP panel surface:

- Client selector
- Project selector
- Style DNA selector/version
- Timeline selector/current timeline
- AI profile selector
- source toggles
- edit-density controls
- Analyze
- progress
- Review Plan
- Dry Run report
- Approve/Freeze
- Apply

Review list supports per decision:

- preview
- approve
- disable
- modify parameters
- replace candidate
- regenerate query/choice

The UI talks only to backend API contracts.

## 16. Resolve compatibility spike

Before implementing the real panel/apply adapter, run a bounded compatibility spike against the user's installed Resolve Studio build.

Record:

- Resolve exact version
- scripting API version/availability
- Workflow Integration support and packaging requirements
- timeline duplication support
- media import and frame placement behavior
- transform controls
- Text+/caption capabilities
- Fusion title limitations
- scripting access while UI panel is active
- error behavior

Outcome is a capability matrix checked into docs. Domain interfaces change only if the probe proves the proposed capability boundary impossible.

## 17. Cloud-provider policy

First vertical slice is local-first.

OpenAI and Claude share the `DirectorProvider` contract and are added as benchmark/quality adapters only after the local end-to-end pipeline is proven. No cloud provider receives client content unless the client's/run's policy explicitly allows it.

`AUTO` routing is deferred until there is real confidence telemetry.

Permission is deny-by-default and is evaluated immediately before every remote
request against the frozen run policy. The request record contains provider,
data classes sent, purpose, policy decision, and redacted response provenance.
Transcripts, frames, filenames, and metadata are distinct data classes so a
permission for one does not imply the others. Revocation prevents future
requests but does not rewrite historical artifacts.

## 18. Security, privacy, provenance

- Secrets only via local secret/config mechanisms; never Git.
- Client media remains local unless an explicit provider action requires upload and policy allows it.
- Every remote asset retains provider/source ID and license/attribution metadata.
- Client asset isolation is enforced in domain queries, not just directory naming.
- Logs must redact secrets and avoid unnecessary raw client content.
- Generated assets retain generation provenance.
- Cache, download, preview, embedding, and temporary paths are namespaced by
  ownership scope and `client_id`; cache keys include the scope. Domain access
  requires the requesting `client_id` even when a caller knows another asset ID
  or path.
- Local paths are canonicalized and checked against configured roots before
  access. Symlinks, junctions, `..`, case differences, and alternate Windows
  path forms MUST NOT bypass root or client boundaries.
- Remote downloads use size/type limits, content sniffing, quarantine before
  validation, and a content hash before becoming eligible assets.
- Logs and provider traces store references/hashes instead of raw transcript or
  media content unless a diagnostic mode is explicitly enabled for that run.

## 19. Observability

Every log/event includes:

- `run_id`
- module
- step
- provider/model where relevant
- elapsed time
- status
- error code/category

Provider telemetry includes load/warm state, latency, memory/cost where available, and confidence without secrets.

UI errors should expose a short message plus a diagnostic ID linking to detailed local logs.

## 20. Testing

### Unit

- schemas and migrations
- timing math
- policy enforcement
- query planning
- ranking/diversity rules
- plan validation
- deterministic hashes

### Contract

Shared compliance suites for each port:

- ResolveAdapter
- AI providers
- AssetSource
- GenerationProvider
- ArtifactStore

Every port's suite covers success, typed failure, timeout, cancellation,
idempotent retry, unsupported capability, malformed vendor response, and
redaction. Resolve contract tests additionally prove source-identity rejection
for every mutating method and no mutation after failed preflight.

### Integration

- fake Resolve adapter
- fake providers
- filesystem run store
- full Analyze pipeline without installed Resolve

### Golden editorial tests

Use small consented fixtures with expected structural properties. Golden tests should not pretend taste is completely deterministic; they assert invariants and track decision deltas.

### Resolve smoke tests

Dedicated local fixture project, always on duplicated timelines.

## 21. Metrics and acceptance

Per run:

- stage latency
- cold/warm model load time
- peak VRAM/RAM where measurable
- remote cost if applicable
- number of proposed decisions
- approve/modify/disable/replace counts
- results by action type

Primary quality metric:

`acceptance_rate = decisions_kept_without_material_change / reviewed_decisions`

Also report replacement rate and disable rate separately so the metric cannot hide poor asset selection.

`reviewed_decisions` excludes decisions that have not reached a terminal review
state. “Material change” is versioned and initially means a changed action,
selected asset, interval by more than the action-specific tolerance, or any
parameter marked editorially material in the decision schema. Reports MUST
include the metric-definition version and raw counts. MVP quality sign-off
requires a checked-in benchmark protocol and human-approved thresholds; this
spec deliberately does not invent a universal acceptance-rate target before a
baseline is measured.

## 22. MVP delivery sequence

### Slice 0 — compatibility and contracts

- freeze schemas/interfaces
- fake providers and fake Resolve
- Resolve capability spike

### Slice 1 — local Analyze path

- timeline snapshot fixture
- transcription/alignment
- Style DNA snapshot
- Director
- draft plan
- inspectable artifacts

### Slice 2 — retrieval and review

- client-local + Pexels/Pixabay
- embedding/reranking baseline
- Review Plan flow
- freeze approved plan

### Slice 3 — Resolve Apply

- preflight
- duplicate timeline
- B-roll/punch-in/basic overlay application
- verification/apply report

### Slice 4 — editorial breadth required for MVP

- editorial inserts
- sticker/callout path
- caption emphasis within proven Resolve capability
- acceptance telemetry

### Slice 5 — quality benchmark

- compare local profiles
- optionally implement OpenAI and Claude adapters
- benchmark against the same fixtures/reels
- keep cloud adapters only if they provide practical quality value

## 23. MVP acceptance criteria

MVP is considered technically complete only when:

1. Backend runs without Resolve installed/started using fake adapters.
2. A real Resolve Studio timeline can be captured without mutation.
3. Analyze creates all required persisted artifacts and a valid draft Edit Plan.
4. User can review/change/disable/replace decisions and freeze a deterministic approved plan.
5. Dry Run performs zero timeline mutations.
6. Apply never mutates the source timeline.
7. Apply creates a duplicate and places supported decisions at frame-accurate positions.
8. Failed preflight performs zero mutation.
9. Client-local assets cannot leak into another client's search.
10. Provenance/license metadata survives from candidate to selected asset to Edit Plan.
11. A failed/changed step can be rerun without rerunning unrelated upstream work.
12. Metrics report acceptance/replacement/disable rates and stage timings.
13. Model/provider choice can be changed without changing domain schemas.
14. No ComfyUI dependency is required for the core flow.
15. Approved-plan hashes are stable across repeated serialization and reject
    every semantic mutation covered by the schema.
16. Crash/retry tests prove artifact atomicity, stale propagation, single-step
    lease recovery, and Apply operation reconciliation.
17. Every mutating Resolve contract test rejects the source identity, an
    unregistered target, and an expired/mismatched preflight.
18. Two-client adversarial tests prove isolation across catalog queries, direct
    asset-ID lookup, caches, previews, downloads, embeddings, logs, and path
    aliases/junctions.
19. Timing property tests cover integer and NTSC rational rates, drop-frame
    display, non-zero timeline starts, trims, speed changes, and declared VFR
    normalization behavior.
20. Cloud tests prove deny-by-default behavior and that each transmitted data
    class requires explicit policy permission.
21. The Slice 0 capability matrix resolves every `TBD_BY_SPIKE` required by the
    selected first vertical slice; unsupported decision types fail preflight or
    are excluded before approval.
22. The benchmark protocol records fixture consent/provenance, metric version,
    local hardware/software versions, warm/cold procedure, raw counts, and
    human-approved MVP thresholds.

## 24. Known risks and mitigations

### Resolve API gaps

Mitigation: early capability spike, small adapter surface, preflight failure before mutation, feature degradation rather than hidden failure.

### Editorial quality

Mitigation: explicit reasons/intent, Style DNA, review telemetry, repeatable benchmark fixtures, provider A/B testing.

### Visual relevance vs visual taste

Mitigation: separate embedding/reranking from optional VLM judge; retain evidence; add diversity/off-brand rules.

### Windows model lifecycle/load latency

Mitigation: model manager, cold/warm benchmarks, lazy load, measured resident profiles; avoid premature worker architecture.

### Schema/cache evolution

Mitigation: schema versions, hashes, immutable artifacts, stale propagation, explicit migration/version handling.

### Licensing/privacy

Mitigation: provenance as required schema data and explicit per-client cloud/source policy.

## 25. Technical-review disposition and open decisions

The review closed the safety and consistency gaps around canonical approval
hashing, immutable artifacts, orchestration leases/transitions, typed adapter
errors, Resolve target identity, Apply journaling/recovery, rational frame time,
client-scoped storage, cloud data classes, and adversarial acceptance tests.

The specification is internally consistent with D-001 through D-020, but it is
**not yet sufficiently concrete for final approval**. The following decisions
must be resolved in this document before the implementation-plan gate opens:

1. **Freeze v1 schemas.** Define the closed JSON shapes and field types for
   `Run`, `TimelineSnapshot`, `Transcript`, `Alignment`, `StyleDNA`,
   `VisualAsset`, `EditPlan`, `ApplyOperation`, `ApplyReport`, policy snapshots,
   manifests, and typed errors. The field sketches in section 5 are not exact
   schemas.
2. **Freeze API contracts.** Define the MVP HTTP resources/commands, request and
   response schemas, status codes, idempotency semantics, concurrency behavior,
   SSE event envelope, replay cursor, and reconnect behavior.
3. **Freeze port contracts.** Replace capability bullet lists with exact typed
   method inputs/outputs for every MVP port, including transcription,
   alignment, direction, retrieval/reranking, artifact storage, and asset
   sources. The Resolve surface above is only the minimum safety boundary.
4. **Freeze decision and operation semantics.** Specify required parameters,
   validation rules, track/layer policy, collision policy, and verification
   postconditions for each of the five MVP action types.
5. **Resolve Dry Run semantics.** Choose whether the named Dry Run product
   command stops at validated draft or may include review/freeze; one command
   must have one deterministic terminal state and artifact set.
6. **Define retention/deletion policy.** Set lifecycle rules for client/run
   artifacts, quarantined downloads, caches, logs, cloud request records, and
   generated duplicate timelines. Cleanup authorization and audit behavior
   must be explicit.
7. **Approve the benchmark protocol and thresholds.** The protocol may measure
   a baseline before numeric thresholds are chosen, but the authority, sample
   set, minimum evidence, and rule for MVP sign-off must be explicit.

Resolve-version-specific capability values may remain `TBD_BY_SPIKE` because
D-018 and D-019 explicitly gate them on the compatibility probe. The data and
interface contracts that do not depend on that probe may not be deferred to
implementation or silently decided in an implementation plan.

## 26. Approval gate

This document freezes the intended MVP architecture and technical contracts
only after section 25 is resolved and the user explicitly approves the revised
specification. After approval, the next step is an implementation plan produced
from this spec. No application implementation should begin before that plan is
reviewed and approved.
