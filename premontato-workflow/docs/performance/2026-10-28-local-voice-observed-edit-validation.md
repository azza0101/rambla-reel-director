# Local voice identity and observed editing: validation, 28 October 2026

Status: experimental development on feat/omnicut-grounded-sequence-20261028 / draft PR 35. This work DOES NOT pass the editorial release gate and is not an installer update. The installed Omni-Cut test 0.2.30 remains unchanged. No main merge, cloud inference, mouse automation, production-media edit or Resolve timeline creation occurred in this validation.

## Built

- Optional WeSpeaker ResNet34 voice embeddings from cached 16 kHz PCM, source-local galleries, overlapping-anchor exclusion, independent cross-source profile consensus and explicit unknown results. Actor names are not used as acoustic evidence.
- Positive face/voice enrollment with independent-source consensus. Repeated anchors in one clip cannot outvote several independent sources. Fixed a mean calculation that divided two face matches by three. Listening identity can be checked separately from lip activity; ambiguous multiple-face frames are rejected in this path.
- Observed speech-turn inventory and monotone interval matching. Repeated short comic replies are distinct events, not text duplicates. Whole source utterances are the matching atoms. Semantic negatives and observed content are checked against the spoken version, not a screenplay whitelist.
- Last substantially complete usable performance per field takes precedence over a slightly more literal alternative. This is currently a field/source lock, NOT a solved take-boundary detector inside a long MP4.
- Visual rejection triggers another bounded alignment search rather than discarding every other candidate in that file. A retry limit never promotes an unverified candidate.
- Separate interval audit for missing/reused events, reused source frames, exposed same-field joins, sub-1.5-second shots/reactions and discontinuous record positions. A technical interval pass is NOT a pass of acting/prop continuity, semantic equivalence or editorial quality. The experimental response is explicitly diagnostic_only / release_ready=false.
- Optional worker protocol actions build_observed_excerpt and audit_observed_edit, with voice/enrollment/alignment progress. They do not replace the normal installed panel engine.
- NVDEC validates both source and actual native frame bounds before any seek/window read. A real test hit INVALID INDEX at EOF with preroll; three regressions reproduce the unsafe calls, and the patched real-source rerun completed without that block.

## Actual measurements

Primary source-local audio comparison used real Resolve transcripts and source audio. Raw embedding voting agreed with 32/33 supplied labels in about 3.44 seconds, versus 29/33 for the earlier MFCC probe. These are NOT human truth annotations. The conservative integrated replay accepts 31/33 anchors, agrees with all 31 accepted labels and returns two unknowns. All 202 embedding requests were cache hits; total replay 1.73 seconds, including model startup and validation. Of 68 focused units, 49 receive an identified voice; short/weak speech remains unknown.

Additional voice checks used 12 real clips covering trailer scenes 2/5/6/7 and five clips with another cast. Across 236 supplied anchor labels: 196 identified, 193 agreed, 3 disagreed, 40 unknown. Total measured voice processing was 61.30 seconds in that pass, with a mixture of already cached audio and first-time embeddings. This is not a cold import/transcription/video-analysis benchmark. In this initial pass, single-profile and sparsely labelled clips remained unknown rather than being forced into two speakers. A subsequent experimental open-set gate permits a single well-supported profile only at cosine >=0.70, never merely because its competitor disappeared after overlap exclusion; this threshold is not a calibrated identity probability. A further 14-clip scene-6 run exercised voice extraction across 1,526 timed source units, overlapping some of the first cases.

Three scene-level automatic experiments were run on scenes 5, 6 and 7. The initial longest-word-count reference selection was rejected: it can prefer dialogue contaminated with pickups/direction. The scene-6 comparison was then frozen to the SAME 34-event excerpt used by the preceding preview, not selected by a hand-authored cut plan. Current diagnostic result: all 34 event IDs retained, no reused source ranges or exposed same-field joins, but 15 speaker-coverage turns unresolved and zero verified reaction overlays. It does NOT improve on the earlier preferred edit. The 53.8-second MP4 has 1,345 frames, 640x360 H.264 and mono AAC; render 12.63 seconds and full decode passed. Visual contact-sheet inspection confirms that the middle still holds the woman's shot too long. Do not publish this planner as a quality fix.

A separate Gemma local-only performance-selection test returned in 9.57 seconds. It marked runs as complete despite unexplained gaps and technical speech inside them. It was rejected and not used to alter the edit. An ID-valid JSON response alone is not sufficient editorial validation.

## Automatic and native verification

- Python: tools/run_python_tests.py, 318 passed, including plain packaging contracts.
- JavaScript: bundled Node, node --test --test-isolation=none tests/unit/*.test.cjs, 262 passed, no skips.
- Resolve API readback: Studio 21.1.0.17, project test-mcp, 25 fps; current timeline and count of 50 timelines unchanged. No synthetic project or new timeline was created: the editorial gate failed before native materialization. This is explicitly NOT a passed native edit test.
- Private footage, transcripts, audio, embeddings, rendered MP4s and API credentials are excluded from Git. Models/dependencies were isolated on Z. No global dependency or other product was changed.

## Model provenance and distribution gate

Model: https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/wespeaker_en_voxceleb_resnet34.onnx

SHA256: 5ef208a9da1453335308a6b6f4e6dfbd7e183a38b604de0a57664f45d257fe94 (26,534,365 bytes). WeSpeaker documents the pretrained model as CC-BY-4.0: https://github.com/wenet-e2e/wespeaker/blob/master/docs/pretrained.md . Kaldi-native-fbank code is Apache-2.0. Isolated wheel tested: kaldi_native_fbank 1.22.4, CPython 3.13 Windows x64; SHA256 638586ce9661cf2b16a5cf35c2900f38c307592be54ab9da266b8816eeeeb5fa. No model or dependency is bundled/distributed by this draft. Preserve model attribution and dependency notices and recheck distribution conditions before packaging.

Preprocessing: 16 kHz raw PCM amplitude, 80-bin Kaldi fbank, 25 ms windows/10 ms shift, hamming, dither zero, snip edges, mean normalization, normalized 256-dimensional output; CPU inference with two threads. Cache identity includes source path/size/mtime, frame interval, fps, model SHA and preprocessing version.

## Remaining gate

Before this can replace the installed editor: robust scene/performance boundaries must stop script matches from bouncing between scenes inside the same take; canonical performance selection must use complete acting context instead of word count; short turns need better acoustically grounded evidence; reactions must be found and verified in actual source material; object handling/gesture completion needs visual evidence. A label, a successful render or a clean interval audit cannot stand in for those checks. Keep diagnostic generation available, but do not label it a finished edit.

Final cross-scene replay of the latest code: scene 5 and scene 7 were rerun without manual cuts. Scene 5: 20 events / 1 cuts / 3.59 s; 20 unresolved speaker turns; 0 verified reactions; short shots []. Scene 7: 38 events / 11 cuts / 37.59 s; 15 unresolved speaker turns; 0 verified reactions; short shots [5, 7]. Neither result passes the editorial gate.

Warm replay after the single-profile gate: scene 5 2.48 s, 20 unresolved turns. scene 7 10.92 s, 15 unresolved turns. This does not change the failed editorial release gate.
