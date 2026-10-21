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


## Provider JSON recovery and automatic support (0.1.3)

CUT requests recover provider output-validation failures by requesting a new complete json_object document with the full schema in the instructions, then validating against that schema locally before accepting/cache-writing it. Request/schema errors are not treated as recoverable output errors. Truncated output retains the bounded quota-aware recovery. No failed_generation fragment is used as a plan.

On 2026-10-21 the user explicitly authorized automatic GitHub debugging for Auto-Cut. Its dedicated diagnostics settings enable automatic reporting only on the first authorized start; a later opt-out stays off. ASSISTENZA exposes the current sanitized report, delivery status, copy and automatic toggle. The existing private-repository requirement, allowlist, deduplication, retries and daily budget are reused. Categories distinguish PROVIDER_JSON and PROVIDER_OUTPUT_TRUNCATED. Transcripts, media, API keys and local paths are excluded. No continuous Codex monitoring or automatic patching is implied. Original failure was submitted as private GitHub issue #16.


## v0.1.5 editorial review

CUT uses Groq for contextual ASR-block selection and local measured-word reconciliation for nearby retakes. Proposals are versioned separately from measured ASR cache. `cut/editorial-review.json` stores original and kept text, decisions, and warnings locally, excluded from GitHub support reports. Partial generated output is never used as a CUT result.


## 0.1.6 / v0128 — selected range and retained source

Use `USA VIDEO DELLA TIMELINE` after setting Resolve IN/OUT. Video/audio marks must agree. Resolve marks are relative to timeline start and OUT is inclusive; the stored source range is half-open. With no marks the entire source is analyzed. A changed range creates/reuses a separate project, preserving the full-video project and original file. Only selected audio is sent to Groq; ASR words are offset to absolute original-file times. All CUT rebuilds clamp breathing handles to that range.

Apply uses a styled dialog: new timeline, or current timeline. The current-timeline path requires one untrimmed full source video/audio, creates a numbered backup in BCK, compacts the CUT at the start, then retains the full original reference after a two-second gap with both video and audio disabled. It sets IN/OUT to the CUT only and adds CUT/ORIGINALE markers without overwriting existing markers. A failure activates the complete BCK and reports its name; the partially edited timeline is never deleted. The original file is never modified. The scripting API reconstructs references to the original media; this does not preserve the identity of the old TimelineItem objects. Timeline identity is preserved.

The duplicate synchronous Workflow SDK call before Apply was removed; the isolated apply process still validates current project/timeline before mutation. VFR duration checks use original-file identity, untrimmed offsets and actual retained-frame availability rather than requiring exact agreement between container duration and Resolve decoded duration.

GUI, source-adapter and engine regressions are tested locally. Real selected-audio extraction is verified without new cloud calls. Physical current-timeline application remains user-triggered; no automatic Apply was performed during implementation.


## 0.1.8 / v0130 — reapply from memory

Current-timeline Apply now checks the live timeline before mutation. An edited timeline (including disabled source clips) requires a styled OK/Cancel confirmation. OK preserves the complete current timeline as a disabled nested reference after the new CUT; its editable backup remains in BCK / timeline name, numbered with date/time. Reapply uses the saved CUT and pause choices without reimporting or reanalyzing. A fingerprint prevents applying an outdated confirmation after additional edits. Cancel performs no apply request. The new CUT itself remains native clips. Existing loose BCK entries are retained unchanged. Physical application remains user-triggered.
