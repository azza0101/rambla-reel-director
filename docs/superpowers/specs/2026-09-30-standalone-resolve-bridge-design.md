# RAMBLA standalone Resolve bridge

## Goal

Replace the unreliable long-running Fusion `UIDispatcher` bridge with a standalone Windows window launched from Resolve's Scripts menu. The bridge must receive packages automatically, expose truthful connectivity, and never modify Resolve until the user presses **APPLICA**.

## Components

### Resolve launcher

`tools/resolve_bridge/RAMBLA_B_ROLL.py` becomes a small stable launcher. It starts or focuses the standalone bridge and exits immediately. It contains no package polling or persistent UI, so Resolve's embedded Python event loop cannot block communication.

### Standalone bridge

A new Python entry point runs with RAMBLA's bundled virtual environment and uses Tkinter for its window. It:

- discovers the active RAMBLA server;
- creates and refreshes a bridge session heartbeat;
- polls Resolve project/timeline status and pending handoffs every second;
- displays package counts, revision, destination choice, progress, errors, and completion;
- calls the existing received, apply, discard, capture, and status endpoints;
- keeps **APPLICA** disabled until a package from the current bridge session is actually received;
- never calls the apply endpoint before the user presses **APPLICA**.

### Single instance

The standalone bridge owns a localhost lock port. A second launcher sends a focus request to the running instance and exits. Closing the window releases the lock and stops heartbeats, so RAMBLA changes to **BRIDGE OFFLINE** after the existing lease timeout.

## Update model

The installed Resolve script remains a stable launcher. All changing UI and polling logic lives in the workspace and is loaded fresh whenever the launcher runs. Future bridge changes therefore require no copying into Resolve and no PowerShell update.

## Timeline safety

- Reading status and receiving packages are non-mutating.
- **APPLICA** retains the existing destination choices.
- Active-timeline mode still creates its required TEMP backup.
- The existing asynchronous handoff job remains the only writer to Resolve.
- Existing video and audio items remain protected by the current materialization checks.

## Failure behavior

- RAMBLA unavailable: show offline and retry without closing the window.
- Resolve unavailable: show the returned diagnostic and keep polling.
- Package mismatch: do not enable **APPLICA**.
- Apply failure: show the server error and retain the package for retry or discard.
- Bridge closed: heartbeat ends and RAMBLA reports offline.

## Verification

- Unit tests for discovery, session heartbeat, package polling, apply gating, destination payload, and single-instance behavior.
- Integration smoke test against the local RAMBLA server with a fake transport.
- Live read-only verification that the bridge detects the current Resolve project and timeline.
- No live apply during verification unless explicitly triggered through **APPLICA**.
