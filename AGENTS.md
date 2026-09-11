# RAMBLA REEL DIRECTOR — collaboration rules

This repository is an architectural project. Product implementation is forbidden until the design, technical specification, and implementation plan have each been explicitly approved.

## Mandatory startup workflow

Before any task:

1. Synchronize the repository without discarding local work.
2. Read `docs/PROJECT_BRIEF.md`.
3. Read `docs/ARCHITECTURE.md`.
4. Read `docs/DECISIONS.md`.
5. Read `docs/NEXT_TASK.md`.
6. If `docs/NEXT_TASK.md` or another approved document points to a current specification, plan, review, approval, or task file, read that file before acting.
7. Do not contradict approved decisions in `docs/DECISIONS.md`.
8. Treat the repository as the source of truth over prior chat context whenever repository instructions exist.
9. Do not require the user to remind you to read these files: automatically re-read them at the start of every new task after synchronization.

### Sandboxed-task synchronization fallback

Some Codex Windows sandboxes may be unable to write `.git/FETCH_HEAD` or access the host credential helper even when the source workspace has already been synchronized outside the sandbox. In that case, do not abort solely because `git pull` cannot run inside the sandbox if all of the following are true:

- the task was launched from the intended source workspace;
- the user or an external trusted process has just synchronized that source workspace against `origin/main`;
- the exact expected `main` commit SHA is provided to the task;
- `git rev-parse HEAD` inside the task matches that expected SHA;
- the working tree is clean.

When those conditions hold, record that synchronization was externally verified and continue reading the repository. Do not claim the sandbox itself performed the pull.

If local chat context conflicts with the current repository state, stop and follow the repository unless the user explicitly overrides it.

## Delivery workflow

- Use a separate branch for every implementation task.
- Add or update automated tests before considering work complete.
- Commit and push the branch.
- Open a pull request toward `main` describing changes, tests and results, open problems, and decisions required.
- Never merge autonomously.
- Apply review corrections on the same branch.

### Git writes from the Windows sandbox

The Windows sandbox may allow normal workspace file edits while denying writes inside `.git` such as `FETCH_HEAD` or `index.lock`.

- Do not ask the user to manually run PowerShell or Git commands merely to work around this sandbox limitation.
- Keep ordinary file edits, analysis, and tests in the sandbox.
- If a required Git operation fails specifically because the sandbox cannot write `.git` or cannot access Git credentials/network, request explicit elevated/out-of-sandbox execution for the minimum necessary Git command(s) in the intended repository.
- Scope elevated Git operations to the exact repository, branch, and files required by the current task.
- Before committing, verify the diff and `git diff --check`; after pushing, verify the resulting HEAD, remote tracking state, and clean working tree.
- Never use elevation to bypass project safety gates, modify unrelated files, or install unrelated software.
- If elevated execution is unavailable, stop with the workspace changes intact and report the exact blocked Git operation; do not ask the user to recreate the work manually and do not create an alternate repository unless explicitly authorized.

## Safety boundaries

- Never modify the original Resolve timeline. The source timeline is `REEL_MASTER`; generated work targets a copy such as `REEL_AI_v01`.
- Never let AI reasoning mutate Resolve. Generate and review a persisted Edit Plan first; apply it only after explicit approval.
- Do not modify ComfyUI or use its Python environment.
- Do not modify global Python environments or install global dependencies without approval.
- Do not commit secrets, credentials, customer data, private media, model weights, caches, runtime logs, proxies, renders, or downloaded B-roll.
- Keep client assets isolated. Never mix assets across clients automatically.
- Keep the backend independently runnable and testable without Resolve or the panel.

## Current phase

The MVP technical specification and the first implementation plan are explicitly approved. Implementation is authorized only for the scope defined by `docs/superpowers/plans/2026-09-11-foundation-safe-resolve-vertical-slice.md` and its approval record. Start with Task 0 to prove the Codex-driven Git delivery path before product edits. Do not broaden scope beyond the approved plan, and do not merge autonomously.
