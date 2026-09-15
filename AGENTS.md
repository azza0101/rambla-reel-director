# RAMBLA REEL DIRECTOR — collaboration rules

This repository is an architectural project. Product implementation is forbidden until the design, technical specification, and implementation plan have each been explicitly approved.

## Mandatory startup workflow

Before any task:

1. Synchronize the repository without discarding local work.
2. Read `docs/PROJECT_BRIEF.md`.
3. Read `docs/ARCHITECTURE.md`.
4. Read `docs/DECISIONS.md`.
5. Read `docs/NEXT_TASK.md`.
6. If `docs/NEXT_TASK.md` points to a current spec/plan/approval, read only the sections needed for the active execution batch.
7. Do not contradict approved decisions in `docs/DECISIONS.md`.
8. Treat the repository as source of truth over stale chat context.
9. Do not reconstruct old project history unless a concrete ambiguity requires it.

### Sandboxed-task synchronization fallback

Some Codex Windows sandboxes may be unable to write `.git/FETCH_HEAD` or access the host credential helper even when the source workspace has already been synchronized outside the sandbox. In that case, do not abort solely because `git pull` cannot run inside the sandbox if the intended branch/base is externally verified and local work is preserved. Never discard local edits to force synchronization.

## Delivery workflow

- Use the implementation branch named by the active approved plan.
- Add/update automated tests before considering behavior complete.
- Commit/push logical changes without rewriting useful history.
- Never merge autonomously.
- Apply review corrections on the same branch.

### Git writes and network access from the Windows sandbox

The Windows sandbox may allow workspace edits while denying `.git` writes/network/credential-helper access.

- Do not ask the user to manually run commands just to work around sandbox limitations.
- Prefer narrowly scoped permission requests first.
- Use authenticated GitHub API transport if local Git writes remain blocked.
- Never force-push.
- Preserve stale/dirty source checkout and current runtime caches.

## Safety boundaries

- Never modify the original Resolve timeline.
- AI reasoning must not mutate Resolve before an explicitly approved persisted Edit Plan.
- Do not modify ComfyUI or its Python environment.
- Do not modify global Python/PATH/CUDA/system configuration without approval.
- Do not commit secrets, credentials, private media, model weights, caches, runtime logs, proxies, renders, or downloaded B-roll.
- Keep client assets isolated.
- Keep the backend independently runnable/testable without Resolve.

## Current phase — Professional Curation UI Redesign

The Professional Curation UI Redesign spec and implementation plan were explicitly approved on 2026-09-15.

Authoritative documents:
- `docs/superpowers/specs/2026-09-15-curation-ui-professional-redesign.md`
- `docs/superpowers/plans/2026-09-15-curation-ui-professional-redesign.md`
- `docs/approvals/2026-09-15-curation-ui-professional-redesign-plan-approved.md`
- `docs/NEXT_TASK.md` for the active turn-batch schedule.

Implementation branch: `feat/curation-ui-v1`.

The previous debug-style Curation UI contract and older Editorial Intelligence execution instructions are superseded where they conflict with this phase.

### Execution mode

- **Single-agent sequential execution**, LOW-CREDIT.
- Normal Chat is the external reviewer; no routine internal subagents/reviewers.
- Preserve useful existing local work/commits; do not reset/clean/restart completed work merely because remote lags.
- TDD/focused tests while iterating; full suite only at final acceptance as specified by `docs/NEXT_TASK.md`.
- The Codex client/harness has demonstrated a finite per-turn execution budget independent of weekly/account quota. Therefore the approved implementation is intentionally split into the coherent turn batches defined in `docs/NEXT_TASK.md`.
- Inside a batch, do not emit user-visible progress after individual tasks/tests/commits; continue until the batch is complete or a genuine blocker occurs.
- A batch completion (`BATCH_A_COMPLETE` or `BATCH_B_COMPLETE`) is a valid end-of-turn checkpoint and is **not** a product blocker. The next user turn resumes from that checkpoint without redoing completed work.
- Final completion is `TESTABLE=YES` after Batch C acceptance.
- `HARD_BLOCKER` is reserved only for a real issue requiring user action/decision, not for ordinary per-turn budget exhaustion when the current batch can be safely checkpointed.

### Product target

- `/curation` is the professional user surface; `/debug` stays engineering-only.
- source-video picker/upload + advanced local-path registration;
- source-video player + metadata;
- source-audio extraction/cache as guide audio + optional replacement guide audio;
- reuse-first analysis;
- up to 3 real playable video previews + 4 real image thumbnails per phrase;
- real video/image cards, lightbox/inspector, separate selection controls;
- ordered mixed-media multi-select mapped deterministically to V2/V3/V4...;
- mutually exclusive NO BROLL;
- autosave + refresh persistence + atomic `selection-plan.json`;
- safe asset-id media routes, never arbitrary filesystem paths in the professional UI;
- standard runtime with no GPT/OpenAI/Codex call;
- `resolve_calls=0`.

Never merge autonomously.