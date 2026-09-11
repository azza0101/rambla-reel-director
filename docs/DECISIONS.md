# Architecture Decision Log

Only explicitly approved decisions belong in the approved section. Proposed choices stay separate until accepted.

## Approved from the project brief

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

## Proposed — awaiting approval

### P-001 — Modular monolith with ports and adapters

Adopt the recommended architecture in `docs/ARCHITECTURE.md`, with a single local backend process, strict domain modules, typed ports, and immutable run artifacts.

### P-002 — FastAPI control plane

Use FastAPI for localhost HTTP plus WebSocket or server-sent progress events, subject to a short panel compatibility spike.

### P-003 — Filesystem-first run store

Use versioned JSON artifacts and structured logs as the MVP source of truth, with a small metadata index only if measurements show it is needed.

### P-004 — First vertical slice

Prove one complete Analyze → Review → Approve → Duplicate → Apply flow before broad provider and effect coverage.

### P-005 — Capability-oriented local Model Manager

Manage separate transcription, alignment, direction, embedding, reranking, and optional judging capabilities with measured Fast and Low VRAM profiles.

