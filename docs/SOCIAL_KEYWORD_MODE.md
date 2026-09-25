# Social keyword mode and beat-scoped media reset — 2026-09-23

Implemented locally in api-first-v5; no remote SHA published in this change.

- TikTok, Instagram and YouTube Shorts default to keyword/metadata discovery. Both Qwen thumbnail ranking and automatic clip acquisition/verification are skipped. Qwen embedder construction is lazy; this path does not invoke it.
- Beat toolbar checkbox `Verifica social con Qwen (GPU)` opts beat research back into the previous visual pipeline, through validated `visual_verify` request/search options. Default off. Global social search remains lightweight.
- Discovery cards remain unverified; this mode cannot establish absence of overlays or visual accuracy. Explicit preview/download actions remain available.
- `CLEAN MEDIA · QUESTA FRASE` clears target beat video/image rows and selections, rebuilds video diagnostics and resets its gallery rounds. It retains transcript, editorial plan, other beats and shared downloaded media. No real user artifacts were cleaned during tests.
- Verified-shot cache version bumped to prevent reuse of previous social verification behavior. Scoped cleanup also invalidates target shot cache records.
- Verification: 593 tests passed; backend compile and rendered inline JavaScript syntax passed. Includes default no-inference/no-download tests for all three providers, explicit opt-in test, scoped artifact preservation and busy/unknown route guards.
- Real TikTok searches/GPU profiling were not run for this change. Existing server needs RESTART_RAMBLA_V5.ps1 to load code.
