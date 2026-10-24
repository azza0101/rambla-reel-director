# Save, restore and update implementation plan

Goal: show update stages, save Resolve and Premontato work, restart only the plugin, reopen persisted work.
Architecture: existing session.js owns versioned atomic JSON project documents and automatic recovery; native dialogs select named saves. Existing updater.js owns streaming verified downloads and a private, random progress pipe for the elevated installer. Electron relaunch preserves its original launch arguments and runs only after successful install/save. No Resolve process restart. User already authorized autonomous implementation.

- [ ] Tests first: project roundtrip, corrupted save preservation, source modification invalidation, Resolve SaveProject failure, streaming progress/hash and restart ordering.
- [ ] Atomic project save/load and autosave, source fingerprints, draft persistence and restore validation. Renderer save/save-as/open controls.
- [ ] Resolve SaveProject via SDK before update, before/after timeline work and periodically while idle; failures visible.
- [ ] Update progress from network bytes and elevated install phases, shutdown worker, automatic plugin relaunch; no restart on failed save/install.
- [ ] Verify renderer/real Electron harness and packaging; publish dedicated release without main merge/latest promotion. Old versions require one manual reopen to load this new updater.
