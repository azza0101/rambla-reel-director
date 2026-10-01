# Resolve Title Template Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `KURA_paper_title_v8` as RAMBLA's default Resolve title while allowing validated `.drfx` uploads, per-project selection, user-level installation, and exact-time title generation with any compatible template.

**Architecture:** A focused template-library module validates and stores packages and performs collision-safe installation. Project selection is persisted beside existing project state, HTTP endpoints expose the library, and the transcript UI provides upload/select/install controls. The isolated Resolve helper receives the selected insertion name and discovers a safe writable Text+ control at runtime.

**Tech Stack:** Python 3.12, FastAPI, standard-library `zipfile`/`hashlib`/`pathlib`, existing vanilla HTML/CSS/JavaScript UI, DaVinci Resolve scripting API, pytest.

**Spec:** `docs/superpowers/specs/2026-09-29-resolve-title-template-library-design.md`

## Global Constraints

- Bundle `KURA_paper_title_v8.drfx` and select `KURA_paper_title_v8` by default.
- Accept only validated `.drfx` ZIP packages containing exactly one usable `Edit/Titles/**/*.setting` entry.
- Never silently substitute a different title.
- Install only into the current Windows user's Resolve template directory; do not alter global Python, PATH, CUDA, or Resolve configuration.
- Preserve JSON export when Resolve or a title template is unavailable.
- Preserve the source timeline and roll back every incomplete generated timeline.
- Do not commit or publish during implementation because this worktree contains approved mixed uncommitted product work; use exact diff and verification output as the audit trail.

## Review Focus

- A ZIP traversal filename must be rejected before any copy or extraction.
- Two packages with the same filename but different bytes must coexist without overwriting user data.
- A package copied while Resolve is open must report restart required instead of ready.
- A custom title with multiple Text+ nodes must edit only an unambiguous exposed `Template` control or fail and roll back.
- A project whose selected library file disappears must remain explicitly invalid and must not fall back to KURA.

---

### Task 1: Validated template library and bundled default

**Files:**
- Create: `backend/app/resolve_title_templates.py`
- Create: `backend/assets/resolve_titles/KURA_paper_title_v8.drfx`
- Test: `tests/unit/test_resolve_title_templates.py`

**Interfaces:**
- Produces: `inspect_drfx(path: Path) -> ResolveTitleTemplate`, `template_library(root: Path, bundled_root: Path) -> list[ResolveTitleTemplate]`, `store_uploaded_drfx(source: BinaryIO, filename: str, root: Path) -> ResolveTitleTemplate`, `install_template(template: ResolveTitleTemplate, resolve_root: Path) -> InstallResult`.

- [ ] **Step 1: Write failing validation tests** for the supplied KURA package, corrupt ZIP, traversal paths, multiple title settings, missing title setting, stable SHA-256 ID, upload size limit, missing stored file, and filename collision.
- [ ] **Step 2: Run** `pytest tests/unit/test_resolve_title_templates.py -q` and verify the new imports fail.
- [ ] **Step 3: Implement the module** with immutable metadata records, streaming SHA-256, central-directory validation, atomic storage, and hash-aware installation.
- [ ] **Step 4: Copy the supplied package** to `backend/assets/resolve_titles/KURA_paper_title_v8.drfx` and verify inspection returns insertion name `KURA_paper_title_v8`.
- [ ] **Step 5: Run** `pytest tests/unit/test_resolve_title_templates.py -q` and verify all tests pass.

### Task 2: Project selection and HTTP API

**Files:**
- Modify: `backend/app/curation_server.py`
- Modify: `backend/app/project_config.py`
- Test: `tests/unit/test_resolve_title_template_api.py`
- Test: `tests/integration/test_health_api.py`

**Interfaces:**
- Consumes: Task 1 library functions and metadata records.
- Produces: list/upload/install endpoints plus `GET/PUT /api/curation/projects/{project_id}/resolve-title-template`; `selected_resolve_title_template(project_root: Path) -> str`.

- [ ] **Step 1: Write failing API tests** for default selection, valid bounded binary upload, invalid upload, per-project persistence, nonexistent template selection, installation status, collision preservation, and deleted selected package without fallback.
- [ ] **Step 2: Run** `pytest tests/unit/test_resolve_title_template_api.py tests/integration/test_health_api.py -q` and verify failures describe missing routes.
- [ ] **Step 3: Add persistence** using a small project-local JSON field/file compatible with projects that predate this feature.
- [ ] **Step 4: Add endpoints** with bounded upload reads, sanitized responses, explicit error codes, and no arbitrary filesystem paths.
- [ ] **Step 5: Run the focused API tests** and verify they pass.

### Task 3: Template-aware Resolve generation

**Files:**
- Modify: `backend/app/resolve_textplus_timeline.py`
- Modify: `backend/app/curation_server.py`
- Test: `tests/unit/test_resolve_textplus_timeline.py`

**Interfaces:**
- Consumes: selected validated `ResolveTitleTemplate.resolve_name` from Task 2.
- Produces: `choose_text_control(item: Any) -> Any`; `materialize_in_resolve(payload)` accepts `title_name` and returns it in the result.

- [ ] **Step 1: Write failing tests** for a `Template` control, a single Text+ control, one writable non-expression Text+ control, ambiguous controls, unavailable title, selected title forwarding, and rollback.
- [ ] **Step 2: Run** `pytest tests/unit/test_resolve_textplus_timeline.py -q` and verify the new compatibility cases fail.
- [ ] **Step 3: Replace the constant title** with the validated payload value and implement ordered text-control discovery without editing expression-driven internal nodes.
- [ ] **Step 4: Keep text-before-trim behavior** and extend final verification to title name, text, ranges, clip count, and source signature.
- [ ] **Step 5: Run focused Resolve tests** and verify they pass.

### Task 4: Drag-and-drop template UI

**Files:**
- Modify: `backend/app/transcript_intent_ui.py`
- Test: `tests/unit/test_transcript_intent_ui.py`
- Test: `tests/social_gallery_controller.cjs` or a new focused Node controller if interaction coverage requires it.

**Interfaces:**
- Consumes: Task 2 list/upload/select/install endpoints and Task 3 generation response.
- Produces: template selector, drop zone, installation action, readiness state, and guarded timeline creation.

- [ ] **Step 1: Write failing rendered-page assertions** for selector, drop target, file input, install action, four status states, default template copy, and preserved JSON controls.
- [ ] **Step 2: Add controller tests** for upload progress, successful auto-selection, invalid package feedback, missing selected file, restart-required disabling, and no fallback.
- [ ] **Step 3: Run focused Python and Node tests** and verify they fail before UI implementation.
- [ ] **Step 4: Implement the compact panel** with accessible drag/drop, file picker fallback, upload progress, selection persistence, install status, and actionable messages.
- [ ] **Step 5: Run focused UI tests and `node --check`** on the rendered application script; verify all pass.

### Task 5: Product verification and real Resolve acceptance

**Files:**
- Modify: `.superpowers/sdd/2026-09-27-transcript-intent-workflow/progress.md`
- Modify: `docs/WINDOWS_DESKTOP_APP.md`

**Interfaces:**
- Consumes: complete Tasks 1–4.
- Produces: verified desktop build and operator instructions.

- [ ] **Step 1: Run Python compilation** for all changed application modules.
- [ ] **Step 2: Run the complete pytest suite** with the established writable temporary fixture and remove test-generated artifacts afterward.
- [ ] **Step 3: Run rendered JavaScript syntax checks and `git diff --check`**.
- [ ] **Step 4: Restart RAMBLA** and verify the bundled KURA item appears selected with truthful installation status.
- [ ] **Step 5: Real acceptance in Resolve:** create a separate timeline, verify all clips are named `KURA_paper_title_v8`, verify selected text values and exact frames, and verify the source signature is unchanged.
- [ ] **Step 6: Probe an unknown title name** in a rollback-safe temporary operation and verify the UI/API reports unavailable/restart guidance without leaving a timeline.
- [ ] **Step 7: Update operator documentation and progress ledger** with build URL, tests, timeline name, title name, text values, frame ranges, and source preservation evidence.
