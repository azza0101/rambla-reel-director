# Next Task — Execute first implementation plan

Current phase: **implementation authorized for the approved first vertical slice**.

The MVP technical specification is approved and the first implementation plan was explicitly approved by the user on 2026-09-11. Approval is recorded at:

`docs/approvals/2026-09-11-foundation-safe-resolve-plan-approved.md`

The implementation plan is:

`docs/superpowers/plans/2026-09-11-foundation-safe-resolve-vertical-slice.md`

## Required next action

Execute the approved plan exactly within scope.

1. Synchronize the repository and read `AGENTS.md`, the approved design/contracts specifications, the approval record, and the implementation plan.
2. Use Superpowers `subagent-driven-development` (preferred) or `executing-plans`, with TDD and verification-before-completion.
3. Start with **Task 0** and create/switch to branch:

`feat/foundation-safe-resolve-slice`

4. Task 0 must prove Codex can perform the complete Git delivery path itself: branch creation/switch, workspace edit, commit, push, cleanup commit, push, and remote-tracking verification. Do not ask the user to run PowerShell/Git manually.
5. If sandboxed Git writes are denied, request the minimum out-of-sandbox/elevated Git execution allowed by `AGENTS.md`. If the host still refuses it, stop before product implementation and report the exact blocker.
6. If Task 0 passes, continue the plan task-by-task. Keep all implementation changes on the feature branch.
7. Follow red/green TDD steps and run the specified verification commands before each completion claim.
8. Open a pull request to `main` when the plan completion gate is satisfied. Never merge autonomously.

## Authorized scope

This plan authorizes only the foundation/safety vertical slice: local backend, contracts/hashing, immutable artifacts, orchestration/review/Dry Run, HTTP/SSE, fake Resolve Apply/retry safety, client/path isolation/retention, Resolve capability probe, and one controlled real `PUNCH_IN` applied only to a generated duplicate timeline.

Do **not** install or integrate real AI models, cloud providers, ComfyUI, generated video, broad retrieval/provider integrations, or final panel breadth during this plan.

## Completion gate

Stop and report when either:

- Task 0 cannot establish reliable Codex-driven Git writes/pushes; or
- the entire approved plan is implemented, verified, pushed on the feature branch, and a reviewable pull request to `main` exists.

Do not merge the pull request autonomously.
