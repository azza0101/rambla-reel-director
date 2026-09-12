# Director Engine V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Build a deterministic, Resolve-independent editorial plan and local review report for the entire real 85-second source.

**Architecture:** A pure Python planner consumes persisted ASR and semantic beat artifacts, uses client-scoped asset metadata for retrieval, and emits a validated offline Edit Plan. A separate CLI persists source/runtime artifacts and renders an escaped HTML report. Resolve Apply remains an untouched replaceable port.

**Tech Stack:** Python 3.12, pytest, standard-library JSON/HTML/path handling, existing local ASR artifact.

**Spec:** GitHub Issue #2 comment 5645244488 (approved Director Engine V1 scope).

## Global Constraints

- No Resolve mutation, bridge mutation experiment, GUI automation, native fallback, or ComfyUI change.
- Runtime transcript, media, manifest, plans, and reports stay outside Git.
- Single-agent; no global/system install; PR #1 remains draft; no merge.
- Strict client isolation; deterministic frame timing and decisions; no hard-coded Resolve project/timeline.

---

### Task 1: Pure offline Director contracts and planning

**Files:** Create `backend/app/director_engine.py`; test `tests/unit/test_director_engine.py`.

**Interfaces:** `build_edit_plan(transcript, beat_outline, assets, *, client_id, source_frames)` returns a validated JSON-ready dictionary; `validate_edit_plan(plan)` rejects timing, coverage, action, and asset-scope violations.

- [ ] Write failing tests for complete frame coverage, deterministic actions, client isolation, semantic retrieval, and full captions.
- [ ] Run `pytest tests/unit/test_director_engine.py -q` and confirm missing implementation fails.
- [ ] Implement minimum deterministic adapters, caption chunking, ranking and validation.
- [ ] Run targeted tests to GREEN.

### Task 2: Runtime artifacts and local HTML review

**Files:** Create `backend/app/director_preview.py`, `backend/app/director_cli.py`; test `tests/unit/test_director_preview.py`.

**Interfaces:** `render_report(plan)` returns escaped HTML; CLI reads runtime artifact paths and writes normalized transcript, beat artifact, plan and HTML outside Git.

- [ ] Write failing test for HTML containing all beats/captions with escaped untrusted text.
- [ ] Run targeted test and confirm RED.
- [ ] Implement report and runtime CLI.
- [ ] Run targeted tests, full pytest, and compileall.
- [ ] Run CLI on real transcript/outline and client-scoped local workflow asset; inspect persisted plan/report for entire 2135 frames.
- [ ] Publish one logical commit via GitHub API transport after verifying remote parent and intended file set; verify PR #1 remains draft and post HANDOFF.
