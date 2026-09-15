# Next Task — Execute Editorial Intelligence + StyleDNA V1

Current phase: **implementation authorized for the approved Editorial Intelligence + StyleDNA V1 plan**.

Approval is recorded at:

`docs/approvals/2026-09-14-editorial-intelligence-style-dna-v1-plan-approved.md`

Approved implementation plan:

`docs/superpowers/plans/2026-09-14-editorial-intelligence-style-dna-v1.md`

Approved design/spec:

`docs/superpowers/specs/2026-09-14-editorial-intelligence-style-dna-v1-design.md`

## Required next action

Execute the approved plan exactly within scope on branch:

`feat/editorial-intelligence-style-dna-v1`

Base/unified branch:

`feat/resolve-panel-safe-v1`

1. Synchronize the remote implementation branch and verify its expected parent/base before editing.
2. Read `AGENTS.md`, `docs/PROJECT_BRIEF.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, this file, the approval record, design/spec, and implementation plan.
3. Use Superpowers `subagent-driven-development`, `using-git-worktrees`, `test-driven-development`, and `verification-before-completion`.
4. Work in an isolated clean worktree/smoke checkout. Leave the original dirty `Z:\RAMBLA-reel-director` checkout untouched.
5. Execute all plan tasks continuously, task-by-task. Each production behavior change follows RED -> GREEN -> REFACTOR; run the focused verification named by the plan before committing each task.
6. After every task, perform spec-compliance and code-quality review before continuing. Record progress in the SDD ledger so execution can resume safely after compaction or interruption.
7. Keep Resolve completely frozen during this plan; every analysis/smoke path must preserve `resolve_calls=0`.
8. Do not modify ComfyUI, global Python, credentials, system configuration, user media, model weights, downloaded B-roll, or unrelated files.
9. At completion run fresh `pytest -q` and `python -m compileall backend`, inspect the complete diff against `feat/resolve-panel-safe-v1`, and perform a final whole-branch review.
10. Open a **draft** pull request from `feat/editorial-intelligence-style-dna-v1` to `feat/resolve-panel-safe-v1`. Never merge autonomously and do not update `main`.

## Completion gate

Stop only for an irreversible/destructive operation, security-sensitive action, a side effect outside the isolated worktree that requires explicit permission, or a plan defect where every forward path would be guesswork.

Otherwise continue autonomously until the plan is implemented, freshly verified, pushed, and represented by a reviewable draft PR against `feat/resolve-panel-safe-v1`.
