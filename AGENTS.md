# RAMBLA REEL DIRECTOR — collaboration rules

## Current source of truth

Current implementation phase: **Professional Curation UI Redesign** on branch `feat/curation-ui-v1`.

Read first:
1. `docs/NEXT_TASK.md`
2. only the source/tests directly relevant to the active plan task
3. `docs/DECISIONS.md` only when a real architecture ambiguity exists

The older Editorial Intelligence execution instructions and the old debug-style Curation UI contract are superseded wherever they conflict with the approved Professional Curation UI Redesign.

## Execution mode — continuous workflow with GitHub API transport

The current Codex Windows sandbox cannot create a normal Git clone/worktree because Git for Windows fails before credential-helper invocation with a signal-pipe Win32 access error. This is an environment limitation, not a project blocker.

Use the existing verified plain workspace:

`Z:\APP REEL TEST\qwen-embedding-smoke\curation-ui-plain`

Treat GitHub remote state as authoritative and use the already-working authenticated GitHub API / `gh api` transport for delivery. Do **not** retry `git clone`, `git fetch`, `git pull`, reset, clean, or other `.git`-dependent loops in this sandbox.

Execution must match the earlier successful continuous style:

- single worker, sequential execution;
- execute the approved implementation plan continuously, task by task;
- for production behavior changes use RED -> GREEN -> REFACTOR;
- run the focused verification named for the task;
- after each completed logical task, publish the verified file set to `feat/curation-ui-v1` through GitHub API as one logical commit, verifying the expected remote parent first and verifying the new remote SHA after publication;
- continue immediately to the next task without a user-facing status stop;
- maintain a tiny local execution ledger (untracked is fine) with current task, latest remote SHA, files changed, tests run, remaining item, next action;
- Normal Chat is the external reviewer; no routine internal reviewer/subagent loops;
- do not reread old Issue #3 history on every turn.

`BATCH_*`, WIP publication, token-presence checks, compilation alone, or a single smoke endpoint are **not completion gates and are not reasons to end execution**.

A user signal `.` means: read the newest relevant Normal Chat instruction on Issue #3, read the local execution ledger, and resume implementation immediately. It is not a request for a status report.

Stop/end a turn only for:
- a genuine blocker requiring user action/decision that cannot be solved within approved scope; or
- final `TESTABLE=YES`.

If the product harness interrupts a turn for its own limit, preserve code/tests/ledger exactly where they are. On the next user signal, resume from the ledger without re-planning or emitting a status-only turn.

## Delivery

- Implementation target remains `feat/curation-ui-v1`.
- Use GitHub API commits as the delivery mechanism in this sandbox.
- Before every publication: verify remote branch head equals the expected parent.
- After every publication: verify the remote branch advanced to the new commit and inspect the changed-file set.
- Never force-push and never merge autonomously.
- `wip/curation-ui-batch-b-review` is not the implementation target.

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
