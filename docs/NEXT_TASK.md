# Next Task — Execute first implementation plan

Current phase: **implementation authorized for the approved first vertical slice**.

The MVP technical specification is approved and the first implementation plan was explicitly approved by the user on 2026-09-11. Approval is recorded at:

`docs/approvals/2026-09-11-foundation-safe-resolve-plan-approved.md`

The implementation plan is:

`docs/superpowers/plans/2026-09-11-foundation-safe-resolve-vertical-slice.md`

## Required next action

Execute the approved plan exactly within scope.

1. Read current remote `main` through authenticated GitHub API and read `AGENTS.md`, the approved design/contracts specifications, the approval record, and the implementation plan from that exact remote state.
2. Use Superpowers `subagent-driven-development` (preferred) or `executing-plans`, with TDD and verification-before-completion.
3. Start with **Task 0** and branch:

`feat/foundation-safe-resolve-slice`

4. Prefer normal Git if it works. If the Windows sandbox keeps `.git` read-only but `gh` is authenticated and GitHub API is readable/writable, use the **GitHub API transport fallback in `AGENTS.md`** instead of stopping.
5. Under API transport, do not implement inside the stale/dirty `Z:\RAMBLA-reel-director` checkout. Preserve it and materialize a clean plain working tree from the exact remote `main` commit in a separate non-Git directory under `Z:\RAMBLA-reel-data\codex-work\`.
6. Task 0 must prove Codex can perform the complete delivery path itself without user-run PowerShell/Git: create the remote feature branch from current `main`, publish a smoke-file commit through GitHub API, publish a cleanup commit deleting the smoke file, and verify the remote branch after both operations.
7. If Task 0 passes by either normal Git or API transport, continue the plan task-by-task. Keep every published implementation commit on the feature branch.
8. Follow red/green TDD steps and run the specified verification commands before each completion claim. Under API transport, verify intended changed files/content and the remote branch parent before every non-forced ref update.
9. Open a pull request to `main` when the plan completion gate is satisfied. Never merge autonomously.

## Authorized scope

This plan authorizes only the foundation/safety vertical slice: local backend, contracts/hashing, immutable artifacts, orchestration/review/Dry Run, HTTP/SSE, fake Resolve Apply/retry safety, client/path isolation/retention, Resolve capability probe, and one controlled real `PUNCH_IN` applied only to a generated duplicate timeline.

Do **not** install or integrate real AI models, cloud providers, ComfyUI, generated video, broad retrieval/provider integrations, or final panel breadth during this plan.

## Completion gate

Stop and report when either:

- neither normal Git delivery nor the authenticated GitHub API transport in `AGENTS.md` can establish a reliable Codex-driven remote branch/commit/PR path; or
- the entire approved plan is implemented, verified, published on the feature branch, and a reviewable pull request to `main` exists.

Do not merge the pull request autonomously.
