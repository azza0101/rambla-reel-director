# RMBL Auto-Cut — separate source snapshot

Resolve Workflow Integration and Python Auto-Cut engine. Snapshot of engine v0133 / integration 0.1.11 plus local Apply safety changes.

Current-timeline Apply uses the existing API-only path: CUT on the left, disabled previous edit nested on the right, BCK safety timeline. Native keyboard archive prototype is included for reference but disabled in the service (`editable_archive=False`). No simulated keyboard input is enabled.

The shared Python engine is included to preserve imports; this is a source snapshot, not a self-contained installer. Python dependencies are in pyproject.toml. Resolve's native Workflow Integration SDK/runtime is not redistributed. Provider credentials, GitHub tokens, user projects, media, caches and logs are excluded. Configure credentials locally.

See docs/AUTOCUT_INTEGRATION.md and tools/install_autocut_integration.py for installation. Existing release/update locations are unchanged; this snapshot does not publish a release or modify the installed application.
