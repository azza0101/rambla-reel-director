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

### Git writes and network access from the Windows sandbox

The Windows sandbox may allow normal workspace file edits while denying writes inside `.git`, network access, or access to host Git credentials.

- Do not ask the user to manually run PowerShell or Git commands merely to work around this sandbox limitation.
- Keep ordinary file edits, analysis, and tests in the sandbox.
- First prefer a narrowly scoped permission request that keeps execution sandboxed: request only the filesystem write access needed for the repository/.git plus network access needed for GitHub.
- Use full elevated/out-of-sandbox execution only when scoped additional permissions cannot satisfy the operation, for example when the host credential helper is required.
- Scope any permission request to the exact repository, branch, Git command family, and network destination required by the current task.
- If the current task permission profile rejects escalation before showing an approval prompt, do not loop.
- Before committing, verify the intended file set and run the task's verification commands; after publishing, verify the resulting remote branch head and PR state.
- Never use elevation to bypass project safety gates, modify unrelated files, or install unrelated software.

### GitHub API transport fallback

If local `.git` writes remain blocked but `gh` is installed, authenticated, and GitHub API access works, the GitHub API transport is an approved delivery path. Do not stop solely because `.git/FETCH_HEAD` or `.git/index.lock` is read-only.

Rules for this fallback:

- GitHub remote state is authoritative. Read the exact `main` SHA through `gh api` before starting.
- Do not implement from a stale or dirty checkout. Preserve any existing local modifications, then materialize a clean plain working tree from the exact remote commit into a separate non-Git workspace outside `Z:\RAMBLA-reel-director`, preferably under `Z:\RAMBLA-reel-data\codex-work\<task-name>\`.
- The plain working tree may be created from the GitHub archive API or equivalent authenticated GitHub API reads. It MUST contain no invented files or content.
- Create the implementation branch remotely from the verified `main` SHA through GitHub API. For the current approved slice the branch is `feat/foundation-safe-resolve-slice`.
- Publish logical commits through GitHub's Git Data API (`blobs` -> `tree` -> `commit` -> non-forced branch-ref update) or an equivalent authenticated GitHub API operation. Before each ref update, re-read the remote branch head and verify it still equals the expected parent. Never force-push.
- A task commit must contain only the files intended by that task. Run tests and diff/content verification in the plain working tree before publishing the corresponding API commit.
- Remote verification replaces local tracking verification: confirm the branch ref points to the new commit, inspect changed files/compare against `main`, and verify the intended content through GitHub API.
- Open/update the pull request through `gh`/GitHub API. Never merge autonomously.
- Task 0 is satisfied when Codex proves the full API delivery cycle itself: create the remote feature branch from current `main`, publish a smoke-file commit, publish a cleanup commit that removes the smoke file, and verify the remote branch after both operations without user-run shell commands.
- Keep the stale/dirty `Z:\RAMBLA-reel-director` checkout untouched until a host process can safely resynchronize it later. The API worktree and remote branch are the active implementation surfaces while this fallback is in use.

If neither local Git delivery nor authenticated GitHub API transport is available, stop with workspace changes intact and report the exact blocked operation; do not create an alternate repository unless explicitly authorized.

## Safety boundaries

- Never modify the original Resolve timeline. The source timeline is `REEL_MASTER`; generated work targets a copy such as `REEL_AI_v01`.
- Never let AI reasoning mutate Resolve. Generate and review a persisted Edit Plan first; apply it only after explicit approval.
- Do not modify ComfyUI or use its Python environment.
- Do not modify global Python environments or install global dependencies without approval.
- Do not commit secrets, credentials, customer data, private media, model weights, caches, runtime logs, proxies, renders, or downloaded B-roll.
- Keep client assets isolated. Never mix assets across clients automatically.
- Keep the backend independently runnable and testable without Resolve or the panel.

## Current phase

The MVP technical specification and the first implementation plan are explicitly approved. Implementation is authorized only for the scope defined by `docs/superpowers/plans/2026-09-11-foundation-safe-resolve-vertical-slice.md` and its approval record. Start with Task 0 to prove the Codex-driven delivery path before product edits. Local Git is preferred when available; authenticated GitHub API transport is explicitly approved when Windows sandbox policy keeps `.git` read-only. Do not broaden scope beyond the approved plan, and do not merge autonomously.
