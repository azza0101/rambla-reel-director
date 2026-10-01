# Transcript Intent Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the persistent transcript review, intent selection, constrained Director and timestamped export workflow.

**Architecture:** A focused `transcript_intents.py` service owns phrase state, transcript revisions and export contracts. Existing FastAPI routes expose it, the Director package carries the Coverage allowlist, and the current single-page UI adds a transcript workspace while retaining existing retrieval and curation behavior.

**Tech Stack:** Python 3, FastAPI, vanilla JavaScript/CSS, pytest, Node controller tests.

**Spec:** `docs/superpowers/specs/2026-09-27-transcript-intent-workflow-design.md`

## Global Constraints

- Do not add packages or touch global Python, PATH, CUDA, ComfyUI or system configuration.
- Preserve existing plans/media when transcript changes; mark them stale.
- Coverage, Animation and Highlight may overlap.
- Only Coverage phrases may produce B-roll or provider work.
- Use real source timestamps in all exports.

## Review Focus

- Legacy project without `phrase-intents.json` loads without changing its current plan.
- Concurrent transcript save with a stale revision changes no artifact.
- Empty Coverage selection cannot generate an unconstrained plan.
- Added/removed transcript lines remain ordered and within the source interval.
- Overlapping intent tags appear in every applicable export without corrupting selection state.

---

### Task 1: Persistent intents and transcript correction

**Files:**
- Create: `backend/app/transcript_intents.py`
- Modify: `backend/app/curation_server.py`
- Test: `tests/unit/test_transcript_intents.py`

**Interfaces:**
- Produces: `load_phrase_intents(run)`, `save_phrase_intents(run, changes, expected_signature)`, `transcript_document(run)`, `save_transcript_document(run, text, expected_revision)`.

- [x] Write failing tests for defaults, overlapping tags, stale revisions, retiming and remapping.
- [x] Run the focused tests and confirm missing-interface failures.
- [x] Implement atomic persistence and correction behavior.
- [x] Add GET/PUT transcript and phrase-intent API routes.
- [x] Run focused tests and existing transcript-correction tests.

### Task 2: Coverage-constrained Director

**Files:**
- Modify: `backend/app/editorial_import.py`
- Modify: `backend/app/api_first_director.py`
- Modify: `backend/app/debug_server.py`
- Test: `tests/unit/test_api_first_director.py`
- Test: `tests/unit/test_editorial_import.py`

**Interfaces:**
- Consumes: `load_phrase_intents(run)`.
- Produces: editorial input field `coverage_selected_chunk_ids`; deterministic compiler enforcement.

- [x] Write failing tests proving full context remains present and unselected chunks cannot produce B-roll.
- [x] Run focused tests and confirm the new assertions fail.
- [x] Add the allowlist to the package, prompt and compiler.
- [x] Make Director start reject an explicitly empty Coverage selection.
- [x] Run Director and import test suites.

### Task 3: Timestamped export contracts

**Files:**
- Modify: `backend/app/captions.py`
- Modify: `backend/app/transcript_intents.py`
- Modify: `backend/app/curation_server.py`
- Test: `tests/unit/test_transcript_exports.py`

**Interfaces:**
- Produces: `render_semantic_srt(chunks)`, `build_animation_export(...)`, `build_textplus_export(...)` and download API routes.

- [x] Write failing tests for 2–3 word SRT cues, concatenation flags and joined Text+ items.
- [x] Run the focused tests and confirm missing-interface failures.
- [x] Implement deterministic exports and validation.
- [x] Add SRT, Animation JSON and Text+ JSON endpoints.
- [x] Run export and caption tests.

### Task 4: Transcript workspace UI

**Files:**
- Create: `backend/app/transcript_intent_ui.py`
- Modify: `backend/app/curation_ui_v2.py`
- Modify: `backend/app/curation_theme.py`
- Test: `tests/unit/test_transcript_intent_ui.py`
- Test: `tests/transcript_intent_controller.cjs`

**Interfaces:**
- Consumes: transcript, intents and export API routes.
- Produces: editable transcript panel, mode toolbar, phrase chips, counts and export controls.

- [x] Write failing markup/controller tests for save, all three independent tags and downloads.
- [x] Run Python and Node tests and confirm failures.
- [x] Implement the panel and client controller without replacing existing phrase navigation.
- [x] Add compact desktop/mobile styling and workflow completion states.
- [x] Run UI/controller tests.

### Task 5: Regression and product verification

**Files:**
- Modify only files required by failures attributable to Tasks 1–4.

**Interfaces:**
- Consumes: all previous task interfaces.
- Produces: a verified desktop build with no new runtime dependency.

- [x] Run Python compile checks.
- [x] Run focused transcript, Director, export and UI tests.
- [x] Run the complete available Python and Node suite with cache disabled.
- [x] Inspect the rendered curation page contract and launcher build token.
- [x] Record remaining environment-only limitations without claiming them fixed.
