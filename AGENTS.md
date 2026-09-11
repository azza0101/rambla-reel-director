# RAMBLA REEL DIRECTOR — collaboration rules

This repository is an architectural project. Product implementation is forbidden until the design, technical specification, and implementation plan have each been explicitly approved.

## Mandatory startup workflow

Before any task:

1. Synchronize the repository without discarding local work.
2. Read `docs/PROJECT_BRIEF.md`.
3. Read `docs/ARCHITECTURE.md`.
4. Read `docs/DECISIONS.md`.
5. Read `docs/NEXT_TASK.md`.
6. If `docs/NEXT_TASK.md` or another approved document points to a current specification, plan, review, or task file, read that file before acting.
7. Do not contradict approved decisions in `docs/DECISIONS.md`.
8. Treat the repository as the source of truth over prior chat context whenever repository instructions exist.
9. Do not require the user to remind you to read these files: automatically re-read them at the start of every new task after synchronizing `main`.

If local chat context conflicts with the current repository state, stop and follow the repository unless the user explicitly overrides it.

## Delivery workflow

- Use a separate branch for every implementation task.
- Add or update automated tests before considering work complete.
- Commit and push the branch.
- Open a pull request toward `main` describing changes, tests and results, open problems, and decisions required.
- Never merge autonomously.
- Apply review corrections on the same branch.

## Safety boundaries

- Never modify the original Resolve timeline. The source timeline is `REEL_MASTER`; generated work targets a copy such as `REEL_AI_v01`.
- Never let AI reasoning mutate Resolve. Generate and review a persisted Edit Plan first; apply it only after explicit approval.
- Do not modify ComfyUI or use its Python environment.
- Do not modify global Python environments or install global dependencies without approval.
- Do not commit secrets, credentials, customer data, private media, model weights, caches, runtime logs, proxies, renders, or downloaded B-roll.
- Keep client assets isolated. Never mix assets across clients automatically.
- Keep the backend independently runnable and testable without Resolve or the panel.

## Current phase

Technical specification review. No application code, product dependencies, models, or Resolve integration may be added until the specification and implementation plan are approved.
