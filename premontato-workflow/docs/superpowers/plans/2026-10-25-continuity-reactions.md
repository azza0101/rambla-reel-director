# Reactions and scene continuity implementation plan

> Execution: superpowers:executing-plans, directly in this session; no agents.

**Goal:** preserve listening reactions, action transitions and continuous angles in automatic local edits.
**Architecture:** keep dialogue matching unchanged. Finalize pacing with source continuity and script-action coverage; attach a validated listening-video overlay before a tension resolution, retaining the preceding dialogue audio. Resolve assembles video and audio from separate verified source ranges and coalesces contiguous matching AV clips.
**Tech stack:** existing Python/OpenCV/Light-ASD, Node and Resolve SDK. No services or new dependencies.
**Spec:** user instructions in this conversation; VIDEO_COLICHE profile.

## Constraints and review focus
- No jump within the same source angle: preserve source continuity or fail explicitly when backwards/incompatible. Do not replay matched speech.
- Preserve motion between adjacent matched lines from a shared wide take, plus a bounded trailing action. Do not fabricate action recognition; flag unlocated coverage.
- Reaction coverage needs automatic answer-speaker evidence and face continuity into the actual listening preroll, or existing manual proof. Uncertain evidence must remain unavailable.
- Listening video retains the original preceding line audio, exact equal lengths, mono output. No audio from a different performance under lips speaking.
- Manual decisions remain authoritative; unsafe assembly must not create a misleading timeline.

### 1. Source and action continuity
- [x] Write failing pacing tests for internal silence jumps, same-take gaps and action bridge coverage; include backward order rejection.
- [x] Implement focused worker continuity helpers and call from pace_plan; preserve all dialogue bounds and idempotency.
- [x] Verify Python suite and real saved plan: no discontinuous adjacent same-source cuts; exit/approach present.

### 2. Listening reaction
- [x] Write tests for automatic reaction eligibility and uncertain face evidence, with model inference mocked only at the inference boundary.
- [x] Add bbox evidence/short face continuity check to ASD, and generate listening overlay at tension-resolution when an eligible tight answer take exists. Retain existing silent-reaction behavior as fallback.
- [x] Verify actual Fabrizio close take, preroll stills and unchanged girl audio.

### 3. Resolve assembly and delivery
- [x] Write failing JS tests for overlay video/audio mapping, invalid durations, contiguous coalescing and project persistence.
- [x] Implement validated overlay/action metadata in existing security/session/adapter modules; keep max3 tracks, mono and source attributes.
- [x] Run suites, inspect new versioned test timeline in actual Resolve, compare sources/readback and preserve existing timeline.
- [x] Build/validate and publish dedicated Premontato release from PR19 without merge/latest.

Execution ledger: 99 Python tests and 96 JavaScript tests passed; 9 packaging contracts passed. Actual Resolve readback verified the listening video with preceding girl audio, mono tracks and continuous source angles. Renderer checked reaction enabled state and disable/re-enable persistence without page errors. Source action coverage is bounded by dialogue anchors, not claimed as semantic action recognition. Final take tail is deliberately retained for manual timing review. Packaging/publication verification recorded in VALIDATION.md.
