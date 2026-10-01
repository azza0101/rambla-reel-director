# RAMBLA · B-ROLL Resolve Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect an active Resolve timeline to RAMBLA · B-ROLL and round-trip generated edits into safe versioned copies.

**Architecture:** A Resolve Utility script talks to localhost HTTP endpoints. A focused bridge service owns Resolve inspection/rendering and persists timeline linkage in each RAMBLA project. Existing exporters consume that linkage and always duplicate the recorded source.

**Tech Stack:** Python, FastAPI, DaVinci Resolve scripting API, Fusion UI Manager, vanilla HTML/CSS/JS.

**Spec:** `docs/superpowers/specs/2026-09-30-rambla-broll-resolve-bridge-design.md`

## Global Constraints

- Never start Resolve from RAMBLA.
- Never mutate or delete the linked source timeline.
- Every generated timeline and media bin is versioned under `TEMP`.
- Use the active timeline In/Out; fall back to the complete timeline.

## Review Focus

- Resolve closed: return a readable error without side effects.
- RAMBLA closed: plugin starts it and waits with a timeout.
- Missing In/Out: capture full timeline.
- Changed source timeline: refuse export before duplication.
- Render failure: remove only the bridge-created job and retain source state.

### Task 1: Bridge domain and capture

**Files:** Create `backend/app/resolve_bridge.py`; create `tests/unit/test_resolve_bridge.py`.

- [ ] Test range selection, stable identity, render cleanup and manifest payload.
- [ ] Implement Resolve inspection and capture with no source mutation.
- [ ] Run bridge unit tests.

### Task 2: HTTP integration and project linkage

**Files:** Modify `backend/app/curation_server.py`; modify `backend/app/curation_project.py`.

- [ ] Test status/capture endpoints and persisted linkage.
- [ ] Import rendered audio through the primary-audio pipeline.
- [ ] Run API tests.

### Task 3: Resolve Utility UI and installer

**Files:** Create `tools/resolve_bridge/RAMBLA_B_ROLL.py`; create `INSTALL_RESOLVE_BRIDGE.ps1`.

- [ ] Test launcher/startup and endpoint request logic without Resolve.
- [ ] Implement themed Fusion UI Manager window and one-click install.
- [ ] Install into the user's Resolve Utility scripts directory.

### Task 4: Safe linked-timeline export

**Files:** Modify `backend/app/resolve_textplus_timeline.py`; modify its tests.

- [ ] Test source resolution by ID, offset conversion and version allocation.
- [ ] Export only to a duplicate under `TEMP` with matching media bin.
- [ ] Run Resolve timeline tests.

### Task 5: Branding, Envato and real verification

**Files:** Modify UI/launcher strings and browser profile launcher.

- [ ] Rename visible product surfaces to `RAMBLA · B-ROLL`.
- [ ] Verify Envato opens through the Windows URL shell.
- [ ] Run the installed bridge against Resolve and verify source signatures before/after.
