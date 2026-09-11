# Next Task — Approve first implementation plan

Current phase: **implementation plan approval**.

The MVP technical specification was explicitly approved by the user on 2026-09-11 and recorded as D-028 in `docs/DECISIONS.md`.

The first implementation plan is:

`docs/superpowers/plans/2026-09-11-foundation-safe-resolve-vertical-slice.md`

This plan intentionally implements only the control-plane and mutation-safety foundation plus one real `PUNCH_IN` vertical slice. It does not yet add real AI models, retrieval providers, generated media, cloud providers, or the final Resolve panel.

## Required next action

Request explicit human approval of the first implementation plan.

If approval is granted:

1. Codex synchronizes the repository and reads `AGENTS.md`, the approved specifications, and the implementation plan.
2. Codex uses a dedicated implementation branch `feat/foundation-safe-resolve-slice`.
3. Task 0 first proves that branch creation, commit, push, and remote tracking work without asking the user to operate Git manually.
4. If the Git delivery path passes, execute the plan task-by-task using Superpowers TDD/subagent workflow.
5. Stop and report immediately if Task 0 cannot establish reliable Codex-driven Git writes/pushes.
6. Keep every implementation change on the task branch and open a pull request to `main`; never merge autonomously.

## Completion gate for this plan

The plan is accepted only after:

- isolated local backend tests pass;
- v1 contracts/hashing/artifact persistence tests pass;
- Dry Run has zero Resolve mutation paths;
- fake Resolve end-to-end Apply/retry tests pass;
- client/path isolation and retention tests pass;
- the installed Resolve version has a factual capability matrix;
- a controlled manually seeded `PUNCH_IN` plan is applied only to a generated duplicate timeline while the source remains unchanged;
- the branch is pushed and a reviewable pull request exists.

Do not install or integrate local AI models until this plan has completed and been reviewed.