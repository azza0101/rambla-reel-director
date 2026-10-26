# Visual review implementation plan

Goal: expose phase results and review real stills, framing and visible characters before timeline creation.
Architecture: keep existing YuNet scan cache. Add a separate cached sparse visual review in shot_analyzer.py, with local SFace face grouping and anonymous labels. Manual scene-character assignments are authoritative and restricted to reviewed source intervals. Identity suggestions never imply active-speaker recognition. Existing worker module names remain compatible with older updaters.

- [x] Add failing tests for conservative face clustering, reviewed character coverage, review validation and timeline gate.
- [x] Pin Apache-2.0 SFace model, include it in offline builds; sample at most two stills per ten-second interval and cache by source fingerprint/version.
- [x] Add secure IPC review results and confirmations; rebuild candidate selection using confirmed visible characters, with unknown coverage as fallback and explicit warnings.
- [x] Add still cards, cast corrections, pending confirmation state, phase-local bars, counts, elapsed time and error status; test real renderer.
- [ ] Complete package validation and publish isolated product release after verification; unit, media and UI checks already passed. Distinguish harness tests from installed Resolve tests.
