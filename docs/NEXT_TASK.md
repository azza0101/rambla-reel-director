# Next Task — Execute first implementation plan

Current phase: **implementation authorized for the approved first vertical slice**.

The MVP technical specification is approved and the first implementation plan was explicitly approved by the user on 2026-09-11. Approval is recorded at:

`docs/approvals/2026-09-11-foundation-safe-resolve-plan-approved.md`

The implementation plan is:

`docs/superpowers/plans/2026-09-11-foundation-safe-resolve-vertical-slice.md`

## Current delivery status

Task 0 has passed through the authenticated GitHub API transport fallback.

Verified remote branch:

`feat/foundation-safe-resolve-slice`

Evidence:

- Task-0 base main: `a47674ced3777d967094417f3156b4dbbae35738`
- smoke commit: `7c3fd9f93f538be3b471ba4f427409df236e6ae4`
- cleanup commit / feature-branch head after Task 0: `70f538089fffd674ce51e3577b701b115e7abf82`
- after cleanup, the feature branch had zero file differences from its Task-0 base main

Local `.git` remains read-only in the Windows sandbox. Continue using the GitHub API transport described in `AGENTS.md`; do not treat the local Git limitation as a blocker.

## Required next action

Continue the approved plan from **Task 1**.

1. Read current remote `main`, current feature-branch head, `AGENTS.md`, the approved specifications, approval record, and implementation plan through authenticated GitHub API.
2. Use Superpowers `subagent-driven-development` (preferred) or `executing-plans`, with TDD and verification-before-completion.
3. Keep using remote branch:

`feat/foundation-safe-resolve-slice`

4. Materialize the exact remote feature-branch tree into a clean plain working directory with no `.git`.
5. Prefer `Z:\RAMBLA-reel-data\codex-work\foundation-safe-resolve-slice` only if writable. If the host denies that path after permission approval, use a sandbox-writable current-workspace/temp child according to the fallback in `AGENTS.md`; do not modify the stale/dirty `Z:\RAMBLA-reel-director` checkout.
6. Execute Task 1 and later tasks strictly in plan order with red/green TDD. Run the specified tests before each completion claim.
7. Publish each logical task commit through GitHub API only after verifying the current remote branch parent equals the expected parent. Never force-update the branch.
8. After every API commit, verify the remote branch ref and changed-file set/content.
9. Open a pull request to `main` when the plan completion gate is satisfied. Never merge autonomously.

## Authorized scope

This plan authorizes only the foundation/safety vertical slice: local backend, contracts/hashing, immutable artifacts, orchestration/review/Dry Run, HTTP/SSE, fake Resolve Apply/retry safety, client/path isolation/retention, Resolve capability probe, and one controlled real `PUNCH_IN` applied only to a generated duplicate timeline.

Do **not** install or integrate real AI models, cloud providers, ComfyUI, generated video, broad retrieval/provider integrations, or final panel breadth during this plan.

## Completion gate

Stop and report when either:

- authenticated GitHub API transport itself becomes unavailable or remote publication cannot be made safely without force/update races; or
- the entire approved plan is implemented, verified, published on the feature branch, and a reviewable pull request to `main` exists.

A denied preferred local API-worktree path is not by itself a stop condition if another sandbox-writable plain workspace exists.

Do not merge the pull request autonomously.
