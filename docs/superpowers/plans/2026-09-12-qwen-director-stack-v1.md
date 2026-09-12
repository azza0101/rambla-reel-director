# Qwen Director Stack V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional, locally gated multi-Qwen Director/retrieval/ranking path without changing Resolve or breaking the heuristic offline plan.

**Architecture:** Explicit local model capabilities gate Qwen provider invocation. Strict JSON Director output and client-scoped embedding/reranking enrich the existing offline plan; absence or invalid output falls back to deterministic rules with provenance. A benchmark reports actual provider use and unavailability rather than synthetic inference.

**Tech Stack:** Python 3.12 standard library plus optional isolated `qwen-asr`, `transformers`, `sentence-transformers`, `torch`/Qwen weights; existing pytest suite.

**Spec:** GitHub Issue #2 comment 5645532712, approved by user message “Vai”.

## Global Constraints

- No Resolve mutation, GUI automation, native scripting fallback, ComfyUI edit, global installation, large model download without user decision, or merge.
- Runtime weights/cache/media/transcript/benchmarks outside Git; local-files-only model resolution.
- Single-agent; retain deterministic heuristic fallback and strict client isolation.

---

### Task 1: Provider contracts and capability gate

**Files:** Create `backend/app/qwen_stack.py`; test `tests/unit/test_qwen_stack.py`.

**Interfaces:** `QwenConfig` resolves only models under a configured runtime root; `capabilities(config)` reports weight/package status; `QwenDirector.propose(beat)` parses closed action/query JSON with one bounded repair; Qwen ASR/alignment, embedding, reranker and optional judge adapters are lazy local-only ports.

- [ ] Write RED tests: absent weights cannot trigger download/inference; invalid Director JSON repairs once then falls back; client mismatches are rejected before embedding; optional judge is off.
- [ ] Run targeted pytest and confirm expected RED.
- [ ] Implement minimum contracts, capability checks and lazy adapter boundaries.
- [ ] Run targeted pytest GREEN.

### Task 2: Offline plan integration and provenance

**Files:** Modify `backend/app/director_engine.py`, `backend/app/director_preview.py`; test `tests/unit/test_qwen_integration.py`.

**Interfaces:** Optional planner/ranker injects query, decision, embedding score, reranker score and model provenance into per-beat plan; heuristic path remains default.

- [ ] Write RED tests for enriched query/action, selected candidate scores and provider provenance, fallback equivalence and escaped HTML.
- [ ] Run targeted pytest and confirm RED.
- [ ] Integrate optional Qwen path and readable per-beat provider/score columns.
- [ ] Run targeted and existing Director tests GREEN.

### Task 3: Benchmark, real capability probe and delivery

**Files:** Create `backend/app/director_benchmark.py`; test `tests/unit/test_director_benchmark.py`; update this plan with verified runtime requirements.

**Interfaces:** `benchmark(...)` compares heuristic and attempted Qwen path on identical source/outline/assets, recording timing, provider status and explicit blocker if unavailable.

- [ ] Write RED test that unavailable Qwen is reported, not represented as a completed inference.
- [ ] Run targeted pytest and confirm RED, implement benchmark, then GREEN.
- [ ] Run on the real 2135-frame source with isolated asset manifest; verify no Resolve call.
- [ ] Run full pytest and compileall; publish only intended code/tests/docs via non-forced GitHub API commit and verify PR #1 draft.
- [ ] Post HANDOFF QWEN_DIRECTOR_STACK_V1 with actual models exercised, benchmark, exact blocker, hardware observation and SHA.
