# RAMBLA Media Research Controls & Project Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add project-level media cleanup, per-beat replace/append research, and a local project library with rename/delete/storage accounting, without rerunning Analyze/ASR.

**Architecture:** Keep durable analysis/editorial state separate from disposable retrieval state. Add a focused maintenance service for safe filesystem operations and project-library metadata; extend staged sourcing with beat targeting + append/replace merge semantics; wire small FastAPI endpoints and UI controls on top. Preserve existing project IDs, imported plans, selections that remain valid, and `resolve_calls=0`.

**Tech Stack:** Python 3.12, FastAPI, existing RAMBLA JSON artifacts, pathlib/shutil, vanilla JS UI, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-16-media-research-project-library-design.md`

## Global Constraints

- Never run Analyze/ASR for clean-media, beat replace, beat append, rename, open, or delete.
- Never delete source video, guide audio, transcript, semantic chunks, analysis signature, imported visual plan, or imported plan snapshot during media cleanup.
- All destructive paths must resolve under configured `ProjectStore.root`.
- `NO_BROLL` and `CONTINUE_PREVIOUS_VISUAL` survive media cleanup; stale asset selections do not.
- Project delete removes only the validated project directory.
- Append merge is atomic and preserves existing candidates/selections when new provider calls fail.
- `resolve_calls = 0` for every new endpoint.

---

### Task 1: Safe project library service

**Files:**
- Create: `backend/app/project_maintenance.py`
- Modify: `backend/app/curation_project.py`
- Test: `tests/unit/test_project_library.py`

**Interfaces:**
- Produces `project_library_rows(store: ProjectStore) -> list[dict]`
- Produces `rename_project(store: ProjectStore, project_id: str, name: str) -> CurationProject`
- Produces `delete_project_tree(store: ProjectStore, project_id: str) -> dict`

- [ ] Write tests that create two temporary projects, add nested files, assert size/file counts and newest-first ordering.
- [ ] Verify tests fail because library service does not exist.
- [ ] Implement symlink-safe recursive accounting and source/status metadata.
- [ ] Add atomic rename through `ProjectStore` preserving project ID and analysis signature while regenerating `project.rambla.json`.
- [ ] Add validated recursive delete limited to `ProjectStore.root`.
- [ ] Run focused tests and commit.

### Task 2: Project-wide CLEAN MEDIA

**Files:**
- Modify: `backend/app/project_maintenance.py`
- Modify: `backend/app/curation_selection.py` only if needed for selection cleanup helper
- Test: `tests/unit/test_media_cleanup.py`

**Interfaces:**
- Produces `clean_project_media(run_root: Path, retrieval_root: Path) -> dict`

- [ ] Build fixture with transcript, semantic chunks, analysis signature, visual plan, editorial/imported-plan, retrieval JSON, asset-cache/image-cache/quality-clips, and selection state.
- [ ] Verify RED: cleanup function missing.
- [ ] Implement deletion allowlist for retrieval artifacts/caches only.
- [ ] Remove selected asset references whose candidate IDs disappeared while preserving NO_BROLL/CONTINUE records.
- [ ] Return deleted file count/bytes/cleared selections/preserved decisions/partial failures/`resolve_calls=0`.
- [ ] Verify durable artifacts remain byte-identical.

### Task 3: Beat-scoped replace/append artifact merge

**Files:**
- Create: `backend/app/beat_research.py`
- Modify: `backend/app/online_sourcing_cli.py`
- Modify: `backend/app/image_sourcing_cli.py`
- Test: `tests/unit/test_beat_research.py`

**Interfaces:**
- Produces `merge_video_rows(existing, fresh, beat_id, mode) -> list[dict]`
- Produces `merge_image_artifact(existing, fresh, beat_id, mode) -> dict`
- Produces `seen_candidate_keys(...) -> set[str]`

- [ ] RED tests: replace modifies only targeted beat; append preserves old rows and adds only unique provider/provider_id or source/content identities.
- [ ] Implement merge helpers independent of subprocess execution.
- [ ] Ensure append never lowers quality thresholds and caps persisted candidates at spec limits.
- [ ] Add persisted per-beat research round metadata.
- [ ] Keep writes atomic.

### Task 4: Worker support for targeted research

**Files:**
- Modify: `backend/app/debug_run_cli.py`
- Modify: `backend/app/online_sourcing_cli.py`
- Modify: `backend/app/image_sourcing_cli.py`
- Test: `tests/unit/test_beat_research_worker.py`

**Interfaces:**
- Add CLI args `--beat-id <id>` and `--research-mode replace|append` to video/image staged sourcing path.

- [ ] RED test command builders emit beat/research arguments and do not include analyze stage.
- [ ] Filter visual plan/chunks to target beat for provider execution.
- [ ] Snapshot existing artifact before scoped run; merge fresh scoped output after successful provider process.
- [ ] For append, derive seen IDs and ensure next pass excludes/merges duplicates.
- [ ] If worker fails, restore/preserve previous artifact.
- [ ] Emit structured events with beat ID, mode, round, added counts.

### Task 5: FastAPI project maintenance endpoints

**Files:**
- Modify: `backend/app/debug_server.py`
- Test: `tests/unit/test_project_maintenance_api.py`

**Interfaces:**
- `GET /api/curation/projects`
- `PATCH /api/curation/projects/{project_id}` body `{name}`
- `DELETE /api/curation/projects/{project_id}`
- `POST /api/curation/projects/{project_id}/media/clean`
- `POST /api/curation/projects/{project_id}/beats/{beat_id}/research` body `{mode}`

- [ ] RED endpoint tests, including malformed IDs, running-stage delete refusal, current data preservation, and `resolve_calls=0`.
- [ ] Implement Pydantic request models and routes.
- [ ] Beat research launches a dedicated stage without Analyze/ASR.
- [ ] Clean-media route rehydrates curation payload with empty retrieval shelves but intact plan.

### Task 6: UI project library + media controls

**Files:**
- Modify: `backend/app/curation_ui.py`
- Test: `tests/unit/test_curation_product_v2.py`
- Test: `tests/unit/test_curation_ui.py`

**Interfaces:**
- Project panel buttons: `PROJECTS`, `CLEAN MEDIA`.
- BROLL beat controls: `NEW SEARCH`, `ADD RESULTS`.

- [ ] RED HTML/JS contract tests for all controls and endpoint calls.
- [ ] Add Project Library dialog: rows show name, ID, source filename, modified time, disk usage, transcript/plan state; OPEN/RENAME/DELETE actions.
- [ ] Add CLEAN MEDIA confirmation and immediate hydrate.
- [ ] Add beat buttons visible only on BROLL beats; wire replace/append stages and preserve append results while running.
- [ ] Add compact show-more behavior beyond initial shelf counts.
- [ ] Ensure delete-current clears state/localStorage.
- [ ] Run node syntax check via CI.

### Task 7: Final integration verification

**Files:**
- Modify: `.github/workflows/online-sourcing-tests.yml` to include new focused files.

- [ ] Run full focused branch suite.
- [ ] Confirm embedded JS syntax check passes.
- [ ] Confirm backend compile passes.
- [ ] Confirm legacy `project.json` migration tests remain green.
- [ ] Confirm vertical-social regression tests remain green.
- [ ] Verify branch SHA and report exact launcher/build marker for user acceptance.
