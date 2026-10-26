# Local analysis reuse: implementation plan

Approved scope: `../specs/2026-10-26-local-analysis-reuse.md` and the user's request to prepare an isolated integration commit.

1. Preserve an exact snapshot of base `80ee38de59342e78eac7d3f92d95178ee362522e`, record the baseline checks, and coordinate the touched files on PR #19. Adopt the subsequent `219b91dd07344370806ebac29dbb106216b275ee` (v0.11.7) as the integration parent, preserving the camera planner changes; isolate the new camera tests' encoder fixture at the shared instance boundary.
2. Add focused failing regressions for shared semantic initialization, mapped PCM cache hits and skipped unused RMS requests.
3. Implement the shared encoder accessor in `worker/transcript_align.py` and consume it in `worker/staged_dialogue.py`; memory-map validated PCM hits in `worker/local_audio.py`, closing rejected mappings before replacement; gate RMS requests and truthful skipped progress in `plugin/session.js`. A shared pacing entry point lazily fills missing original-source RMS data when a saved project or disabled pacing later switches to local planning, as required by the independent review.
4. Run focused regressions, the product suites and one independent read-only patch review. Fix material findings and record native-runtime verification still pending.
5. Verify the exact changed-file set, publish one commit through GitHub's Git Data API on the isolated branch, verify its contents, and open a draft PR targeting `feat/premontato-workflow`. Do not merge or release.

Transport: plain API worktree (no `.git`), exact baseline blob hashes, non-forced ref update with expected parent. Intermediate snapshots, logs, model downloads and test caches are excluded from the commit.
