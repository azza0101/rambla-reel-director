# Integrated local reuse — validation 2026-10-26

## Scope and source
Baseline: 52244b93f9437b04e430132d918fe744f8b02bb0 (release 0.11.11 plus documentation). Integration branch: perf/premontato-integrated-reuse-20261026, target feat/premontato-workflow. PR20 6f2cdbbefceb8daa2b6d935ae43e44b5f8bc3fe1 was cherry-picked as ab1c5da; PR21 09b6b76e4c8139962819e4292deda4520c9437b6 as 7a70e35. No merge/main/product release.

The staged conflict preserves the complete 0.11.11 single-camera and editorial code and changes encoder access only. Additional changes fix shallow source mutation, share fingerprinted RMS between IPC/listening/breaths, aggregate current ASD/RMS/semantic work, distinguish both Groq stages, and expose live candidate progress plus a collapsed performance summary. Models, thresholds, source words and timing policies remain unchanged.

## Measurement method
Windows host, five real clips. Existing Resolve transcripts, Groq classifications and editorial response were reused; HTTP was explicitly forbidden in the benchmark. Visual analyses were also preseeded for this verified comparison. First run means PCM/RMS/ASD caches initially empty, NOT a complete first-time import/transcription/visual analysis. Subsequent runs use the same worker and caches. Caches reside in private directories on C, matching the installed product drive. No production cache or global Python was modified.

A harness issue initially let the shared embedded Python import development modules from its _pth file. Those optimized comparisons were discarded. tools/benchmark_pipeline.cjs now inserts the requested worker root before imports, asserts module origins, and records their paths and SHA256 in private worker-source.json. Model/tokenizer files were copied from existing local pinned assets and hash-verified.

| Case | Baseline | Integration | Interpretation |
|---|---:|---:|---|
| First local computation, visual/Groq cached | 119.096 s | 130.766 s | No demonstrated first-pass improvement; one measured pair is 9.8% slower |
| Warm run 1 | 2.080 s | 0.851 s | Same worker reuse |
| Warm run 2 | 1.836 s | 0.748 s | Same worker reuse |
| Warm run 3 | 1.848 s | 0.600 s | Same worker reuse |
| Warm median | 1.848 s | 0.748 s | 2.47x faster / 59.5% less elapsed time on this material |

This is not a controlled machine-isolation experiment or a guarantee for other footage. Resolve transcription, network/quota waits and fresh visual analysis are outside these timings. A preliminary unchanged visual stage alone was about 189 seconds, so warm speedup must not be presented as full-workflow speedup on new files.

## Work actually measured in the integration
First run: 27 initial ASD calls and 16 listening calls; 35 unique video decodes, 105 ONNX inference calls, zero shared-sample hits, 8 interval-cache hits during listening. Decode: 102.925 s; inference: 15.287 s; face detection: 7.580 s; tracking/crop: 0.399 s. Two targeted RMS scans: 0.308 s total. Warm runs: all 43 ASD calls hit interval cache, zero decode/inference, two RMS cache hits and zero scans; 283 semantic text requests hit cache with zero model initializations/embedding computation. Both Groq stages use cache and make zero HTTP requests.

PR21's shared-window benefit is valid in its synthetic tests but was NOT exercised by this scene (zero shared-window hits). Do not claim that it accelerated this first pass. Detailed counters are currently scoped to the staged dialogue engine; legacy paths show unavailable instead of fabricated zero ASD costs.

## Quality and native proof
All eight verified run signatures match exactly: media IDs, source ranges, reaction ranges/offsets and actions. No human cut plan or scene-specific heuristic was supplied. Real payload deep equality also passes after planning.
Native Resolve adapter test created PREMONTATO v0.11.11 - TEST PERF INTEGRATA 104741 under Premontato / v0.11.11 / Test: 19 V2/A2 base items, three V3 video-only inserts, 1618 frames, all three audio tracks mono. Original timeline content and current timeline were preserved. No UI automation or mouse/touch/keyboard control was used after OFF.

The five uncertain/off-camera speaker moments and unverified reaction intention already present in the baseline remain; this is a performance integration, not a new claim of editorial perfection.

## Tests and readiness
139 JavaScript and 163 Python tests pass on Windows, zero skips. Includes shared RMS invalidation/unavailable behavior, actual internal breath reuse, source immutability, scoped current-work accounting, real ASD entrypoint instrumentation, candidate progress and separate Groq timings. git diff --check passes.
Ready for source integration review and packaging. Not installed over the running plugin, not published as a new release. New performance UI is constructed and unit-tested but not visually exercised due the explicit no-automation instruction. Installer/restart path remains to be checked when releasing.

## Decision on further tuning
Keep CPU/ONNX models and current frame mappings. Decode dominates this first pass, not neural inference or face crop copies; a GPU inference variant would target a much smaller fraction and could compete with Resolve/ComfyUI. The next justified experiment is shared low-resolution proxy/batched video decoding, but only after source-frame/audio alignment and editorial equivalence are validated. No unvalidated proxy/GPU change is included here.

## Reproduction
Run tools/benchmark_pipeline.cjs with --project (saved Premontato project), --seed-root (existing Premontato user-data folder), --cache-root (new private directory), --output (local report), --python (bundled runtime), --runs 4, and optionally --seed-shots (a prior cache/shots directory). --product-root selects a frozen baseline checkout. The tool never copies credentials and refuses missing Groq cache rather than sending a request. Raw reports and test footage remain under ignored review/ or private temporary directories and are not committed.

## Final exact-source replay
After a progress-only completion for the conservative reaction path, the final source was replayed with verified imports and the warmed private cache: fresh-worker cached analysis 1.840 s, then 0.275/0.279/0.312 s in the same worker. All signatures still match baseline and native readback. These additional values demonstrate load/cache variability; the table above retains the first paired series rather than selecting the fastest run.
