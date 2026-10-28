# Editorial prototype verification status — NOT RELEASE READY

28 October 2026. This branch intentionally separates the verified optional GPU reader commit from the experimental editorial changes. Do not package these editorial changes as a successful quality fix.

The real-source scene-planning regression failed on four dialogue scenes in the latest run: no continuous path could satisfy all content/field constraints. The run returned only six decisions from the remaining jobs, including the catalogued silent scene. This is worse coverage than the installed baseline and must not replace it.

Findings:
- Shot-by-shot lexical ranking can pull older fragments into an otherwise valid performance.
- Active-speaker visibility does not by itself prove agreement with the expected screenplay character.
- Resolve speaker_name metadata existed in the original transcript but was dropped both by scene routing and utterance preparation. The prototype preserves it with source-local confidence checks. A segment containing multiple short turns is not certified as one speaker per utterance.
- Adjacent source files can be equivalent fields; file ID is insufficient to prevent jump cuts.
- A silent catalogued scene was omitted because the former path required speech. The new visual-scene path includes its actual source extent and reports missing dialogue separately; it does not claim action-level timing intelligence.
- A short generic fragment was sometimes accepted as complete coverage of a distinctive screenplay line. Stronger filters expose this upstream classification problem, rather than solving scene construction.

Current automated verification: 260 Python tests pass. The JavaScript suite also passes all 262 tests. These numbers do not establish editorial quality. Real-source tests used actual saved transcripts/script and current source media, with the configured local model; no handcrafted cut plan or hardcoded production ranges were used.

Resolve 21.1.0.17 was inspected read-only. No new native timeline was created and no installed plugin was changed by this prototype. Native application of the full revision was deliberately not attempted after scene-plan verification failed. No new release/installer was published.

Next architectural task: select a coherent, substantially complete performance per field/scene, build an audio/text continuity spine before camera coverage, then perform scene-local text/speaker/continuity verification. Do not treat a rendered proxy preview alone as proof of editorial quality. Preserve the original source evidence and allow earlier performances only for genuinely missing/unusable content. Any recovery must be covered by real-source regression tests before it reaches the updater.

## Follow-up: scene 6 experiment
The real-source routing probe exposed an ordering bug: catalog vetoes could clear a previously assigned route after nearby context had been applied. A new snapshot-based pass restores only unassigned interior speech between accepted anchors agreeing on the same scene, within 20 seconds. It does not cross a known competing scene or propagate newly restored anchors. Three focused tests and the real transcript probe verify the recovery of the proposal exchange that was previously missing.

A separate private locked-performance experiment was run without multicam synchronization or a human cut plan. Single-utterance ASD evidence classified the observed male/female fields more reliably than long mixed-speaker windows. However, the experiment still reports four missing screenplay dialogue beats and two same-field discontinuities. Its 360p preview is a diagnostic draft, not a successful edit or an installed update. A variant allowing broader source gaps admitted repetitions and was rejected. Do not distribute either editorial planner as production-ready.

Fresh checks: 259 Python tests under test_*.py and 262 JavaScript tests passed. These counts use the stated discovery pattern and do not supersede the failed editorial quality gate. Resolve was not mutated; the preview was rendered directly from source media with local FFmpeg, H.264 video and mono AAC.

## Transcript-first correction after preview feedback
The preview still selected content by screenplay beat, despite locking performances. This was not a transcript-first editor and cannot preserve improvised comic structure reliably. The observed_story prototype now inventories every timed utterance inside a performance boundary without screenplay labels, text deduplication or automatic deletions. Cleanup is explicitly pending; this is not a new finished edit.

Four focused tests preserve identical answers to different questions, off-script corrections, and whole spoken units. Real-source inventory checks retained 57 utterances in one focused performance and 68 in another, including repeated prosciutto replies; the latter contains the culatello correction. The variants differ and must not be combined merely to fill screenplay beats. Object handling and gesture completion have not been verified from these text tests. No new preview or installed update is claimed by this change.

## Mandatory cover rule and observed-dialogue excerpt
Added a tested experimental jump_cover validator: a cutaway must be verified as the other person listening, last at least ceil(1.5 * fps) frames, cross the actual edit point, remain inside the sequence and leave base audio unchanged. Three focused tests cover valid joins, short/unverified coverage and incorrectly positioned cutaways. The helper is not yet wired into the installed plugin.

The new private transcript-first experiment retains the initial 34 source utterance events of the comic exchange without screenplay filtering. It is an excerpt ending before technical interruption, not the full scene. Alternative fields are queried by spoken-text/context similarity and checked with local ASD plus SFace; multicam synchronization is not assumed. Where a discontinuity cannot receive verified listening coverage, the experiment keeps continuous original source material instead. This can leave speaker close-ups unresolved and is not a passed editorial quality gate. It does not claim successful recognition of hand-held objects or gestures.

Fresh Python discovery test_*.py: 266 tests passed. The low-resolution MP4 is private test output; no Resolve timelines were changed and no installer/release was published.
