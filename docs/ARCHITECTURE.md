# Architecture Proposal — RAMBLA REEL DIRECTOR

Status: **proposal awaiting explicit approval**. This document defines architecture only; it authorizes no product implementation.

## Options considered

### A. Modular monolith with ports and adapters — recommended

One local backend process contains independently testable domain modules. External systems—Resolve, AI models, cloud LLMs, stock providers, storage, and ComfyUI—are accessed through typed ports with replaceable adapters. A durable run store and explicit step orchestrator connect the modules.

Benefits: fastest path to an observable MVP, simple local deployment, easy debugging, no premature distributed-systems cost, and clean future extraction points. Trade-off: module boundaries require discipline because process isolation does not enforce them.

### B. Local service mesh / worker processes

API, orchestration, model inference, retrieval, and Resolve integration run as separate local services or workers.

Benefits: stronger isolation, independent model lifecycle, and better crash containment. Trade-offs: substantially more packaging, IPC, versioning, retries, observability, and Windows support work before editorial value can be tested.

### C. Workflow engine with event-sourced decisions

Every pipeline step is a command/event in a durable workflow, with decisions and revisions represented as an append-only history.

Benefits: excellent replay, auditability, and long-running recovery. Trade-offs: highest conceptual and implementation overhead; premature for one-user MVP unless resumability requirements prove unusually strict.

## Recommendation

Choose **A: modular monolith with ports and adapters**, while borrowing two ideas from C: immutable run artifacts and explicit state transitions. This makes editorial experiments cheap and inspectable without locking the product into a monolith: ports preserve replacement boundaries, and versioned schemas preserve migration paths.

## System boundaries

### Resolve Panel

Thin client only: context selection, intensity controls, run progress, plan review, preview, per-decision edits, approval, Apply, Undo, and errors. It does not host models or editorial logic.

### Local API and Run Orchestrator

FastAPI is the recommended control plane; WebSocket or server-sent events carry progress. The orchestrator executes explicit resumable steps, records status, and never calls Apply during Analyze.

### Domain services

- **Project Manager:** client/project/run identity, paths, configuration, and isolation rules.
- **Style DNA:** validation, versions, candidate analysis, approval, and resolution into a run snapshot.
- **Transcript Engine:** transcription, word/segment alignment, timing confidence, and persisted artifacts.
- **Editorial Director:** turns transcript plus style and controls into semantic edit decisions; it never selects final files or mutates Resolve.
- **Query Planner:** expands editorial intent into diverse, concrete visual searches.
- **Asset Catalog:** normalizes local and remote media into `VisualAsset` records.
- **Retrieval and Ranking:** candidate retrieval, multimodal similarity, reranking, optional judge, diversity, and policy filters.
- **Sticker Engine:** client/global/generated sticker candidates under Style DNA constraints.
- **Plan Service:** validates, versions, diffs, edits, approves, and freezes Edit Plans.
- **Apply Service:** converts an approved frozen plan into adapter operations with idempotency and rollback metadata.
- **Benchmark Service:** captures latency, VRAM, cost, acceptance, replacements, and failure data.
- **Provider Registry / Model Manager:** capability-based provider selection, lazy load/unload, resource budgets, and health.

### Ports and adapters

- `ResolveAdapter`: inspect project/timeline, export media, duplicate timeline, import assets, create tracks/items, apply transforms/titles/captions, and verify results.
- `DirectorProvider`: local Qwen, OpenAI, Claude, and future Auto routing.
- `TranscriptionProvider`, `AlignmentProvider`, `EmbeddingProvider`, `RerankProvider`, `VisualJudgeProvider`.
- `AssetSource`: client library, global library, Pexels, Pixabay, and future commercial sources.
- `GenerationProvider`: optional ComfyUI adapter; the system remains functional when unavailable.
- `ArtifactStore` and `RunRepository`: filesystem-first MVP implementations behind interfaces.

## Data flow

1. Panel creates an analysis run using client, project, timeline, Style DNA version, provider profile, and edit controls.
2. ResolveAdapter captures a read-only timeline snapshot and exports only necessary analysis media.
3. Transcript and alignment steps persist versioned outputs.
4. The approved Style DNA is resolved into an immutable run snapshot.
5. Editorial Director emits intent-level decisions with reasons and confidence.
6. Query Planner produces multiple semantic queries per visual intent.
7. Asset sources yield normalized candidates; policy filters enforce client isolation, licensing, aspect, duration, and crop safety.
8. Embedding retrieval, reranking, and an optional confidence-gated visual judge select candidates.
9. Plan Service validates timing, collisions, density constraints, and required provenance; it writes a draft Edit Plan.
10. User reviews and revises decisions. Approval freezes a version and hash.
11. Dry Run stops here and emits reports/previews.
12. Apply verifies the approved hash, duplicates `REEL_MASTER`, targets `REEL_AI_v01`, executes idempotent operations, and verifies the result.

## Preliminary schemas

All persisted objects carry `schema_version`, stable IDs, timestamps, and provenance. Exact fields will be frozen in the technical specification.

### Client

- `id`, `slug`, `display_name`, `status`
- `default_style_id`
- `asset_roots`, `library_roots`, `reference_roots`
- `brand`: logos, fonts, palette, usage constraints
- `policies`: allowed sources, licensing, generation, cloud use

### Project

- `id`, `client_id`, `name`, `status`
- `resolve_project_ref`, `source_timeline_ref`
- `style_dna_id`, `style_dna_version`
- `media_manifest_ref`, `run_ids`
- `provider_profile`, `edit_controls`

### StyleDNA

- `id`, `client_id`, `name`, `version`, `status` (`candidate|approved|retired`)
- `editorial`: pacing, shot duration, densities, retention, interruption and rhythm rules
- `visual`: typography, palette, caption layout, hierarchy, stickers, cards, transitions, animation
- `content`: source-type preferences and weights
- `sound`: optional MVP-deferred preferences
- `evidence`: reference analyses and confidence
- `approved_by`, `approved_at`

### EditPlan

- `id`, `run_id`, `version`, `status` (`draft|in_review|approved|applied|failed`)
- `source_timeline_snapshot`, `target_timeline_name`
- `style_snapshot_ref`, `controls_snapshot`, `provider_trace`
- `decisions[]`: stable ID, interval/time, action, intent, reason, confidence, queries, candidate refs, selected asset, parameters, review state
- `validation`: timing/collision/policy results
- `approval`: actor, timestamp, frozen content hash
- `apply_result`: operation log, verification, rollback/undo metadata

### VisualAsset

- `id`, `type`, `source`, `ownership_scope`, `client_id`
- `local_path` or `remote_url`, `preview_path`
- `duration`, `dimensions`, `aspect_ratio`, `safe_crop`
- `semantic_tags`, `embedding_ref`
- `license`, `attribution`, `source_identifier`
- `quality_score`, `relevance_score`, `confidence`
- `content_hash`, `cache_state`

## Persistence and client isolation

Runtime/client data should live outside tracked source directories. A configurable data root contains `clients/<client-id>/...` and `runs/<run-id>/...`. Every asset and run carries an ownership scope. Cross-client lookup is denied by default; a separate global library must be explicitly enabled.

Git tracks schemas, code, tests, non-sensitive configuration examples, and documentation only.

## Debug strategy

- One `run_id` propagated through every log, artifact, provider call, and apply operation.
- Structured JSON logs by module and step; human-readable summaries in the UI.
- Inspectable immutable artifacts: timeline snapshot, transcript, alignment, style snapshot, director output, queries, candidates, ranking evidence, selected assets, plan versions, and apply report.
- Explicit step state machine: pending, running, succeeded, failed, skipped, invalidated.
- Rerun one step from validated upstream artifacts; downstream artifacts become stale rather than silently reused.
- Content hashes and schema versions make cache behavior explainable.
- Provider/model timing, memory, cost, and confidence captured without secrets.

## Testing strategy

- Unit tests for schemas, policies, timing math, query planning, ranking rules, and plan validation.
- Contract tests for every provider and adapter port using shared compliance suites.
- Golden-file tests for transcript-to-plan behavior on consented, non-private fixtures.
- Property tests for timeline invariants: no negative durations, overlaps only when allowed, frame/time conversion stability, and deterministic plan hashes.
- Integration tests with fake Resolve and fake providers; no Resolve installation required in CI.
- Resolve smoke tests in a dedicated local fixture project, always on duplicated timelines.
- Acceptance evaluation records approve/modify/disable/replace outcomes by decision type and Style DNA.

## Resolve integration strategy

Start with a fake adapter and a capability matrix validated against the actual Resolve Python API. Keep MCP as an optional adapter or external-agent façade, never a domain dependency. Apply is a two-phase operation: preflight and duplicate first, mutation second. Every operation has an idempotency key and postcondition. Unsupported Resolve capabilities fail preflight before timeline mutation.

## Local AI architecture

Use a capability-oriented Model Manager rather than a single resident model. Profiles:

- **Fast:** Director and embedding model resident when measurements justify it.
- **Low VRAM:** one model loaded at a time with explicit unload and cache controls.
- **Quality:** stronger local or cloud provider selected explicitly.

Candidate models—Qwen3-ASR-1.7B, Qwen3-ForcedAligner-0.6B, Qwen3.5-4B/9B, Qwen3-VL-Embedding-2B, and Qwen3-VL-Reranker-2B—remain hypotheses. Benchmark baseline precision first, then BF16/FP16 and only later FP8/INT8/4-bit when measured quality, latency, and VRAM justify them. Auto cloud escalation is post-MVP.

## MVP boundaries

The first vertical slice should prove the complete approval loop on one 9:16 talking-head timeline and one approved Style DNA. Limit sources to client library plus Pexels/Pixabay adapters, decision types to B-roll/editorial insert/punch-in/sticker/caption emphasis, and one Resolve adapter implementation. Generated media, learning, music, horizontal formats, multi-user/cloud collaboration, and sophisticated SFX remain out.

## Principal risks

- Resolve API capability gaps for Fusion/Text+, captions, transforms, and reliable undo.
- Frame-rate, timecode, variable-frame-rate, and alignment errors causing unsafe edits.
- Editorial quality being difficult to measure; acceptance telemetry needs consistent review semantics.
- Reference analysis cannot reliably identify exact fonts or infer intent without user correction.
- Licensing and provenance vary by source and must be first-class data.
- Multimodal rankings may be semantically relevant but visually repetitive, unsafe to crop, or off-brand.
- Local model memory contention and load latency on Windows despite ample VRAM.
- Panel technology and Resolve version support may constrain UI architecture.
- Schema evolution can invalidate cached artifacts and approved plans unless versions and hashes are strict.
- Cloud providers create privacy, cost, and determinism concerns and must be explicit per client/run.

