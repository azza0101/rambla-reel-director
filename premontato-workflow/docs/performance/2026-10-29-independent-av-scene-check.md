# Independent audio/video experiment

The observed editor now accepts optional `editorial_mode: independent_av`.
Its existing default remains unchanged. This worker experiment is not installed
in the normal panel or published as an automatic update.

The compiler retains the selected dialogue performance as a separate audio
spine, creates a video spine, and inserts only evidence-backed listener shots.
Optional reactions last at least 1.5 seconds, have a known different visible
identity and matching speaking identity, and leave at least half a second of
the verified speaker before and after the insert. An unavailable reaction is
omitted rather than guessed. Forced jump-cover handling remains a separate
existing mechanism; this change does not claim to solve every uncovered join.

The result preserves observed turn boundaries and reports unresolved camera
coverage as check requests with original event IDs and timing. It separately
reports speaker coverage, content equivalence, and action verification. Even a
plan with complete speaker coverage is not automatically editorially approved.
No model is trained by this change; no cloud calls or new dependencies occur.

`tools/render_observed_av.py` renders audio and video independently, mutes video
insert audio, validates source existence and track coverage, and removes its
temporary files. The caller supplies an existing FFmpeg executable. Temporary
files live beside the requested output, allowing previews entirely on Z:.

## Actual replay

The same frozen 34-event excerpt and same 14 independent recordings used for
the previous Nemotron experiment were replayed. The model/runtime/cache
configuration is unchanged. Human-reference timecodes or camera selections are
not inputs to the new rule.

The replay produced 11 selected dialogue segments, 19 video segments and four
verified listener inserts of 40 frames each at 25 fps (1.6 seconds). The actual
640x360 H.264/AAC mono MP4 has 1,339 frames and lasts 53.56 seconds. Decoding
previous and new preview audio to 16 kHz mono float PCM produced identical
857,088 samples, zero mean absolute difference, and correlation effectively 1.
This verifies unchanged rendered audio; it does not certify the underlying
dialogue cleanup or acting choices.

The long unresolved shot remains. Ten unresolved voice turns are grouped into
three unresolved selected-video spans. This experiment improves the track
representation and listening coverage but does not yet solve the alternative
take equivalence and action-continuity problem. A source-sampled contact sheet
was inspected, not the complete movie with continuous audio playback.

Increasing visual candidate search from three to twelve rounds found no extra
usable shots. That change was reverted. One replay took 62.73 seconds, another
warm-cache replay 43.25 seconds; these runs differ in cache warmth/search budget
and are not a controlled speed comparison. Timings exclude transcription and
cold voice/model extraction. No native Resolve apply was attempted.

## Model/tool decision

No additional model download is justified just to split audio and video. A
local vision-language second opinion could be useful for a short unresolved
action sequence and its transcript: check shown objects, question/response
order and whether a proposed insert contradicts the action. It must use supplied
candidate IDs and source intervals, allow abstention, and never invent timing
or treat a still as acoustic evidence of who speaks. Such a check is not yet
implemented or benchmarked here. Existing Qwen vision probes depend on a
separate ComfyUI environment; this task does not import or modify that stack.

## Checks

Five new compiler tests cover audio preservation, return to the speaker,
invalid/short listener inserts, unresolved status and invalid audio clock.
The new tests were run before implementation and failed because the module
was absent. Full validation: 362 Python tests in the plugin runtime and 262
JavaScript tests pass. An initial system-Python run failed two PDF tests because
that separate environment lacks pypdf; no global installation was made.

This is a testable first slice, not all requested editorial rules integrated.
Automatic action understanding, better whole-take selection and local VLM
second checks remain outstanding. No stable release or quality parity with the
human reference is claimed.

## Seven-second spoken-shot review rule

The compiler now queues a local vision-language review when a spoken visual
hold exceeds seven seconds. Adjacent same-source/same-field segments count as
one hold even if their source trims differ. Exactly seven seconds does not
trigger. The reviewer may keep the shot, suggest an existing alternative, or
abstain; a timer never forces a cut. Requests carry source intervals, dialogue
IDs, available verified alternatives and a stable fingerprint for future cache
use. The worker enriches requests with turn context and candidate IDs.

Actual replay of the saved scene plan queued exactly the defective hold at
18.48 seconds, lasting 16.16 seconds. Three new tests cover the trigger,
boundary and fragmented-hold cases; the Python suite now has 365 tests.
The Qwen adapter has not been connected: requests remain `pending_model`,
which is explicitly not a successful visual check. No model was run, no
new preview cut was applied, and no normal-panel update is claimed here.
