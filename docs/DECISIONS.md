# Architecture Decision Log

Only explicitly approved decisions belong in the approved section. Superseded or future choices stay separate until accepted.

## Approved

### D-001 — Edit Plan before mutation

AI reasoning produces a structured, persisted, inspectable, editable Edit Plan. Resolve is not modified during analysis.

### D-002 — Protect the source timeline

`REEL_MASTER` is never modified. Apply operates on a duplicate named initially `REEL_AI_v01`.

### D-003 — Hybrid product boundary

A lightweight Resolve panel communicates over localhost with an external local backend that can run while Resolve is closed.

### D-004 — Replaceable Resolve integration

Resolve access is behind `ResolveAdapter`. Resolve MCP may be supported but is never a foundational dependency.

### D-005 — Local-first and provider-neutral

Local execution is preferred. Cloud Director providers and ComfyUI are optional adapters. ComfyUI and its Python environment remain untouched.

### D-006 — Client isolation

Client assets, styles, libraries, references, and projects are isolated. Cross-client asset reuse is denied by default.

### D-007 — MVP format and goal

MVP supports only 9:16 talking-head reels. The key success measure is editorial acceptance rate, not maximum automation breadth.

### D-008 — Observable modular pipeline

Persist intermediate artifacts and structured logs. Steps must be independently inspectable and rerunnable; no opaque monolithic pipeline.

### D-009 — Controlled development workflow

Implementation uses task branches, tests, commits, pushes, and pull requests to `main`. No autonomous merges.

### D-010 — Modular monolith with ports and adapters

Use one local backend process with strict domain modules and typed ports/adapters. Borrow event-sourced discipline only where it adds value: immutable run artifacts, explicit state transitions, schema versions, and hashes. Do not introduce local microservices/workers until measurements justify process isolation.

### D-011 — FastAPI control plane, simple progress transport first

Use FastAPI for the localhost control plane. Prefer ordinary HTTP plus Server-Sent Events for one-way progress/event streaming in the first implementation. Add WebSocket only when a concrete bidirectional real-time requirement appears.

### D-012 — Filesystem-first durable artifacts

Versioned JSON artifacts and structured logs are the MVP source of truth. A metadata index/database is optional and must not become authoritative; add one only when navigation/query performance requires it.

### D-013 — First vertical slice before feature breadth

Prove one complete Analyze → Review → Approve → Duplicate → Apply flow before broadening effects, sources, or providers.

### D-014 — Capability-oriented Model Manager

Manage transcription, alignment, direction, embedding, reranking, and optional visual judging as separate capabilities. Support measured Fast and Low-VRAM profiles. Candidate model names are hypotheses until benchmarked.

### D-015 — Resolve Python API first; MCP later as optional façade/adapter

Validate and implement the first `ResolveAdapter` directly against the official Resolve scripting API. MCP is optional and may be added later for external agents or as another adapter, but the core product must not depend on it.

### D-016 — Global asset library deferred from MVP

MVP searches client-local assets first, then permitted online sources (initially Pexels/Pixabay). A cross-client/global asset library is deferred to avoid early isolation and provenance complexity.

### D-017 — Cloud providers are non-blocking for the first local vertical slice

Freeze provider interfaces in the technical specification, but first prove the local pipeline. After the local vertical slice is functional, add OpenAI and Claude providers as benchmark/quality options before calling MVP complete if they materially improve editorial acceptance. Cloud use remains explicit per client/run.

### D-018 — Windows-first, Resolve Studio capability probe

MVP targets the user's Windows workstation and DaVinci Resolve Studio. The exact installed Resolve version and Workflow Integration capabilities must be detected in the first compatibility spike rather than hard-coded into the domain design. The backend remains independent of panel technology and Resolve version-specific details.

### D-019 — Panel technology is capability-gated

Prefer a native Resolve Workflow Integration panel when supported by the installed Resolve build. Keep a thin external/local fallback possible for development and diagnostics; neither UI path may own domain logic.

### D-020 — Runtime media/data live outside Git-tracked source

Code and non-sensitive docs/config remain in the repository. Client media, references, downloaded assets, model weights, caches, runs, previews, logs, and generated media live under a configurable local data root outside tracked source directories.

### D-021 — Closed v1 schemas and canonical persisted types

The MVP uses closed, versioned JSON contracts for persisted core entities and typed errors. The normative v1 shapes are frozen in `docs/superpowers/specs/2026-09-11-rambla-reel-director-mvp-contracts-v1.md`. Unknown major versions are rejected; migrations are explicit and never silently reinterpret artifacts.

### D-022 — HTTP/SSE contract is deterministic and idempotent

The localhost API uses `/v1`, typed JSON responses/errors, idempotency keys for every mutating command, optimistic version conflicts, and SSE with monotonic per-run event IDs plus replay via `Last-Event-ID`. SSE is notification/progress only; resource state remains authoritative.

### D-023 — MVP ports are typed and capability-based

Transcription, alignment, Director, embedding, reranking, optional visual judging, asset sources, artifact storage, and Resolve all use frozen typed method contracts and `Result<T, TypedError>` boundaries. Vendor exceptions never cross into domain services.

### D-024 — Five editorial actions have fixed v1 semantics

`BROLL`, `EDITORIAL_INSERT`, `PUNCH_IN`, `STICKER`, and `CAPTION_EMPHASIS` have explicit required parameters, layer/collision policy, validation rules, and verification postconditions. Unsupported Resolve capabilities exclude the affected action before plan freeze rather than silently approximating it.

### D-025 — Dry Run has one meaning

Dry Run executes Analyze through plan validation, emits a draft plan plus `dry_run_report.json`, performs zero Resolve mutation, and never freezes/approves the plan. Review, Freeze, and Apply are separate commands.

### D-026 — Retention v1 is local-first and explicit

Approved Style DNA, approved plans, Apply journals/reports, and provenance needed to justify applied edits are never auto-deleted. Non-approved run artifacts default to 30-day retention; temporary/quarantine/unselected-cache data use bounded TTLs; generated Resolve timelines are never auto-deleted. Destructive cleanup requires explicit authorization and audit.

### D-027 — Benchmark v1 separates hard safety gates from editorial taste

MVP sign-off requires zero source-timeline mutation, cross-client leakage, unapproved cloud transmission, and non-idempotent Apply-retry failures. Editorial quality is measured on a frozen consented corpus with acceptance/modify/replace/disable metrics. After baseline measurement, the user approves a versioned benchmark gate; faster providers may not replace a higher-quality default if they fall below that gate.

## Deferred / future decisions

- Exact global-library design and sharing rules.
- Automatic learning from user corrections.
- Music and advanced sound-design automation.
- Horizontal workflows and auto-reframing.
- Generated-video providers.
- Multi-user/cloud collaboration.
- Whether any model/server deserves process isolation after profiling.
