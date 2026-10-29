# Local Nemotron hybrid evidence — 29 October 2026

## Implemented and kept separate

The new branch adds a native Nemotron adapter and a conservative second opinion after WeSpeaker identities have been reconciled across independent recordings. Worker action `analyze_voice_evidence` can run without Resolve, Codex, MCP, a screenplay, or cloud services. `build_observed_excerpt` accepts `voice_mode: hybrid`; its previous default remains `wespeaker`. The installed panel and stable update channel are unchanged. This is functional experimental worker code, not a completed replacement for the installed editor.

Anonymous diarization clusters are recording-local. At least two non-overlapping acoustic observations must agree before an unknown voice can borrow an identity. Query and overlapping anchors are excluded. Primary assignments survive disagreements; the disagreement is logged. Uncertain overlaps and fragments under 200 ms remain unknown. Secondary-only assignments and contradictory evidence cannot enrol face identities. Original text, IDs and source frames remain unchanged.

The adapter checks the pinned 107,012,128-byte model, uses the official portable NeMo-Speech.cpp runtime, reuses 16 kHz mono PCM and writes validated success-only JSON cache. GPU start/exit, timeout, JSON and segment-validation failures can receive one CPU attempt; fallback provenance is explicit. Temporary WAVs are removed. No download occurs during analysis. The bounded `v3-offline` preset works on long files; unbounded `--offline` full attention rejected the 424.8-second recording in the earlier spike.

Model: [NVIDIA Nemotron-3-Diarization](https://huggingface.co/nvidia/Nemotron-3-Diarization/tree/f667ed73aee57d40cc39428eb768b4fd87a0a29e), Q8_0 SHA-256 `08456d9e22cd9a323c0364d98375f3746d6e68507ebb705cd46438c534c7a3a1`. Runtime: [official v0.2.0](https://github.com/NVIDIA/NeMo-Speech.cpp/releases/tag/v0.2.0). The benchmark keeps model/runtime/data on Z:. Existing private PCM/voice/visual caches are reused in their existing location. No weights, media, transcripts, embeddings, native binaries or private logs are committed.

## Actual inference and cache

Five distinct real recordings, 1,122.24 seconds total, include two casts. The extra short excerpt is part of one of those recordings, not additional footage. GPU and CPU native inference were both run, not mocked. GPU failure branches are covered by controlled test doubles; no live GPU fault was induced.

- On the 424.8-second clip, the earlier WAV-only native benchmark measured 1.43 s GPU / 11.65 s CPU. The new adapter measured 2.07 s GPU, including temporary-WAV/cache work from already extracted PCM.
- On a different 98.4-second clip, the actual new CPU adapter measured 2.889 s; exact cache replay took 0.0065 s.
- Reusing all 14 diarization caches in the observed-scene test took about 0.164 s total in the adapter. Voice fusion and visual/semantic matching have additional costs.
- These timings exclude initial Resolve transcription, original-video audio extraction and cold WeSpeaker extraction. They are not full-day workflow or end-to-end editing times.

## Identity evaluation

This is agreement with supplied Resolve labels, not human-annotated diarization error rate, face accuracy or editorial acceptance. No reference labels are supplied to the fusion decision rule: it calibrates from primary acoustic predictions. The scored anchors have independent primary embedding evidence. A fifth clip without such anchors is timed and produces anonymous turns, but is not assigned an invented accuracy score.

| 104 scored anchors | Primary WeSpeaker | Worker hybrid |
|---|---:|---:|
| Agreement with supplied Resolve labels | 81 | 85 |
| Disagreement | 1 | 1 |
| Unknown | 22 | 18 |

The earlier throwaway calibration experiment reported 86 agreements. That used supplied Resolve anchors for calibration; this implementation uses stricter independent primary predictions, overlap deduplication and minimum-duration guards. The production rule is not weakened to reproduce the larger number.

On the frozen difficult 68 utterances, identified voices increased from 49 to 54. This is additional coverage, not proof that each newly identified short reply is correct.

## Observed edit replay and actual MP4

Both modes receive the same 14 independent source recordings and the same frozen 34-event excerpt. No hand-authored camera plan, actor name or filename exception is used. Inputs include precomputed primary voice observations and existing transcript/shot data; the reference excerpt is a fixed evaluation fixture, not an automatic full-scene selection algorithm.

| Result | Previous mode | Hybrid |
|---|---:|---:|
| Original observed events retained | 34 | 34 |
| Voice turns | 26 | 22 |
| Cuts | 9 | 11 |
| Turns without verified speaker coverage | 15 | 10 |
| Verified reaction inserts | 0 | 0 |

The two face identities were already independently enrolled; this change does not demonstrate a new general face-enrolment solution. At the final hybrid replay, seven unresolved turns have unknown voices and three have a known voice without a verified candidate shot. Same-field interval checks, source reuse, missing/duplicate event-ID checks and minimum shot duration pass. These checks do not certify alternate-take content equivalence, acting/prop continuity or full speaker visibility.

The rendered diagnostic MP4 is 640x360 H.264, 25 fps, 1,339 video frames / 53.56 s, mono AAC, 5,372,818 bytes. FFprobe output and contact sheet were inspected; the render still matches the final source-interval signature. It visibly retains a long stretch on the woman, so this is an improvement with unresolved defects, not a human-quality edit or stable-release approval. No native Resolve apply was attempted in this slice; existing projects/timelines/settings were not modified.

## Reproduce without an agent

`tools/voice_identity_benchmark.py` retains its original primary-only CLI and accepts optional `--diarization-runtime`, `--diarization-model`, `--diarization-device cpu|cuda|cuda:0`, `--diarization-cache`. `--private-output` writes the inspectable local result. Use a private JSON fixture with `source`, `units` and optional `focus_units`.

The worker discovers a bundled native executable/model or these local configuration variables: `PREMONTATO_DIARIZATION_RUNTIME`, `PREMONTATO_DIARIZATION_MODEL`, `PREMONTATO_DIARIZATION_DEVICE`, optional `PREMONTATO_DIARIZATION_CPU_RUNTIME` and `PREMONTATO_DIARIZATION_CACHE_DIR`. WeSpeaker uses its existing model/dependency configuration. Missing secondary files preserve primary results and emit an explicit unavailable/failed status. Assets are not bundled into a stable installer by this change.

## Upstream research and applicability

- [Ghost Editor take selection](https://github.com/kurbaitaev/ghost-editor/blob/8b9a3c5f9fd2ced7458c26c773351909412d894c/references/take-selection.md) favours coherent spoken runs and later fluent takes; its [skill](https://github.com/kurbaitaev/ghost-editor/blob/8b9a3c5f9fd2ced7458c26c773351909412d894c/SKILL.md) adds cut/beat contact sheets and post-render checks. These principles fit our performance locks and diagnostic previews. Its talking-head script reconstruction, zoom-based splice hiding and Gemini-assisted checks should not become our dialogue-comedy defaults.
- [FFmpeg Skill](https://github.com/kajisho5/ffmpeg-skill/tree/1ae1bdf1ca0adbb1606fbca493948b1bbb2f83ff), MIT, supplies local proxy, plan, progress, probing and output-check tools. It is the most directly reusable technical foundation of the three. A technically valid movie can still have the wrong speaker, wrong take or missing gag; those tests are separate.
- [OpenMontage agent contract](https://github.com/calesthio/OpenMontage/blob/195eab24478dc9363326aec437aefc3701635ddf/AGENT_GUIDE.md), AGPL-3.0, separates scene artifacts, stage checkpoints and review criteria. Its creative reasoning is performed by the driving agent. Studying this does not provide a trained autonomous local comedy editor. No OpenMontage code is embedded here.

These projects were read, not installed or used to generate this edit. This change copies no upstream implementation. For a plugin without coding-agent credits, useful editorial principles must become explicit local rules/model inputs and measured checks. Adding their Markdown skills alone is insufficient.

## Validation and delivery limits

357 Python tests and 262 JavaScript tests pass. The new tests were observed failing before implementation, including the review regression where valid JSON with invalid CUDA segment values failed to retry CPU. One focused independent code review found that issue; it is fixed with a RED-to-GREEN regression. Default editor compatibility is preserved. No stable release, automatic updater rollout, live Resolve apply or full-film acceptance is claimed.
