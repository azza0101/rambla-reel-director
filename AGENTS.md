# RAMBLA REEL DIRECTOR — collaboration rules

## Source of truth for current work

Current implementation phase: **Professional Curation UI Redesign** on branch `feat/curation-ui-v1`.

For routine execution in this phase, read:
1. `docs/NEXT_TASK.md` — **self-contained authoritative execution mirror for the active batch**.
2. Directly relevant source/test files for that batch.
3. `docs/DECISIONS.md` only if a product/architecture ambiguity arises.

The full approved redesign spec/plan live on branch `design/curation-ui-professional-redesign`. **Do not fetch/reread them during ordinary batch execution.** `docs/NEXT_TASK.md` already mirrors the requirements needed for the active implementation batches. Consult the design branch only if `NEXT_TASK.md` is genuinely ambiguous.

Old Editorial Intelligence + StyleDNA execution instructions and the old debug-style Curation UI contract are superseded wherever they conflict with `docs/NEXT_TASK.md`.

## Execution mode

- Single worker, sequential, LOW-CREDIT.
- Preserve all existing local/uncommitted work; never reset/clean/restart completed work merely because remote lags.
- The Codex client/harness has shown a finite per-turn execution budget independent of weekly/account quota.
- Therefore execute the redesign in the coherent turn batches defined in `docs/NEXT_TASK.md`.
- Inside a batch, do not emit user-visible progress after individual tasks/tests/commits. Continue until the batch is complete or a genuine blocker occurs.
- `BATCH_A_COMPLETE` and `BATCH_B_COMPLETE` are valid safe end-of-turn checkpoints, not blockers.
- `TESTABLE=YES` is the final completion state after Batch C.
- `HARD_BLOCKER` is reserved for a real issue requiring user action/decision; ordinary turn-budget exhaustion should instead checkpoint the current batch safely and report the nearest completed batch/sub-block.
- No routine subagents/reviewers; Normal Chat is the external reviewer.
- Use focused tests while iterating; full suite only at the final gate specified in `NEXT_TASK.md`.

## Safety boundaries

- `resolve_calls=0`; do not mutate Resolve.
- Do not modify ComfyUI or its Python environment.
- Do not modify global Python/PATH/CUDA/system configuration.
- Do not commit credentials, private media, models, caches, runtime logs, renders, proxies, or downloaded B-roll.
- Source media remains read-only after registration.
- Keep client assets isolated.
- Heavy runtime/model/media artifacts stay under approved `Z:\APP REEL TEST` roots.
- Never force-push or merge autonomously.

## Delivery

- Work on `feat/curation-ui-v1`.
- Commit/push logical changes without rewriting useful history when the environment allows it.
- If local Git writes are sandbox-blocked, preserve workspace changes and use authenticated GitHub API transport where available rather than asking the user to run manual commands.
- Keep `/debug` engineering-facing; `/curation` is the professional product.
- Standard product runtime must require no GPT/OpenAI/Codex calls.
