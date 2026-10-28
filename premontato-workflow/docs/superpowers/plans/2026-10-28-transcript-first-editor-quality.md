# Transcript-first editor quality implementation plan

Approved scope: autonomous development and real-source checks for at least 40 minutes, by user instruction. Continue the existing experimental branch; do not merge main or touch other products.

Goal: preserve observed improvised exchanges, identify source-local voices and positive face matches, select coherent fields, and report unresolved coverage honestly across multiple scenes.

Architecture: a lossless observed-performance ledger precedes all cleanup. The screenplay supplies scene context, not a whitelist of speech. Source-local voice profiles and verified face references constrain camera candidates. Turn alignment preserves complete spoken exchanges and source provenance. A deterministic audit rejects repeated source, partial words, uncovered same-field joins and sub-1.5-second reactions. Uncertain analyses remain explicitly uncertain.

Tasks:
- [x] Benchmark an existing local ONNX speaker embedding against the MFCC baseline with leave-one-utterance-out checks; verify model license and inference preprocessing, use Z only for isolated models/dependencies.
- [x] Implement tested source-local voice profiles and confidence gates; no hardcoded identities or per-file production exceptions.
- [ ] Implement observed-turn alignment and last-complete-performance selection, keeping repeated gag responses and rejecting unmatched adlibs from other scenes.
- [ ] Implement source-supported cleanup and listening cutaways spanning actual joins. No missing coverage may be relabeled as verified.
- [x] Run automatic scene tests on at least three independent scenes/excerpts, with benchmarks and separate content/voice/field/continuity checks.
- [ ] Integrate a coherent worker/panel experimental path only if checks establish an improvement; preserve legacy and installer compatibility.
- [ ] Render inspected low-resolution previews and, if plan audit passes, test a new versioned timeline through Resolve APIs while preserving existing timelines.
- [ ] Run Python and JS suites, inspect diff, commit/push logical changes and document limitations; no stable release without a passed native gate.

Acceptance is measured, not claimed as human-level perfection. No Codex-authored production cut plan or GUI/mouse automation. Original media, user timelines, project settings, and external workloads are preserved.

Ledger start: 2026-10-28 21:26:51 UTC. Minimum work window ends 22:06:51 UTC.

Measured outcome: local voice identity and safety regressions implemented; experimental worker path available. Field/source locking is implemented, but take/run segmentation within a long source and verified listening coverage remain incomplete. Three real-scene edit tests failed editorial acceptance, so no panel default replacement, installer, release or native timeline mutation was performed. The interval audit is explicitly separate from editorial readiness. See docs/performance/2026-10-28-local-voice-observed-edit-validation.md for evidence.
