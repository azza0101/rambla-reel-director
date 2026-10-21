# RAMBLA SRT Workflow Integration implementation plan

Goal: independent `com.rambla.srt`, matching the AutoCut visual language, with local autosave, SRT export, standalone installers and manual verified updates.
Spec: README.md, CODEX_TASK.md, REFERENCE.md and the user's explicit instruction to implement continuously without changing AutoCut.
Architecture: sandboxed Electron renderer, narrow IPC, read-only native Resolve adapter, pure JS export engine, local atomic state, isolated updater. No Python runtime dependency. Windows PowerShell and macOS shell installers copy the locally shipped SDK.

## Constraints and decisions
- Only rambla-srt is delivered; AutoCut reference snapshot is read-only and excluded.
- Exact V3.1 Lua archived under reference/v3.1; SHA256 0ac35af7db4df9cd5d96c0fe9b0e8b9b371e7ac7a60e0c2f71ba20b5e91de17c.
- Preserve V3.1 export byte semantics, including concatenation of disjoint ranges in zero mode and existing half-open mark handling. Document any host discrepancy rather than changing silently.
- SINGLE on opening; MULTI explicit. Per-project/timeline state keyed by stable IDs; fingerprint rechecked before export.
- Native API capability must be verified using Resolve's Electron runtime before choosing a helper.
- No automatic replacement of Utility script, no AutoCut paths, no credentials in artifacts, no production release until live Windows/Mac QA is complete.
- Local workspace uses GitHub API transport per repository AGENTS.md. Old curation branch/workspace instructions are superseded by the user's SRT branch and isolation requirement.

## Tasks (inline execution)
- [x] Regression oracle: execute archived Lua unchanged in a simulated UI/Resolve harness, generate actual SRT outputs for single/multi/context/unicode/fractional FPS/DF/boundary cases; test JS renderer against bytes.
- [x] Adapter and session: native read-only snapshot, strict unreadable-caption checks and __flags handling, identity/fingerprint tests, atomic state, stale-export rejection.
- [x] GUI: AutoCut colors, responsive cards, SINGLE/MULTI, captured ranges, options, save indicators and errors. Browser interaction checks at 620px and 125%.
- [x] Update/install: strict file allowlist and size/hash checks, semver release namespace srt-*, immutable SDK/dependencies during updates, staged swap/backup/rollback; test malformed packages and failure recovery. Install/repair separately for Windows/macOS using local SDK, preserve existing scripts.
- [ ] Integration: real native read-only adapter check and local export parity; sandbox installer/update lifecycle tests; publish verified changes to requested branch after remote-parent check. Document unavailable Mac hardware/signing and any remaining live import/menu checks accurately.

Review focus: timeline switch during async reads; damaged state; lost updates on fast input; malicious update entries; installation failure after backup. Each gets a behavioral test in its owning component.

## Final evidence
65 Node tests and browser UI smoke pass. Windows native host export and reopen tested; three actual exports match original Lua bytes. Mac hardware/signing and online release application remain release gates in VALIDATION.md. User requests commit on handoff only, no PR.
