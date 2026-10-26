# Active-speaker work reuse and profiling

Integration parent: `a69e7aa8886d61f111487ecb2c0c5da876071fdc` (v0.11.9).
Branch: `perf/premontato-speaker-samples-20261026`. Only production change: `worker/active_speaker.py`. Independent of PR #20; neither patch is an installed release.

## What changes

- Coordinate smoothing uses one padded array and vectorized 13-frame medians. Face crops use the requested image region, adding only the required constant border; internal crops share the source frame. Model-input pixels match the old full-frame-padding implementation, including fractional/offscreen coordinates and Python slice edge cases.
- A separate persistent sample cache stores the unrounded averaged float32 frame scores and track geometry. Different requested intervals can reuse the same decoded sample while retaining their own score slice, rounding and speaking classification. The previous v3 interval cache remains usable.
- `elapsed_seconds` is current call latency. `seconds` retains its historical cache semantics. `stage_seconds` separates decode, audio/features, face detection, tracking/crops and ONNX inference. `work` counts actual decodes, detected frames, tracked faces and inference calls; hits report zero new work. These fields are available in the worker result/benchmark; this patch does not change panel labels.
- `tools/benchmark_active_speaker.py` profiles one local source in a private temporary cache, without clearing or reading the user's production cache. It distinguishes cold audio+ASD, exact-interval reuse, equivalent-window reuse, and warm PCM with a cold ASD cache.

No model, provider, thread count, 25 fps sampling, detector settings, inference ensemble, classification threshold or editorial rule changes. Original source frames and word times remain authoritative. No external model/API call is added.

## Verification

Focused tests were observed failing before implementation and passing afterward. They cover exact crop/resize and smoothing equivalence; different speaking results on the same sample; persistence across analyzer instances; legacy v3 hits; malformed/nonfinite sample data; invalidation after source/window changes; inference failure followed by retry; rounded-empty and no-face samples; and truthful work counters on cache hits.

Independent review additionally compared 392 crop cases with real OpenCV, including read-only and nonuniform frames; all nonempty model-input crops matched exactly. Final review has no open findings.

Final checks on the v0.11.9 integration base:

- `node --test --test-isolation=none --test-reporter=spec tests/unit/*.test.cjs`: **117 passed**, no failures.
- `python -m pytest tests/unit -q -ra`: **147 passed, 2 skipped**, no failures. The skips are the existing Windows PowerShell update-payload cases.

Environment: Linux, Python 3.12.14, NumPy 2.3.5, OpenCV 4.11.0.86, ONNX Runtime 1.23.2. The OpenCV/ORT versions match the pinned product packages; the Linux test NumPy differs from the Windows lock. Bundled model hashes were verified. Runtime dependencies and weights are unchanged in the commit.

## Bounded comparison with the real shipped ONNX model

Fixture: two seconds of generated 960x540 video and a generated tone. Real YuNet executes, then its returned boxes are replaced with one fixed synthetic track so that the complete crop and Light-ASD inference path is exercised. This is a performance/equivalence fixture, not a speaking-accuracy test.

Baseline and patched paths use the actual shipped Light-ASD model on CPU with two inference threads. PCM/model are warm; each first computation has a separate empty ASD cache. Three repetitions per case. All recorded model-input hashes and final evidence dictionaries match the baseline exactly.

| Scenario | Baseline median | Patched median | ONNX calls, baseline / patched |
| --- | ---: | ---: | ---: |
| First ASD computation with warm PCM/model | 0.663075 s | 0.675282 s | 3 / 3 |
| Different interval, same sample | 0.618119 s | 0.001144 s | 3 / 0 |
| Exact interval repeat | 0.000147 s | 0.000097 s | 0 / 0 |

**There is no demonstrated first-pass speed improvement in this small experiment.** The patched first computation was slightly slower. The supported gain is eliminating repeated computation for equivalent windows; ordinary distinct windows still require inference, and exact interval repeats were already cached. No total-project speedup is inferred.

The patched first-computation measurements attributed approximately 0.13–0.16 s to decoding, 0.15–0.16 s to detection, 0.009–0.010 s to tracking/crops and 0.34–0.45 s to inference. Those figures describe this synthetic Linux fixture, not the user's footage or Windows machine.

The standalone benchmark also completed against the generated video with the actual detector output (no detected face), correctly reporting zero model calls and distinguishing all four cache scenarios.

## Native follow-up

From a checkout with the product's local runtime and models, run a representative timed source interval, for example:

```text
runtime\python.exe tools\benchmark_active_speaker.py --source "D:\riprese\clip.mp4" --fps 25 --duration-frames 5000 --start 100 --end 150
```

Replace the example metadata and interval with the actual source values. This command can decode the source audio once, so use representative media rather than assuming every cost is limited to two seconds. Output is JSON on stdout and contains local timings and counters, not footage. It requires no Groq or Codex call.

To reduce first-pass latency further, use these native timings to decide whether to tune CPU inference, package a compatible optional CUDA provider, or optimize decoding/detection. GPU support is not enabled by this patch. Any provider/thread/model change needs a separate comparison of both performance and resulting evidence. Native Windows/Resolve, actual file locking, and real-footage editorial acceptance remain unverified here. No merge, installer or release is performed.
