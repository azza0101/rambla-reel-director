# RMBL Auto-Cut — Workflow Integration 0.1.1

## What is implemented

A dedicated Resolve Studio integration: source import, shared Auto-Cut analysis, full transcript with strikeouts and alternative takes, word-range exclusions/restores, undo/redo, pause presets and low-resolution preview. Explicit Apply calls the existing native CUT engine on a new timeline and preserves the source timeline. No Bridge GUI, no outbox or heartbeat, no standalone browser app.

The first source adapter requires exactly one complete video clip in the timeline. It refuses trimmed/multiple/compound video sources rather than silently processing a different range. Existing ASR is used; the installed Resolve SDK does not expose a documented read/export method with exact word timings. No claim of native transcript ingestion yet.

## Windows on this development PC

Run INSTALL_RMBL_AUTO_CUT.ps1. It uses the existing .venv and copies the matching WorkflowIntegration.node from the installed Resolve SDK. Saves and data are isolated in ../autocut-data; existing RMBL and Bridge projects are untouched. Provider settings are read from the existing local .env.local; no credentials are copied into plugin JavaScript or runtime.json.

Save your Resolve project, restart Resolve if necessary, then choose Workspace > Workflow Integrations > RMBL Auto-Cut. Open the source timeline, click USA VIDEO DELLA TIMELINE and then AVVIA AUTO-CUT. Review manually and Apply only when satisfied. A new timeline is created; the original remains available.

External scripting must remain Local for the hidden Python apply helper, as in the existing working installation. The plugin uses the official native SDK for reading the source context. Apply is the original Python native engine, not a reimplementation of clipping in JavaScript.

## macOS / distribution status

Sources and installer platform paths are prepared for Windows/macOS. INSTALL_RMBL_AUTO_CUT.command expects an existing .venv/bin/python with the RMBL dependencies, FFmpeg/FFprobe, and the Blackmagic distribution of Resolve Studio. A physical Mac test, native SDK loading, code signing/notarization and a self-contained one-click runtime installer are pending. Do not present this developer integration as a complete portable Mac/Windows installer.

## Safety and rollback

- Worker binds only 127.0.0.1, with a random per-session header token for page/API/media access.
- Renderer has no Node integration or arbitrary filesystem/API bridge; preload exposes only a source snapshot.
- One instance; closing refuses during analysis/apply. Clean authenticated worker shutdown.
- Stale source or CUT revision is rejected; wrong current project/timeline is rejected before native editing.
- Apply uses a new owned timeline and the existing native engine's cleanup on failure. No automatic Apply or AI calls at startup.
- Remove only com.rambla.autocut from Workflow Integration Plugins to uninstall. Data remains in autocut-data. On plugin-file updates, previous files are backed up under autocut-data/install-backups.

## Verification

Windows: worker startup/authentication/UI/clean shutdown verified from the installed runtime. Browser smoke on synthetic video: word range exclusion saved, alternative-take dialog opened, actual preview generated, no JavaScript errors and no horizontal overflow at 680 px. Zero AI calls and zero Resolve mutations during these tests. Native SDK/plugin opening and real current-timeline Apply still require the user's next test in Resolve. Existing native engine is covered by its mocked regression tests.


## Updates without restarting Resolve (0.1.1)

AGGIORNA in the Auto-Cut header refuses during CUT/APPLICA or an unsaved word-range selection. It stops the worker cleanly, applies verified managed-code updates and relaunches only the Electron integration. The last project/context is restored from autocut-data; user media, choices, credentials, Python runtime and WorkflowIntegration.node are not updated or deleted.

On this development checkout, AGGIORNA reloads local source changes and synchronizes the plugin JavaScript. Registered installed copies check dedicated GitHub autocut-* releases using the preconfigured GitHub access; code-only ZIP is SHA256 checked, path/size/symlink validated, dependency changes require a new installer, and code files have backups with a local path manifest plus automatic rollback on write failures. Close a separate RMBL main application before updating its shared engine, if it is running; Resolve stays open.

First plugin registration or a future native SDK/host compatibility change can still require restarting Resolve. The normal update does not replace the loaded native SDK. Relaunch was verified with an Electron lifecycle mock and actual worker restart tests; the real Resolve integration host still needs the user's opening/update test.
