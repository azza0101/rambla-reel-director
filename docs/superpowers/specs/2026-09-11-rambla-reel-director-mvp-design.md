# RAMBLA Reel Director — MVP Technical Design

Date: 2026-09-11
Status: **draft for human review; implementation is not yet authorized**

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
   - optional ComfyUI generation adapter

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

Approval freezes the full semantic content of the plan and stores a deterministic hash.

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

Artifacts are immutable once a downstream step has consumed them. A rerun writes a new version and marks descendants stale.

## 7. Orchestration state machine

Each step uses:

`pending | running | succeeded | failed | skipped | stale`

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

## 8. Domain ports

Interfaces are capability-based rather than vendor-based.

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

### Phase B — Mutation and verification

1. Duplicate source timeline.
2. Rename target (`REEL_AI_v01`, with collision-safe incrementing).
3. Apply idempotent operations identified by operation IDs.
4. Verify expected items/transforms/tracks.
5. Persist apply report.

If an operation fails mid-apply, report partial state clearly. MVP does not promise magical transactional rollback; instead it can discard the generated duplicate and retry from the untouched master.

## 14. Time model

Internally, timeline operations are frame-based using the captured timeline timebase. Human-facing seconds/timecodes are derived representations.

Required invariants:

- no negative durations
- no out-of-range placement
- stable frame ↔ timecode conversion
- VFR source media must be normalized/mapped explicitly before frame-accurate assumptions
- speech alignment confidence is persisted

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

## 18. Security, privacy, provenance

- Secrets only via local secret/config mechanisms; never Git.
- Client media remains local unless an explicit provider action requires upload and policy allows it.
- Every remote asset retains provider/source ID and license/attribution metadata.
- Client asset isolation is enforced in domain queries, not just directory naming.
- Logs must redact secrets and avoid unnecessary raw client content.
- Generated assets retain generation provenance.

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

## 25. Approval gate

This document freezes the intended MVP architecture once the user explicitly approves it. After approval, the next step is an implementation plan produced from this spec. No application implementation should begin before that plan is reviewed and approved.
