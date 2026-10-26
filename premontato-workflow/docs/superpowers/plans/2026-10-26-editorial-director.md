# Editorial Director Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline. User explicitly requests autonomous implementation and no additional agents.

**Goal:** Interpret screenplay narrative events once through Groq, then select grounded listening inserts locally, with readable returns to the speaker and continuous underlying audio.
**Architecture:** Independent cached text-only editorial pass after utterance classification. Validated beat IDs, cast IDs and verbatim anchors; no model timecodes or source ranges. Local event scheduling verifies actual listening coverage and maintains hard constraints.
**Tech Stack:** Existing Node/Electron Groq client, Python semantic encoder/Light-ASD, Resolve native SDK. No upstream code copied.
**Spec:** docs/styles/VIDEO_COLICHE.md and approved architecture in conversation.

## Global Constraints
- No Codex inference during plugin execution; one bounded editorial Groq request per changed scene, cached by script/spoken text/style.
- V2/A2 complete base, V3 video-only reactions; hard floor 1.5 seconds. Preserve source mappings and existing project timelines.
- Events are suggestions. Missing/malformed data cannot create invented media, wrong listeners or unverified footage.
- No source-specific names, ranges or scene times hardcoded. Master optional, single-camera continuity preserved.

## Review Focus
- Model invents a beat/cast/anchor: reject and show explicit fallback.
- Listener is the affected person rather than the person called by name: prompt and evidence distinguish them.
- Mid-battuta insert needs a readable return; short line skips insert unless explicitly justified ending hold.
- Discarded ASR unit can be crew: semantic lookup requires nearby narrative anchors and inactive-face proof, excludes cues.
- Cached editorial data must invalidate on changed rules; legacy cache and saved plans remain loadable.

### Task 1: Grounded editorial contract and Groq cache
Files runtime/premontato/editorial_client.js, groq_client.js, tests/unit/editorial-client.test.cjs.
- [x] Test schema rejection, one call/cache hit, change invalidation and malformed response behavior.
- [x] Implement planEditorial(prepared, classifications, directions, onProgress) -> {events,summary,warnings}; bounded text, no paths/video.
- [x] Run Node tests.

### Task 2: Narrative listening placement and middle overlays
Files worker/editorial_director.py, staged_dialogue.py, listening_reaction.py, plugin/ipc_security.js, tests/unit/test_editorial_director.py, resolve-adapter.test.cjs.
- [x] Test effect-person/anchor resolution, readable return, explicit ending hold, unknown coverage abstention, no dependency on names.
- [x] Implement event-to-word scheduling and semantically grounded off-camera candidate recovery using existing vectors and local ASD.
- [x] Allow overlay end before parent end; adapter already supports independent V3 windows.
- [x] Enforce minimum duration and visible sequence continuity at overlay entry/exit.

### Task 3: Plugin wiring, verification, and rollout
Files plugin/session.js, renderer.js, index.html, manifest.xml, package.json; docs/releases.
- [x] Wire editorial phase/progress, explicit fallback and review reasons; keep retry cancellation and cached data.
- [x] Full JS/Python suites and actual scene test with real Groq event output; inspect all candidate exclusions, no manually authored plan.
- [ ] Native timeline test, publish dedicated release from PR19 commit without merge/latest, update installed panel and rerun.

### Reference-video handoff (parallel question)
- [x] Supply provider-neutral JSON schema + Gemini prompt, separate observed edits from inferred rules and cite evidence timestamps/confidence.
- [x] Explain external video analysis avoids Codex video costs; JSON review still uses context and structured output is not semantic certainty.

## Execution ledger — 2026-10-26
- Inline execution; no subagents per author instruction. Self-review of schema validation, range safety, cache invalidation, overlay ownership and fallback.
- Existing branch feat/premontato-workflow reused; no main merge or cross-product changes.
- Grounded editorial request and dedicated cache implemented. Two real trial requests during prompt refinement; final v3 response reused for all subsequent local tests. No human-authored cut plan or source-specific ranges.
- Reference-video JSON saved locally, unverified as video evidence. Runtime uses an explicit vetted preference profile, not the raw Gemini observations or estimated timings.
- Local reliable listening overlays remain available as baseline; semantic events augment and constrain matching event beats. Removing baseline coverage merely because an LLM omits a sentence was rejected as a regression.
- Tested readable internal windows, intentional tail exceptions, missing-anchor abstention, crew exclusions, existing listener and revision toggle persistence.
- Native adapter trial v0.11.10 created 19 full V2/A2 base clips and three V3-only inserts (55/55/48 frames), all audio mono; source timeline unchanged.
- Four real narrative intentions: one already satisfied by verified base listener, two insufficient readable placement/anchor, Sandro turn has no verified listener candidate. No assertion of visual emotion.
- OFF immediately closed automation runtime. Remaining work runs through files, CLI and Resolve API; no UI/input sessions are permitted until explicit authorization.
- Publication 0.11.11 supersedes locally installed 0.11.10 trial so the updater can discover an actual newer release.

## Final verified rollout
- Source/tag: a136cb9ca1d3937d2215cc6f977b22407346fb55 / premontato-v0.11.11.
- Fresh publication-checkout suites: 125 JS, 137 Python, exit 0.
- Final native timeline: PREMONTATO v0.11.11 - REGIA VIDEO COLICHE 094052; 1618 frames, 19 V2/A2 base items, 3 V3 inserts (55/55/48 frames), all audio mono, previous timeline unchanged. No human-authored montage.
- Separate single-camera regression: 19 moments, 12 dialogue beats, 1 action bridge, no missing dialogue or reaction inserts; continuous mode retained.
- ZIP validated against source and updater ValidateOnly (4075 files); installer embedded ZIP inspected (4124 entries, package 0.11.11), entrypoint not run. Official Resolve native SDK excluded from distribution.
- Real published release discovered through product updater from version 0.11.10, downloaded 181770916 bytes, SHA256 d9510d43df1ef7a88eebf90487335aa7457b932ff368f02eb2a7d5b8e8e0990f; phases check/manifest/download/verify; current 0.11.11 returns current.
- No new UI session after OFF. The open panel was a local 0.11.10 trial; final 0.11.11 is published and ready through Aggiorna. In-place UI install/restart of the final release remains untested; no claim that the running panel has already loaded it.
