# Local analysis reuse: integration validation

## Scope

Integration parent: `219b91dd07344370806ebac29dbb106216b275ee` (Premontato v0.11.7).
Branch: `perf/premontato-local-reuse-20261026`.
Target: `feat/premontato-workflow`, through a separate draft PR.

Four production files change, all inside `premontato-workflow/`. The v0.11.7 camera-availability changes were adopted before the final checks. This patch does not change the product version, package, model files, release workflow, source transcription or editorial rules.

## Changes and evidence

### Shared semantic encoder

Both local semantic alignment and the Groq-classified staged planner obtain the same lazy encoder in a serial worker process. Model SHA-256 checks still run on first initialization; failed construction does not populate the singleton. Restarting the worker resets it. Text embedding normalization and the existing cache limit are unchanged.

The focused regression runs the real planners and `LocalSemanticEncoder.encode` with model loading/inference replaced at the dependency boundary. Before the patch, a local plan followed by two staged builds constructed three encoders; afterward it constructs one and the repeated staged build performs no additional model inference for cached texts. The synthetic plan and its original word bounds remain identical across the repeated builds. A separate case verifies recovery after failed model initialization.

### Mapped PCM cache hits

Existing `.npy` PCM caches are read-only memory maps. Active-speaker analysis already slices short intervals; those hits no longer allocate the entire cached clip before slicing. The first cache miss still decodes the full source once. RMS analysis still converts full audio when it is required by local pacing.

Tests use real cache files and verify identical int16 samples, identical MFCC results for an audio slice, no second FFmpeg decode on a hit, invalidation after a source change, and recovery from wrong dtype/shape/length or a truncated file. Rejected mappings are verified closed before atomic replacement, the condition required for replacement on Windows. Native Windows execution is still pending.

### RMS analysis only where consumed

Initial Groq analysis skips RMS silence measurements and reports the audio phase as skipped. The worker's `groq_staged_v1` pacing path retains original intervals and does not consume those measurements. Active-speaker PCM loading remains unchanged.

Independent review found and reproduced a restoration case: a saved Groq project can later be reopened with the local planner. The patch therefore routes pacing through a shared helper that lazily fills missing RMS measurements for a nonempty local plan with pacing enabled. It uses full original media, deduplicates multiple takes, includes alternative cameras, and retains successful or unavailable results for future replans.

Regression coverage includes a real project file save/reopen followed by a local replan, enabling local pacing after analysis, alternative-camera data, failed audio extraction without repeated retries, unchanged source words/selected intervals, and no extraction for an empty or staged plan. The progress indicator started by lazy audio closes on success or pacing failure. Worker/provider responses in orchestration tests are local test doubles; no Groq request is made.

## Verification

Environment: Linux, Node.js 24.22.1, Python 3.12.14, pytest 8.3.5 in a temporary test environment. The bundled active-speaker model used by the existing hash test was fetched at the exact baseline blob and verified before use. No runtime dependencies or weights are changed in the commit.

| Command | Result |
| --- | --- |
| `node --test --test-isolation=none --test-reporter=spec tests/unit/*.test.cjs` | 123 passed, 0 failed |
| `python -m pytest tests/unit -q -ra` | 127 passed, 2 skipped, 0 failed |

The two skipped cases are the existing Windows PowerShell update-payload tests. The JavaScript updater tests required permission to open a temporary local Unix socket; they passed without changing the tests. Focused regressions were first observed failing for the intended reasons and then passing after the implementation.

## Native integration gate

No Resolve timeline, installer, Windows runtime or real-media performance benchmark was executed in this environment. No end-to-end speedup percentage is claimed.

Before packaging a release, run the branch in the Windows/Resolve environment with the same inputs, settings and validated Groq labels as v0.11.7. Compare decision media IDs, original start/end frames, reactions and actions; measure first and repeated runs separately. Check a saved Groq project reopened without Groq and a local run with pacing enabled. Preserve existing timelines and collect phase timings without running a second GPU-heavy application during transcription. This commit is prepared for integration review, not a new installed release.
