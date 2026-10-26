# Integrated performance implementation

Baseline: 52244b93f9437b04e430132d918fe744f8b02bb0; branch perf/premontato-integrated-reuse-20261026 targets feat/premontato-workflow. Scope is premontato-workflow only. No UI automation, no new Groq requests, no additional agents.

1. Baseline full suites and frozen real-media Session.analyze benchmark, private cold local caches and preseeded Groq dialogue/editorial caches; rerun in the same worker.
2. Integrate PR20 and PR21 preserving all editorial code. Fix shallow source mutation with existing failing payload-integrity test.
3. Shared fingerprinted RMS accessor for protocol and internal listening/breath callers; retain targeted silence checks. Test cache hits, invalidation and unavailable results.
4. Context-local runtime telemetry grouped into initial speaker, recovery and listening phases, counting interval/sample cache hits, decoded samples, faces/crops and inference. Report progress between candidate checks and beats without pretending a fixed candidate count. Preserve compact listener proof.
5. Separate Groq classification/editorial wall time and cache counters. Display aggregate local timings and growing reaction search activity in the existing panel; no new always-open debug grids.
6. Full suites; compare final scene source signatures and cache-only Groq results to frozen baseline; real Windows/Resolve native readback on a new version-labelled test timeline only if final decisions pass invariants.
7. Publish an integration PR against feat/premontato-workflow, no release or main merge. Document measured limits and avoid speculative GPU/proxy changes.

Ledger:
- Native worktree tool failed Not a git repository; manual isolated checkout created in workspace. Original checkout remains untouched.
- Baseline 125 JS /137 Python pass.
- PR20 conflict resolved from full baseline staged_dialogue.py, replacing only encoder access; commit ab1c5da. PR21 applied cleanly; commit 7a70e35.
- Combined 134 JS pass; existing test_semantic_reuse payload-integrity assertion exposes _editorial_shot_size mutation as anticipated.

- Shared RMS accessor, plan-scoped ASD/RMS/semantic trace, separate Groq timings and reaction-candidate progress implemented; report panel collapsed by default. Detailed trace is for groq_staged_v1; other paths show unavailable rather than fabricated zero costs.
- Unit suites reached 139 JS / 163 Python, no skips on Windows. Source-integrity test retained and passing.
- Benchmark harness issue discovered: shared embedded Python _pth imported original development worker instead of requested worktree. Earlier optimized timing comparisons are invalid and discarded. Generic benchmark now bootstraps sys.path explicitly and asserts/hashes actual module origins in worker-source.json. Missing ignored model/tokenizer were copied from existing pinned local assets after SHA256 validation; no package/global Python changes.
- Verified baseline c4 uses frozen 52244b9 worker, private cache on C, seeded visual analyses and Groq caches only; first local computation 119.096 s, warm 2.080/1.836/1.848 s. Full vision is intentionally excluded from this verified CPU/cache comparison. Correct integrated run c2 in progress.

- Final verified integration c2: first local computation 130.766 s (vs119.096), warm 0.851/0.748/0.600 s (median0.748 vs1.848). All 8 source signatures identical. No shared-sample hits on this scene; no general first-pass speed claim. Decode102.925s vsinference15.287s dominates; proxy/batched decode is a future validated experiment, not an included change.
- Native API test passed with19 V2/A2 +3 V3, mono audio, 1618frames, source/current timeline preserved. No control sessions were reopened after OFF.
- Final whole-change self-review performed (no additional agents per user request). Detailed new performance UI still requires visual release validation; no new release/install requested by this handoff.
