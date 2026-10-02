# Resolve Confirmed Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a confirmable RAMBLA-to-Resolve handoff containing subtitles, highlighted Fusion Titles, selected timed B-roll, and optional generic thematic tail clips.

**Architecture:** RAMBLA writes immutable versioned packages to a local outbox and exposes status/apply endpoints. The Resolve bridge previews a compatible pending package and starts an asynchronous apply job only after user confirmation. Timeline construction remains in the existing Resolve helper, extended with destination modes, role tracks, colors, backups, and progress callbacks.

**Tech Stack:** Python 3.12, FastAPI, vanilla JavaScript/CSS, DaVinci Resolve Python/Fusion scripting API, pytest.

**Spec:** `docs/superpowers/specs/2026-09-30-resolve-confirmed-export-design.md`

## Global Constraints

- Default application mode creates a new empty, versioned timeline in `TEMP`.
- Active-timeline mode must create a safety duplicate in `TEMP` before inserting anything.
- Never overwrite an existing clip; allocate role tracks above occupied video tracks.
- Coverage clips are purple, highlighted Fusion Titles yellow, and generic tail clips beige.
- Preparing, inspecting, or discarding a package must not change Resolve.
- Preserve existing XML, DRT, DRA, audio bridge, Detect Videos, and direct endpoint compatibility.
- Keep every package version; never overwrite a previous handoff.
- Do not commit or push the existing user workspace during this implementation.

## Review Focus

- Resolve project or timeline changes after package creation: apply must reject with a clear mismatch and leave the package retryable (Task 3 test).
- A clip is selected but its downloaded file disappeared: summary must count it unavailable and apply must skip it explicitly (Tasks 1 and 5 tests).
- Apply is clicked twice or retried after success: the package must not insert duplicate items (Task 3 test).
- Active timeline has locked or densely occupied tracks: backup must complete and new role tracks must be created above them without overwrite (Task 4 test).
- Pexels returns fewer than 12 unique videos: show every unique result, disclose the shortfall, and never duplicate cards (Task 6 test).

---

### Task 1: Immutable Resolve package model

**Files:**
- Create: `backend/app/resolve_handoff.py`
- Test: `tests/unit/test_resolve_handoff.py`

**Interfaces:**
- Consumes: normalized rows returned by `editing_resolve_payload(project_id)`.
- Produces: `ResolveHandoffStore`, `prepare_package(...)`, `read_package(...)`, `list_pending(...)`, `transition_package(...)`.

- [ ] **Step 1: Write failing tests for package creation, versioning, summaries, unavailable media, and legal state transitions**

Assert sequential package IDs do not overwrite; counts include subtitles, titles, timed B-roll, generic B-roll and unavailable rows; state transitions allow `pending -> applying -> completed|failed` and `pending|failed -> discarded` while rejecting `completed -> applying`.

- [ ] **Step 2: Run the focused test and confirm the new module is missing**

Run: `python -m pytest tests/unit/test_resolve_handoff.py -q -p no:cacheprovider`

- [ ] **Step 3: Implement the package store**

Use signatures:

```python
class ResolveHandoffStore:
    def prepare(self, project_root: Path, payload: dict[str, Any]) -> dict[str, Any]: ...
    def read(self, project_root: Path, package_id: str) -> dict[str, Any]: ...
    def pending(self, *, resolve_project: str, timeline_id: str) -> list[dict[str, Any]]: ...
    def transition(self, project_root: Path, package_id: str, status: str, **updates: Any) -> dict[str, Any]: ...
```

Persist under `<project>/resolve-outbox/<package_id>/package.json` with atomic writes and schema `rambla-resolve-handoff-1`.

- [ ] **Step 4: Run Task 1 tests and confirm all pass**

### Task 2: Package preparation and local API

**Files:**
- Modify: `backend/app/curation_server.py`
- Modify: `backend/app/curation_artifacts.py`
- Test: `tests/unit/test_resolve_handoff_api.py`

**Interfaces:**
- Consumes: Task 1 store and existing `editing_resolve_payload(project_id)`.
- Produces endpoints `POST /projects/{id}/resolve-handoffs`, `GET /resolve-handoffs/pending`, `GET /resolve-handoffs/{package_id}`, and `POST /resolve-handoffs/{package_id}/discard`.

- [ ] **Step 1: Write failing API tests**

Assert preparing returns `pending` with summary; pending lookup filters by active Resolve project/timeline ID; discard changes no Resolve state; source mismatch is reported.

- [ ] **Step 2: Run API tests and confirm 404/failure before routes exist**

- [ ] **Step 3: Add request/response models and routes**

Preparation must validate current transcript signature, selected title template, linked timeline metadata and media availability without invoking `run_resolve_helper`.

- [ ] **Step 4: Run Task 2 tests and existing combined-timeline API tests**

### Task 3: Asynchronous apply jobs and truthful progress

**Files:**
- Create: `backend/app/resolve_handoff_jobs.py`
- Modify: `backend/app/curation_server.py`
- Test: `tests/unit/test_resolve_handoff_jobs.py`

**Interfaces:**
- Consumes: Task 1 package and `run_resolve_helper(payload, progress_callback=...)` from Task 4.
- Produces `POST /resolve-handoffs/{package_id}/apply` and `GET /resolve-handoffs/{package_id}/status`.

- [ ] **Step 1: Write failing job tests**

Pin monotonic phases and percentages: validate 5, destination 18, import 35, coverage 52, titles 66, subtitles 78, generic tail 88, verify/save 100. Test wrong timeline, retry after failure, simultaneous apply rejection, and completed-package idempotency.

- [ ] **Step 2: Run focused tests and confirm failure**

- [ ] **Step 3: Implement a thread-safe in-process job registry**

Use one active job globally because Resolve scripting is single-writer. Persist every progress update into the package so browser and bridge see identical state.

- [ ] **Step 4: Run Task 3 tests and API tests**

### Task 4: Resolve destination modes, safety backup, tracks, and colors

**Files:**
- Modify: `backend/app/resolve_textplus_timeline.py`
- Test: `tests/unit/test_resolve_textplus_timeline.py`

**Interfaces:**
- Consumes payload fields `destination_mode: "new"|"active"`, `generic_broll_clips`, and Task 3 progress callback.
- Produces `run_resolve_helper(payload, *, timeout=45.0, progress_callback=None)` result containing destination timeline ID/name, backup timeline ID/name, role tracks and inserted counts.

- [ ] **Step 1: Write failing pure-planning tests**

Cover role-track allocation above the highest occupied track; `new` timeline starts empty; `active` requires a successful safety duplicate before insertion; repeated package ID is rejected; track colors map coverage to purple, titles to yellow, generic tail to beige.

- [ ] **Step 2: Run tests and confirm failures**

- [ ] **Step 3: Split destination preparation from item insertion**

Add `prepare_destination(project, source, mode, package_id, temp_folder) -> DestinationPlan` and keep all source mutations behind the successful-backup gate.

- [ ] **Step 4: Extend insertion functions**

Place timed coverage at phrase timing, titles above coverage, native subtitles on subtitle track, and generic clips after program end plus the configured tail gap. Use Resolve clip-color setters and create missing tracks.

- [ ] **Step 5: Emit progress after verified phases and save**

- [ ] **Step 6: Run Resolve helper tests, then manually verify both modes with a disposable package**

Confirm the default source signature is unchanged and active mode produces a safety duplicate before insertion.

### Task 5: Unified RAMBLA Editing control and delivery status

**Files:**
- Modify: `backend/app/transcript_intent_ui.py`
- Modify: `backend/app/timeline_export_ui.py`
- Modify: `backend/app/curation_theme.py`
- Test: `tests/unit/test_transcript_intent_ui.py`

**Interfaces:**
- Consumes Task 2 prepare/status APIs.
- Produces one primary button `INVIA A RESOLVE · SUBS + FRASI + B-ROLL` and a persistent handoff status card.

- [ ] **Step 1: Write failing rendered-page and controller tests**

Assert the primary label, summary counts, `File inviato a Resolve · controlla il bridge`, polling states, progress rendering, failure debug and secondary legacy export controls.

- [ ] **Step 2: Run UI tests and confirm failure**

- [ ] **Step 3: Implement the unified control**

Preparing a package must return immediately to `pending`; poll while pending/applying; show completion timeline name or actionable error. Remove direct Resolve mutation from the primary click.

- [ ] **Step 4: Run Task 5 and regression UI tests**

### Task 6: Twelve generic thematic Pexels candidates

**Files:**
- Create: `backend/app/generic_coverage.py`
- Modify: `backend/app/curation_server.py`
- Modify: `backend/app/curation_ui_v2.py`
- Modify: `backend/app/timeline_export_ui.py`
- Test: `tests/unit/test_generic_coverage.py`
- Test: `tests/unit/test_generic_coverage_ui.py`

**Interfaces:**
- Consumes editorial `global_topic`, transcript text, and existing Pexels provider primitives.
- Produces `derive_topic_queries(...)`, `search_generic_coverage(..., limit=12)`, selection persistence, and `generic_broll_clips` for Task 1.

- [ ] **Step 1: Write failing query and deduplication tests**

Assert Egypt and sustainability examples create concrete topic-first queries, progressive broadening, stable unique ordering, maximum 12, and explicit shortfall when fewer unique candidates exist.

- [ ] **Step 2: Run focused tests and confirm failure**

- [ ] **Step 3: Implement bounded Pexels topic search**

Reuse official Pexels discovery and preview fields. Do not run Qwen/GPU ranking; score by provider relevance and topic keyword overlap.

- [ ] **Step 4: Add the final-page gallery and selection persistence**

Render `COPERTURE GENERICHE · TEMA DEL VIDEO` after visual beats with 12 landscape cards, existing source/preview controls, beige selected state and a truthful result count.

- [ ] **Step 5: Feed selected generic rows into the handoff package**

Store tail order, source metadata, local media path or unavailable reason, default duration and tail gap.

- [ ] **Step 6: Run Task 6 tests and sourcing regressions**

### Task 7: Resolve bridge package inbox and confirmation UI

**Files:**
- Modify: `tools/resolve_bridge/RAMBLA_B_ROLL.py`
- Modify: `tests/unit/test_resolve_bridge.py`
- Test: `tests/unit/test_resolve_bridge_handoff.py`

**Interfaces:**
- Consumes Task 2 pending API and Task 3 apply/status APIs.
- Produces package card, destination controls, Apply/Discard/Retry actions and real progress polling.

- [ ] **Step 1: Write failing bridge source/controller tests**

Assert summary fields, default `new`, explicit `active`, Apply/Discard, progress phases, event processing during polling, retry after failure, and no automatic apply.

- [ ] **Step 2: Run bridge tests and confirm failure**

- [ ] **Step 3: Extend the bridge UI**

Keep audio controls intact. Poll only while visible, show the newest compatible package and send the chosen mode on Apply. Disable only conflicting controls during apply.

- [ ] **Step 4: Install the bridge through Resolve and verify source/installed hashes match**

- [ ] **Step 5: Run bridge tests and manually exercise Prepare -> Preview -> Apply**

Confirm both RAMBLA and bridge show the same counts/status and the source timeline remains unchanged in default mode.

### Task 8: Integrated regression and recovery verification

**Files:**
- Modify only failing tests or implementation files owned by Tasks 1-7.

**Interfaces:**
- Consumes all preceding tasks.
- Produces a verified release candidate in the current workspace.

- [ ] **Step 1: Run focused suites for handoff, Resolve, transcript UI, timeline export, Pexels, and bridge**

- [ ] **Step 2: Run the broader unit suite with a writable workspace basetemp**

Document any pre-existing Windows locked-temp errors separately; do not label them product failures.

- [ ] **Step 3: Perform one real default-mode apply in Resolve**

Verify package summary, progress, TEMP placement, purple/yellow/beige roles, subtitle count, timing, versioned media folder, and unchanged source timeline signature.

- [ ] **Step 4: Perform one real active-mode apply on a disposable test timeline**

Verify safety duplicate exists before insertions and existing clips are untouched.

- [ ] **Step 5: Restart the local launcher and open the final project URL**

Confirm the normal desktop link loads the same updated build and last project.
