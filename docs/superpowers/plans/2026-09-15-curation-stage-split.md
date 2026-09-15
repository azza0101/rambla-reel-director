# Curation Stage Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split transcript analysis, video sourcing, and image sourcing into independently resumable project stages with truthful progress and semantic chunks.

**Architecture:** Extend the existing project-scoped runner with a stage discriminator passed to the worker CLI. Analysis owns transcript/chunk artifacts; video and image stages consume those artifacts and write independent outputs. The single curation controller polls authoritative run snapshots and transcript artifacts.

**Tech Stack:** Python 3.12, FastAPI, subprocess worker CLI, vanilla HTML/JavaScript, pytest.

**Spec:** Issue #3 comment 5680827235.

## Global Constraints

- Preserve project isolation and `resolve_calls=0`.
- Do not mutate Resolve or require OpenAI runtime credits.
- Source and guide changes invalidate only dependent artifacts.
- Full pytest remains outside the Codex Windows sandbox.

### Task 1: Stage-aware runner

**Files:** `backend/app/debug_server.py`, `backend/app/debug_run_cli.py`, `tests/test_debug_server.py`, `tests/unit/test_debug_run_cli.py`

**Interfaces:** Produces `RunState.stage_type`, `POST .../analyze`, `POST .../source/videos`, `POST .../source/images`, and `GET .../transcript`.

- [x] Add failing tests for stage command routing, independent endpoints, and terminal 100%.
- [x] Pass `--stage` to the worker and scope its work to analysis, videos, or images.
- [x] Expose snapshots/events and transcript reads without rerunning upstream stages.
- [x] Run focused tests.

### Task 2: Semantic chunks and searchable queries

**Files:** `backend/app/debug_run_cli.py`, `tests/unit/test_debug_run_cli.py`

**Interfaces:** Produces deterministic `build_short_outline()` and `semantic_query_variants()` output.

- [x] Add a realistic Italian contrast/topic-boundary regression test.
- [x] Split complete ideas at punctuation/discourse changes with time as a safety bound.
- [x] Generate concise visual query variants rather than whole-phrase dumps.
- [x] Run focused tests.

### Task 3: Single-controller staged UI

**Files:** `backend/app/curation_ui.py`, `backend/app/debug_server.py`, `tests/unit/test_curation_ui.py`

**Interfaces:** Adds FIND B-ROLL, FIND IMAGES, Analysis Details, live events/transcript, explicit inspect/select, and zero-result reasons.

- [x] Add browser-contract assertions.
- [x] Bind each action to its stage endpoint and final authoritative snapshot.
- [x] Keep ordered mixed selection, NO_BROLL, persistence, and project-scoped media.
- [x] Run focused tests and compileall.

### Task 4: Publication

**Files:** all files above plus this plan.

- [ ] Verify focused tests and `compileall backend`.
- [ ] Publish one coherent remote commit after the expected parent.
- [ ] Verify remote SHA and changed-file set.
