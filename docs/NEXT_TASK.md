# Next Task — Finish Professional Curation UI Redesign

Current phase: **implementation authorized for the approved Professional Curation UI Redesign**.

Authoritative approval/spec/plan:

- `docs/approvals/2026-09-15-curation-ui-professional-redesign-plan-approved.md`
- `docs/superpowers/specs/2026-09-15-curation-ui-professional-redesign.md`
- `docs/superpowers/plans/2026-09-15-curation-ui-professional-redesign.md`

Implementation branch:

`feat/curation-ui-v1`

The earlier debug-style Curation UI contract and the older Editorial Intelligence + StyleDNA execution instructions are superseded wherever they conflict with this file and the approved redesign plan.

## Required next action

Resume from the **existing local working state** on `feat/curation-ui-v1`. Preserve completed/local work such as the professional ordered selection implementation; do not reset or redo completed tasks merely because the remote branch lags.

Execute the remaining approved plan continuously and sequentially until the professional product is genuinely testable.

### Execution semantics

1. Read the approved redesign spec/plan and the current local state.
2. Use **single-agent sequential execution**. Do not use routine subagents or per-task external review gates.
3. Use TDD/focused tests for the active task, then move directly to the next task.
4. **Do not send a user-visible progress message after an intermediate task, test pass, or commit. Sending that message ends the Codex turn and stops execution.**
5. Continue across Task 3, Task 4, Task 5, Task 6, Task 7 and final acceptance work in the same turn whenever possible.
6. Reuse existing KURA transcript/chunks/candidates/edit-plan and cached model/provider artifacts. Do not rerun expensive ASR/Qwen/provider stages just to exercise the UI.
7. Preserve `/debug` as engineering-only. Build `/curation` as the professional user surface.
8. Keep Resolve frozen with `resolve_calls=0`; no ComfyUI/global Python/PATH/CUDA/system/credential changes.
9. Do not merge to `main` and do not auto-merge.

## Product completion target

`TESTABLE=YES` requires all of the following to work together:

- `/curation` opens as the professional product, not a debug page;
- source video can be chosen/uploaded or registered from a local path;
- source video has a real player and metadata;
- original source audio can be extracted/cached as guide audio, with optional replacement guide audio;
- analysis is reuse-first;
- each phrase can expose up to **3 real playable video previews + 4 real image thumbnails**;
- video and image cards are visually distinct and actually preview media;
- ordered mixed-media multi-select works and persists;
- selected order maps deterministically to V2/V3/V4...;
- `NO BROLL` is mutually exclusive;
- autosave survives refresh/restart;
- `<run>/selection-plan.json` is written atomically;
- professional media routes are asset-id based and do not expose arbitrary filesystem paths;
- standard runtime uses no GPT/OpenAI/Codex call;
- `resolve_calls=0`.

## Completion / stop gate

**Do not stop for ordinary task completion, successful tests, commits, or status reporting.**

End the Codex turn only when:

- `TESTABLE=YES`: the above professional `/curation` milestone is ready for the user to open and test, or
- `HARD_BLOCKER`: a real blocker requires user action/decision and cannot be resolved within the already approved scope.

At that point post one concise HANDOFF with branch/SHA, tests, exact local URL, guide-audio status, preview counts/errors/cache hits, persistence + V2/V3 proof, selection-plan path, `resolve_calls=0`, and any remaining unproven item.