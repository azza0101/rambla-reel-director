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

Current automated verification: 260 Python tests pass. The JavaScript suite has 262 tests; rerun it before publication. These numbers do not establish editorial quality. Real-source tests used actual saved transcripts/script and current source media, with the configured local model; no handcrafted cut plan or hardcoded production ranges were used.

Resolve 21.1.0.17 was inspected read-only. No new native timeline was created and no installed plugin was changed by this prototype. Native application of the full revision was deliberately not attempted after scene-plan verification failed. No new release/installer was published.

Next architectural task: select a coherent, substantially complete performance per field/scene, build an audio/text continuity spine before camera coverage, then perform scene-local text/speaker/continuity verification. Do not treat a rendered proxy preview alone as proof of editorial quality. Preserve the original source evidence and allow earlier performances only for genuinely missing/unusable content. Any recovery must be covered by real-source regression tests before it reaches the updater.
