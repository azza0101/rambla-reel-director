# Resolve Highlighted Titles + Native Subtitles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create and export Resolve timelines containing selected Fusion Titles plus native Subtitle clips for all non-highlighted words, while preserving the complete SRT export.

**Architecture:** A pure combined-manifest builder derives title and subtitle ranges from transcript word timing and intent selections. The isolated Resolve helper gains a native-subtitle compatibility adapter and DRT export path. Existing transcript UI actions move into compact Animation and Editing disclosures without changing their underlying JSON/SRT contracts.

**Tech Stack:** Python 3.12, FastAPI, vanilla HTML/CSS/JavaScript, DaVinci Resolve 21 scripting API, SRT/FCPXML interchange, pytest, Node syntax validation.

**Spec:** `docs/superpowers/specs/2026-09-29-resolve-highlighted-titles-subtitles-design.md`

## Global Constraints

- Complete SRT always includes highlighted words.
- Highlighted words are excluded only from the combined timeline's native Subtitle track.
- Captions contain at most three chronological words and never bridge across a highlighted word.
- Native Resolve Subtitle clips are mandatory; never substitute Text+.
- Use only official Resolve scripting/import/export paths; no mouse or keyboard automation.
- Preserve and save the source timeline; roll back incomplete generated timelines.
- Export combined timelines as native `.drt` with `resolve.EXPORT_DRT`.
- Do not install packages or commit/push mixed worktree changes.

## Review Focus

- Consecutive highlighted words between spoken words must create one hard subtitle gap without swallowing adjacent punctuation.
- An all-highlighted selection must produce zero subtitles but still create valid title clips.
- Resolve builds that import SRT as media but cannot place native subtitle items must fail truthfully and roll back.
- DRT export failure after successful construction must retain the verified combined timeline.
- Repeated combined exports must use unique timeline and file names without overwriting prior work.

---

### Task 1: Combined transcript manifest

**Files:**
- Modify: `backend/app/transcript_intents.py`
- Test: `tests/unit/test_transcript_exports.py`

**Interfaces:**
- Produces: `build_combined_resolve_export(run_root: Path, project_id: str, fps: int) -> dict[str, Any]` with `titles` and `subtitles` arrays.

- [ ] Write failing tests proving complete SRT retains highlights, combined captions exclude highlights, gaps split groups, captions contain at most three words, punctuation/timing survive, and all-highlighted input yields zero subtitles.
- [ ] Run the focused tests and verify they fail for the missing builder.
- [ ] Implement the pure builder by reusing authoritative word timing and existing highlighted-title grouping.
- [ ] Run the focused tests and verify they pass.

### Task 2: Native Subtitle compatibility adapter

**Files:**
- Create: `backend/app/resolve_native_subtitles.py`
- Test: `tests/unit/test_resolve_native_subtitles.py`

**Interfaces:**
- Consumes: Task 1 `subtitles` rows.
- Produces: `render_filtered_srt(rows) -> str`, `insert_native_subtitles(resolve, project, timeline, rows, fps, base_frame) -> list[Any]`, and `verify_native_subtitles(timeline, rows, fps, base_frame) -> None`.

- [ ] Write failing pure SRT/rendering and fake-API verification tests, including empty captions, frame conversion and mismatched native items.
- [ ] Run focused tests and verify failure.
- [ ] Implement temporary SRT creation plus the official SRT media/timeline placement route.
- [ ] Add a rollback-safe live probe in a temporary timeline and inspect `GetItemListInTrack("subtitle", 1)`.
- [ ] If SRT placement is unsupported, ledger the result and implement the official FCPXML caption import route; add its failing tests before production code.
- [ ] Run focused tests and record the supported path for Resolve 21.1.0.17.

### Task 3: Combined timeline creation and DRT export

**Files:**
- Modify: `backend/app/resolve_textplus_timeline.py`
- Test: `tests/unit/test_resolve_textplus_timeline.py`

**Interfaces:**
- Consumes: Task 1 combined manifest and Task 2 subtitle adapter.
- Produces: helper modes `titles` and `combined`; optional `drt_output_path`; result fields `title_count`, `subtitle_count`, `timeline_name`, and `drt_path`.

- [ ] Write failing tests for mode validation, adapter invocation, title/subtitle verification, save behavior, rollback on construction failure, retained timeline on DRT failure, and unique/safe DRT filenames.
- [ ] Run tests and verify failure.
- [ ] Refactor the current title-only materializer into shared construction steps without changing title-only behavior.
- [ ] Add combined subtitle insertion/verification and official `Timeline.Export(path, resolve.EXPORT_DRT, resolve.EXPORT_NONE)` handling.
- [ ] Run focused tests and title-only regression tests.

### Task 4: API routes and downloads

**Files:**
- Modify: `backend/app/curation_server.py`
- Test: `tests/unit/test_resolve_combined_timeline_api.py`

**Interfaces:**
- Consumes: Task 1 manifest and Task 3 helper modes.
- Produces: `POST .../resolve/combined-timeline` JSON and `POST .../resolve/combined-timeline.drt` streamed attachment.

- [ ] Write failing API tests for payload construction, selected template forwarding, combined result, DRT media type/download name, missing highlights, Resolve compatibility errors and absent/empty DRT.
- [ ] Run tests and verify missing-route failures.
- [ ] Implement routes with managed temporary/export files and explicit HTTP error mapping.
- [ ] Run API tests and verify they pass.

### Task 5: Animation and Editing disclosure UI

**Files:**
- Modify: `backend/app/transcript_intent_ui.py`
- Test: `tests/unit/test_transcript_intent_ui.py`

**Interfaces:**
- Consumes: Task 4 routes and existing animation/SRT/title-only routes.
- Produces: `ANIMATION` and `EDITING` disclosure groups with the approved actions and progress copy.

- [ ] Write failing rendered-page tests for the two disclosures, exact action labels, retained template picker, combined creation and DRT download wiring.
- [ ] Run tests and verify failure.
- [ ] Reorganize existing buttons without duplicating handlers; add combined create/download actions and truthful status messages.
- [ ] Run UI tests and rendered JavaScript through `node --check`.

### Task 6: Full verification and real Resolve acceptance

**Files:**
- Modify: `docs/WINDOWS_DESKTOP_APP.md`
- Create: `.superpowers/sdd/2026-09-29-resolve-highlighted-titles-subtitles/progress.md`

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces: verified desktop build, persisted combined timeline and downloadable DRT.

- [ ] Compile all changed Python modules and run all focused tests.
- [ ] Run the complete pytest suite with the established writable temporary fixture; remove generated test artifacts and restore generated schemas.
- [ ] Run rendered JavaScript syntax and `git diff --check`.
- [ ] Restart RAMBLA and verify the new controls in the live page.
- [ ] Create a real combined KURA timeline and inspect every native Subtitle and Fusion Title from a fresh Resolve scripting process.
- [ ] Prove highlighted words are absent only from Subtitle items and remain present in the complete SRT.
- [ ] Export a non-empty `.drt` through the official API and leave the accepted combined timeline open.
- [ ] Update documentation and ledger with build URL, tests, counts, frame ranges and DRT path/size.
