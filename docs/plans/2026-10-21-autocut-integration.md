# Auto-Cut Resolve Integration — implementation plan

Goal: extract the existing Auto-Cut into one Resolve Workflow Integration, with no visible Bridge or RMBL browser app. User approved the described flow and explicitly requested implementation on 2026-10-21.

Architecture: sandboxed Electron integration talks to the bundled native WorkflowIntegration SDK; a loopback-only authenticated Python worker reuses install_cut_routes, CutEngine, cut_pass_ui, native_cut_export and create_native_cut_base. Dedicated data root, projects and runtime; no change to existing RMBL projects. No duplicated take-selection algorithm.

First deliverable: import the original video from a single full-length timeline clip, launch existing cloud Auto-Cut on explicit click, display full word review/exclusions/alternative takes/undo/redo/pause presets and preview. Apply on explicit click creates a new native timeline; source timeline remains intact. Alternatives are disabled red video clips capped to the chosen phrase. Initial version refuses trimmed/multiple video clips rather than silently processing the wrong range.

Windows and macOS share UI/worker/adapter sources; native SDK is copied from the local Resolve installation for the matching platform. Windows verified here; macOS installation and rendering require a physical Mac test. Studio required. No DRFX pretending to install an application.

API tokens: read existing local .env.local through the established settings loader; never embed keys in versioned JavaScript or Git. Future personal installers may provision the existing dedicated keys separately. Python runtime currently provided by installed RMBL; standalone bundled distribution is a subsequent packaging milestone, not claimed complete.

Resolve transcript: installed SDK exposes TranscribeAudio but no documented read/export method with word timing. This milestone uses the existing ASR; native transcript adapter remains pending evidence.

- [x] Tests: worker session auth, source identity/reuse, exact current revision, no bridge routes, native source-frame contract; mocked Resolve adapter failures/cleanup/alternative clip state.
- [x] Implement focused worker and shared CUT UI host.
- [x] Implement secure Electron lifecycle, single instance, read-only Resolve source adapter and local installer.
- [ ] Verify browser review, unit tests, source snapshot through SDK if plugin can be loaded; never auto-apply.
- [ ] Publish source commit and provide installation/opening instructions with real test limitations.

Rollback: remove only com.rambla.autocut from Workflow Integration Plugins; persistent autocut-data remains. Existing RMBL/bridge untouched. A failed Apply removes only its new owned timeline and restores the original timeline.
