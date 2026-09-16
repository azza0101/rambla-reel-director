# RAMBLA Media Research Controls & Project Library Design

## Goal

Add two product-grade capabilities to RAMBLA Curation without forcing re-analysis: (1) controllable media retrieval at project and per-beat scope, and (2) a local project library with rename/delete/storage management.

## Product Principles

- Analysis artifacts are durable. Media cleanup must never delete the source video, guide audio, transcript, semantic chunks, imported visual plan, or analysis signature.
- Retrieval artifacts are disposable and regenerable.
- User decisions survive whenever they still make sense. `NO BROLL` and `CONTINUE_PREVIOUS_VISUAL` survive media cleanup; selections that point to deleted media are removed.
- Destructive actions are explicit and confirmable.
- Per-beat operations never trigger ASR or whole-project analysis.
- Resolve remains untouched: `resolve_calls = 0`.

## 1. Media Lifecycle Model

RAMBLA will treat retrieved media as a separate lifecycle layer under the active editorial retrieval root. The system must distinguish:

1. Analysis state: transcript, semantic chunks, analysis signature.
2. Editorial state: imported `visual-plan.json` and its editorial digest/root.
3. Retrieval state: video candidates, image candidates, diagnostics, downloaded previews, bounded clips, provider attempt records, retrieval cache materialized for the project.
4. Curation state: user selections, `NO BROLL`, `CONTINUE_PREVIOUS_VISUAL`.

Only layer 3 is cleared by `CLEAN MEDIA`.

## 2. Project-Level CLEAN MEDIA

Add a project action labelled `CLEAN MEDIA` near `FIND B-ROLL` / `FIND IMAGES`.

Behavior:

- Requires confirmation explaining that downloaded/search media will be deleted but analysis and editorial plan remain.
- Deletes project retrieval artifacts for the active editorial plan, including:
  - `online-candidates.json`
  - `video-sourcing-diagnostics.json`
  - `image-candidates.json`
  - retrieval benchmark/metrics derived only from sourcing
  - generated preview/poster/bounded-clip folders owned by the active retrieval root
  - per-retrieval provider attempt state
- Does not delete:
  - `project.json`
  - `project.rambla.json`
  - source media
  - guide audio
  - `analysis-signature.json`
  - `transcript-raw.json`
  - `transcript-normalized.json`
  - `semantic-chunks.json`
  - imported `visual-plan.json`
  - editorial imported plan snapshot
- Selection cleanup:
  - remove selected asset references whose assets were deleted;
  - retain `NO_BROLL` decisions;
  - retain `CONTINUE_PREVIOUS_VISUAL` decisions and their continuity relation.
- Return a structured response containing deleted file count, deleted bytes, cleared selection count, preserved decision count, and `resolve_calls: 0`.
- UI immediately rehydrates to empty media shelves while preserving visual beats.

## 3. Per-Beat Media Operations

Each BROLL visual beat gets two controls:

### NEW SEARCH

Purpose: replace current retrieval for that beat.

Behavior:

- Delete only that beat's video and image candidates, diagnostics, provider attempts, materialized clips/previews that are not shared by another beat, and selected assets for that beat.
- Preserve the beat's imported editorial intent/queries.
- Run fresh video and image sourcing for only that beat.
- Existing project-wide media for all other beats remain untouched.
- The result set replaces the previous set for that beat.

### ADD RESULTS

Purpose: broaden candidate choice while preserving current results and selections.

Behavior:

- Keep current candidates and current selection.
- Start another retrieval pass for only that beat.
- Exclude already-seen identities using provider + provider_id/source URL/content hash.
- Use bounded query diversification on later rounds. The original query remains first; additional rounds may use contextual variants already supported by the retrieval engine.
- Merge only new unique candidates into the existing set.
- Preserve source/provider/query/score/clip timings.
- Increment a persisted per-beat retrieval round counter.
- Do not silently downgrade quality thresholds just to fill cards.

### Candidate history and limits

- Default initial display remains concise.
- Persist up to 12 unique video candidates and 16 unique image candidates per beat across `ADD RESULTS` rounds.
- UI shows all accumulated candidates with a compact `Show more` behavior when more than the initial shelf count exists.
- Vertical social, general YouTube, stock, and images remain separate shelves.

## 4. Sourcing Execution Contract

Extend sourcing so workers can target a subset of beat IDs. The currently imported visual plan remains authoritative.

Required backend contract:

- whole project sourcing: existing behavior;
- beat-scoped replace sourcing: target beat IDs + replace mode;
- beat-scoped append sourcing: target beat IDs + append mode + already-seen candidate identities.

A per-beat operation must never invoke the Analyze/ASR stage.

The worker writes new artifacts atomically. In append mode, merge happens only after successful sourcing, so a provider failure does not destroy prior usable results.

## 5. Project Library

Add `PROJECTS` / `MANAGE PROJECTS` in the Project panel. It opens a modal containing locally saved projects.

Each row displays:

- project name;
- project ID in small text;
- source filename;
- last modified date/time;
- total project disk usage, human-readable;
- whether transcript exists;
- whether an editorial plan exists;
- number of retrieved media assets if cheaply available.

Sort by most recently modified first.

Actions per row:

### OPEN

- Load the existing project exactly like `OPEN PROJECT FILE`.
- No Analyze invocation.
- Close modal and hydrate UI.

### RENAME

- Inline edit or small rename dialog.
- Validate trimmed non-empty name, max 120 characters.
- Update authoritative `project.json` and regenerated `project.rambla.json` atomically.
- Project ID and filesystem directory remain unchanged.
- Rename must not invalidate analysis/retrieval artifacts.

### DELETE

- Requires explicit confirmation containing project name and approximate disk usage.
- Refuse deletion while a project stage for that project is running.
- Delete the entire project directory recursively, including source copy, guide, run artifacts, caches, downloaded media, selections, manifests.
- If deleting the currently open project, require a stronger confirmation and then clear UI/localStorage and return to no-project state.
- Deletion may only operate on directories validated as children of the configured `RAMBLA_PROJECT_ROOT`; no arbitrary path deletion.
- Return deleted bytes/files and `resolve_calls: 0`.

## 6. Project Storage Accounting

Implement a focused project-library service rather than mixing recursive filesystem logic into the UI/server route file.

Responsibilities:

- enumerate valid project directories;
- calculate recursive size with symlink-safe traversal;
- count files;
- derive last modified timestamp;
- derive source filename and state flags;
- rename through `ProjectStore`;
- delete through validated project IDs only.

Size calculation may be done on demand when opening the Project Library. The expected project count is low, so no database/index is required yet.

## 7. UI Design

### Project panel

Buttons:

`NEW PROJECT` · `OPEN PROJECT FILE` · `SAVE PROJECT FILE` · `PROJECTS`

When a project is open, additionally show:

`CLEAN MEDIA`

### Visual beat stage

For BROLL beats, directly below the beat heading/diagnostics:

`NEW SEARCH` · `ADD RESULTS`

During either operation:

- disable the two beat controls for that beat;
- show progress/status in the existing run monitor;
- keep old results visible during append mode;
- in replace mode, mark old results as being replaced and remove them only when the replacement operation starts successfully.

Non-BROLL beats do not show these controls.

### Project Library modal

Desktop-first compact table/cards. Destructive delete uses a visually distinct button and browser/modal confirmation. Rename and delete refresh the library immediately.

## 8. Persistence & Compatibility

- Existing `project.json` projects and current `project.rambla.json` manifests remain openable.
- Project rename rewrites the modern manifest so a subsequently saved/downloaded manifest has the new name.
- Old retrieval artifact schema versions are still considered stale by existing version checks.
- `CLEAN MEDIA` must clean both current active retrieval root and safe stale retrieval descendants owned by that project's editorial area, but must not remove imported plan snapshots.
- No global/shared model weights or non-project caches are deleted by project cleanup.

## 9. Safety & Error Handling

- Every destructive filesystem operation resolves paths and verifies they are inside `ProjectStore.root`.
- Reject malformed project IDs.
- Reject deletion of a project with a running stage.
- If media cleanup encounters an individual locked file, report partial failure with exact path/category while leaving analysis state intact.
- Append retrieval merges atomically; partial provider errors are retained in diagnostics but do not erase old candidates.
- Rename failure leaves the previous project metadata intact.

## 10. API Shape

Add project endpoints conceptually equivalent to:

- `GET /api/curation/projects` — project library rows.
- `PATCH /api/curation/projects/{project_id}` with `{ "name": "..." }` — rename.
- `DELETE /api/curation/projects/{project_id}` — recursive delete.
- `POST /api/curation/projects/{project_id}/media/clean` — project retrieval cleanup.
- `POST /api/curation/projects/{project_id}/beats/{beat_id}/research` with `{ "mode": "replace" | "append" }` — beat-scoped video+image research.

Exact internal route wiring may follow current FastAPI conventions, but behavior and response semantics above are required.

## 11. Testing Strategy

Use TDD and add regression tests for:

- CLEAN MEDIA preserves transcript, analysis signature, semantic chunks, visual plan and source/guide files.
- CLEAN MEDIA removes retrieval artifacts and invalid selected asset references while preserving NO_BROLL/CONTINUE decisions.
- NEW SEARCH changes only the targeted beat's media artifacts.
- ADD RESULTS keeps old candidates, adds unique new candidates, and keeps existing selection.
- append dedupe works by provider identity/source/content hash.
- per-beat research never invokes Analyze/ASR.
- project list reports name/source/mtime/size/state.
- rename updates project + manifest without changing project ID or analysis signature.
- delete removes only the validated project directory and refuses traversal/malformed IDs.
- delete refuses while a stage is running.
- deleting current project clears UI state.
- UI exposes Project Library, CLEAN MEDIA, NEW SEARCH and ADD RESULTS.
- existing project-open migration remains green.
- JavaScript syntax and backend compile remain green.
- `resolve_calls = 0` for every new endpoint.

## 12. Acceptance Criteria

The feature is ready for user testing only when:

1. A previously analyzed reel can have all found B-roll/images cleared and sourced again without Analyze.
2. One visual beat can be researched independently in replace mode.
3. One visual beat can accumulate additional unique results without losing prior candidates or selection.
4. Project Library can open, rename and delete projects and shows actual disk usage.
5. Deleting a project actually frees its project directory on disk.
6. Transcript/visual plan survive media cleanup.
7. Existing legacy/current project files still open without Analyze.
8. Focused tests, embedded JS syntax check and backend compile pass on the final branch SHA.
9. Resolve is never called.
