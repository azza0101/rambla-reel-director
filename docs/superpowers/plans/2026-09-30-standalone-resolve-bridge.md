# Standalone Resolve Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the blocking Resolve Utility UI with a standalone, automatically polling RAMBLA bridge launched from Resolve.

**Architecture:** A stable Resolve script launches or focuses a Tkinter bridge process from the workspace. The standalone process owns heartbeat, status/package polling, confirmation UI, and calls the existing HTTP handoff endpoints; the existing server remains the only Resolve writer.

**Tech Stack:** Python 3.12, Tkinter, urllib, FastAPI endpoints, pytest.

**Spec:** `docs/superpowers/specs/2026-09-30-standalone-resolve-bridge-design.md`

## Global Constraints

- One bridge instance per machine.
- No Resolve mutation before **APPLICA**.
- Active-timeline apply retains TEMP backup and existing-item protection.
- Closing the bridge stops heartbeat and RAMBLA reports offline within the existing lease timeout.
- The installed Resolve launcher must remain stable across future workspace updates.

## Review Focus

- RAMBLA restarts on another port: bridge rediscovers it and resumes without closing.
- Resolve project/timeline changes: status refreshes and package selection remains session-safe.
- Multiple pending revisions: only the newest matching package is displayed.
- Apply failure: package remains retryable and the diagnostic is visible.
- Second launch: focuses the first instance and creates no duplicate heartbeat.

---

### Task 1: Polling model and transport

**Files:**
- Create: `tools/resolve_bridge/standalone_bridge.py`
- Create: `tests/unit/test_standalone_resolve_bridge.py`

**Interfaces:**
- Produces: `BridgeClient`, `BridgeSnapshot`, `discover_base()`, `poll_once()`, `receive_package()`, `apply_package()`, `discard_package()`.

- [ ] Write failing tests for port rediscovery, heartbeat refresh, newest matching package selection, failed apply diagnostics, and no-package state.
- [ ] Run `python -m pytest -p no:cacheprovider tests/unit/test_standalone_resolve_bridge.py -q`; expect failures for missing module/interfaces.
- [ ] Implement the transport and immutable snapshot model without UI dependencies.
- [ ] Re-run the test file; expect all tests to pass.

### Task 2: Standalone window and single-instance lifecycle

**Files:**
- Modify: `tools/resolve_bridge/standalone_bridge.py`
- Modify: `tests/unit/test_standalone_resolve_bridge.py`

**Interfaces:**
- Consumes: Task 1 `BridgeClient` and `BridgeSnapshot`.
- Produces: `BridgeApp`, `SingleInstance`, `main()`.

- [ ] Write failing tests for apply gating, destination selection, one-second scheduling, close/heartbeat cleanup, and second-launch focus signaling.
- [ ] Run the focused tests; expect failures for missing lifecycle/UI interfaces.
- [ ] Implement Tkinter rendering, `after(1000, ...)` polling, status/package cards, progress updates, apply/discard actions, and localhost single-instance focus signaling.
- [ ] Re-run all standalone bridge tests; expect all to pass.

### Task 3: Stable Resolve launcher

**Files:**
- Replace: `tools/resolve_bridge/RAMBLA_B_ROLL.py`
- Modify: `tests/unit/test_resolve_bridge.py`
- Modify: `tests/unit/test_resolve_handoff_ui.py`

**Interfaces:**
- Consumes: Task 2 `standalone_bridge.py` entry point.
- Produces: a non-blocking launcher that starts `pythonw standalone_bridge.py` or signals the existing instance.

- [ ] Write failing source-contract tests proving the launcher contains no `UIDispatcher.RunLoop`, package polling, or self-replacement logic and launches the standalone entry point hidden.
- [ ] Run the focused launcher tests; expect the old embedded bridge to fail them.
- [ ] Replace the Utility script with the minimal launcher while preserving workspace and interpreter discovery diagnostics.
- [ ] Re-run bridge, handoff UI, and standalone bridge tests; expect all to pass.

### Task 4: Integration and live-safe verification

**Files:**
- Modify: `backend/app/curation_server.py` only if the standalone client reveals an endpoint contract gap.
- Modify: relevant unit tests for any endpoint change.

**Interfaces:**
- Consumes: existing session, pending, received, apply, discard, capture, and status endpoints.
- Produces: verified end-to-end package receipt without pressing **AGGIORNA**.

- [ ] Run the complete Resolve bridge/handoff test slice and fix only contract failures: `python -m pytest -p no:cacheprovider tests/unit/test_standalone_resolve_bridge.py tests/unit/test_resolve_bridge.py tests/unit/test_resolve_handoff.py tests/unit/test_resolve_handoff_jobs.py tests/unit/test_resolve_handoff_ui.py tests/unit/test_resolve_textplus_timeline.py -q`.
- [ ] Launch the standalone bridge against the local RAMBLA server and verify heartbeat changes to connected, current Resolve project/timeline appear, and a prepared package becomes received automatically.
- [ ] Close the window and verify the session becomes offline after the lease timeout.
- [ ] Do not press **APPLICA** during the smoke test; report the package as ready for user confirmation.
