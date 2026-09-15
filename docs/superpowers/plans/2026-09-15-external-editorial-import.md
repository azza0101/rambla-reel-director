# External editorial import implementation

User-approved design: move editorial reasoning outside the critical local runtime; use a neutral JSON contract. Single-worker execution; no installation, no further generation, no Resolve mutation.

1. Add neutral schema, transcript export and strict timeline/identity validation. Test invalid coverage, stale inputs, continuity and shot constraints before implementing.
2. Add project API import/export and version-isolated atomic persistence. Source stages require a validated import.
3. Adapt imported visual beats directly to image/video searches; preserve queries and shot descriptions, optional retrieval ranking, provenance and global dedupe. Preserve experimental injected/local Director as an optional exporter.
4. Add copy/export/paste/file UI, beat-based curation, source links and truthful playable/discovery cards. Test controller behavior without model dependencies.
5. Run live providers on a small manual transcript/plan fixture, verify mapping, media bytes, selection persistence and timings. Do not generate KURA or rerun ASR.
6. Full regression and compile checks, document evidence/limits, publish verified file set through GitHub API with expected-parent and remote-file verification.

Executed evidence is recorded in `docs/EXTERNAL_EDITORIAL_PLAN.md`; private runtime artifacts remain local.
