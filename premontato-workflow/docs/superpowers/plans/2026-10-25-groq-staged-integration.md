# Groq staged dialogue integration

Goal: rerun the approved scene workflow from the installed Resolve panel without agent-provided labels or source ranges.
Architecture: worker prepares exact timed utterances; Groq labels each utterance against dynamically numbered script beats and cast; local worker selects complete coverage, verifies visibility and continuity, and builds actions/reactions. No reference edit or test data ships.
Execution: inline, as requested by user; no subagents.

- [x] Add grounded-unit and classifier/cache validation tests; run red.
- [x] Implement worker/staged_dialogue.py, runtime/premontato/groq_client.js and protected local key setup. Only whitelisted textual script/utterances leave the PC.
- [x] Integrate Session build/pacing, per-moment review IDs, progress, cancellation and persisted provenance. Legacy local mode remains explicit if no Groq key.
- [x] Run JS/Python suites and installed-runtime cold/warm tests with real Resolve data; fail on missing IDs/dialogue or unavailable master.
- [ ] Build 0.11.0 from verified branch commit, publish dedicated non-latest release without merging; invoke the real updater.
- [ ] Run installed panel through Analyze and Create Timeline without editing data or source choices, verify version, source ranges, track types, repeated-run consistency, and save the project.

Constraints: only premontato-workflow; no credentials/script/footage/caches in release; no billing activation; preserve original timelines and source attributes.
Review focus: aliases/order changes; renamed cast; same-file restarts; invalid/truncated model JSON; API quota/timeouts/cancel; multiple decisions per script beat; fallback must be visible; first analysis cannot rely on prototype labels.
