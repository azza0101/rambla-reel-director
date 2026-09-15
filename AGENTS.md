# RAMBLA REEL DIRECTOR — collaboration rules

## Current source of truth

Current implementation phase: **Professional Curation UI Redesign** on branch `feat/curation-ui-v1`.

Read first:
1. `docs/NEXT_TASK.md`
2. only the source/tests directly relevant to the active plan task
3. `docs/DECISIONS.md` only when a real architecture ambiguity exists

The older Editorial Intelligence execution instructions and the old debug-style Curation UI contract are superseded wherever they conflict with the approved Professional Curation UI Redesign.

## Execution mode — restored continuous workflow

The active implementation workspace MUST be a **real Git checkout/worktree on `feat/curation-ui-v1`**. A plain directory materialized from GitHub API may be used only as a migration/source snapshot, not as the long-running implementation workspace.

Use single-worker sequential execution in the same style that previously completed the Editorial Intelligence plan successfully:

- execute the approved implementation plan continuously, task by task;
- for production behavior changes use RED -> GREEN -> REFACTOR;
- run the focused verification named for the task;
- commit each completed logical task on `feat/curation-ui-v1`;
- continue immediately to the next task without a user-facing status stop;
- maintain a tiny local execution ledger (untracked is fine) with current task, last commit, tests run, remaining item, next action so a new turn can resume without reconstructing history;
- Normal Chat is the external reviewer; do not spawn routine reviewer/subagent loops unless a concrete task genuinely benefits from one;
- do not reread old Issue #3 history on every turn.

`BATCH_A_COMPLETE`, `BATCH_B_CHECKPOINT`, `BATCH_B_COMPLETE`, WIP snapshot publication, token-presence checks, successful compilation alone, or a single smoke endpoint are **not completion gates and are not reasons to end execution**.

Do not optimize for producing a checkpoint. Optimize for completing working end-to-end behavior from the approved plan.

A user signal `.` means: read the newest relevant Normal Chat instruction on Issue #3, read the local execution ledger, and **resume implementation immediately**. It is not a request for a status report.

Stop/end a turn only for:
- a genuine blocker requiring user action/decision that cannot be solved within approved scope; or
- the final `TESTABLE=YES` acceptance state.

If the product harness interrupts a turn for its own limit, preserve code/tests/ledger exactly where they are. On the next user signal, resume from the ledger without re-planning or emitting a status-only turn.

## Delivery

- Work on `feat/curation-ui-v1` in a real Git checkout/worktree.
- Commit logical task completions locally and push them to the feature branch when the task verification is green, so Normal Chat can inspect the actual remote diff.
- Never force-push and never merge autonomously.
- The current `wip/curation-ui-batch-b-review` branch is not the implementation target.

## Safety boundaries

- `resolve_calls=0`; do not mutate Resolve.
- Do not modify ComfyUI or its Python environment.
- Do not modify global Python/PATH/CUDA/system configuration.
- Do not commit credentials, private media, models, caches, runtime logs, renders, proxies, or downloaded B-roll.
- Source media remains read-only after registration.
- Keep client assets isolated.
- Heavy runtime/model/media artifacts stay under approved `Z:\APP REEL TEST` roots.
- Keep `/debug` engineering-facing; `/curation` is the professional product.
- Standard product runtime must require no GPT/OpenAI/Codex calls.
