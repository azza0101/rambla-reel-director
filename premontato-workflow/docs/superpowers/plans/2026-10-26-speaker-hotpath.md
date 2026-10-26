# Active-speaker analysis: bounded performance patch

User request: optimize the slow local speaker-check phase, continuing on an isolated integration branch. Initial base `539b6e277947ed7473f94ea4ec042f960ddfa09a` (v0.11.8); updated integration parent `a69e7aa8886d61f111487ecb2c0c5da876071fdc` (v0.11.9), preserving intervening editorial and timeline changes. Only `premontato-workflow/`; coordination on PR #19. This patch is independent of PR #20.

## Design and invariants

- Preserve model weights/hash, CPU provider, two inference threads, 25 fps samples, detector settings, tracking, full-plus-short inference averaging, float32 reductions, rounding and decision thresholds.
- Smooth coordinates with one edge-padded array and vectorized 13-frame medians instead of padding each coordinate separately. Crop only the requested region, with identical Python slice semantics and border pixels; internal crops may be views. Verify pixels and coordinates against the previous implementation.
- Retain the existing v3 interval cache. Add a separate versioned sample cache keyed by source fingerprint, actual sample offset/duration, source duration, fps and model. Store unrounded float32 frame scores and track geometry, never source frames/audio. Summarize the requested interval separately; identical sample windows can have different speaking results.
- Invalid sample caches are recomputed. Errors are not cached. Rounded-empty requests still avoid model inference. Cache hits must report fresh elapsed latency separately from the legacy historical `seconds` field.
- Record decode, audio/features, detection, tracking/cropping and inference durations plus actual operation counts. A standalone local benchmark uses its own temporary cache and distinguishes cold audio, warm PCM, exact-interval reuse and equivalent-window reuse. No automatic deletion of the user's cache.

## Execution and validation

1. Preserve/verify the exact remote snapshot and record coordination before edits.
2. Add failing regressions: pixel/median equivalence, distinct classifications for a shared sample, persistent and legacy cache reuse, source/window invalidation, invalid-cache recovery, failed inference retry and short/no-face cases.
3. Implement only `worker/active_speaker.py`, then add the generic benchmark and focused documentation.
4. Run focused tests, the product suites, an independent review, and bounded synthetic profiling/equivalence using the shipped ONNX model. Distinguish these results from native Resolve/video acceptance.
5. Publish one isolated commit and draft PR to `feat/premontato-workflow`; no merge, model/package/release change, or provider request.

Expected benefit: fewer preprocessing allocations on a first computation and no repeated decode/tracking/inference for exactly equivalent sample windows. Different windows still need their own inference; no whole-pipeline speedup is assumed.
