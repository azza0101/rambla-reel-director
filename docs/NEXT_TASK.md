# Next Task — Tonight live Resolve fast track

Current phase: **working live software required tonight**.

The user explicitly reprioritized the project on 2026-09-11: use mature open-source foundations where sensible, prefer the real installed DaVinci Resolve over letting a fake adapter block progress, and deliver a functioning RAMBLA slice tonight.

The active fast-track plan is:

`docs/superpowers/plans/2026-09-11-tonight-live-resolve-fast-track.md`

The original approved foundation plan remains valid deferred work:

`docs/superpowers/plans/2026-09-11-foundation-safe-resolve-vertical-slice.md`

## Current delivery status

Authenticated GitHub API transport is proven and remains the delivery path while local `.git` is read-only.

Remote implementation branch:

`feat/foundation-safe-resolve-slice`

Published implementation includes:

- Task 0 API delivery-path smoke: complete
- Task 1 isolated FastAPI backend scaffold: complete
- Task 2 contracts/hashing/schema export: published; complete only the two current review blockers if their fix is already in progress, then stop contract expansion tonight

Draft PR: `#1`.

## Codex ↔ ChatGPT handoff channel

Use GitHub issue `#2` (`RAMBLA agent handoff — Codex ↔ ChatGPT`) as the compact orchestration channel.

At each stable checkpoint, blocker, or review request, Codex MUST post one concise `HANDOFF` comment to issue #2 using the protocol defined in that issue. Before starting the next logical stage, read the latest ChatGPT `REVIEW` reply in issue #2.

- `APPROVED` + `needs_user: NO`: continue autonomously within the current approved plan.
- `FIX`: apply only the requested fix, verify, and hand off again.
- `USER_DECISION` or `needs_user: YES`: stop and request the user's approval in Codex UI.

This handoff channel never bypasses local Codex permission prompts. Important destructive, credential, system-install, source-timeline, scope, merge/release, or other user-visible decisions still require the user.

PR #1 remains the code-review surface; issue #2 is only the status/review-routing channel.

## Required next action

1. Read current remote `main`, the feature branch, `AGENTS.md`, this file, issue #2, and the fast-track plan through authenticated GitHub API.
2. Stay in economical single-agent mode. Use `superpowers:executing-plans`, TDD where it materially reduces risk, and verification-before-completion. Do not spawn reviewer/subagent swarms; ChatGPT is the external reviewer through PR #1 / issue #2.
3. Preserve the existing API worktree and Task 2 local work. Do not touch the stale/dirty `Z:\RAMBLA-reel-director` checkout.
4. If the Task 2 review fix is already underway, finish the two known blockers, test, publish one fix commit, then pivot immediately to the fast track.
5. Start FT1: probe the user's **real Resolve** before building more fake infrastructure.
6. Primary candidate Resolve control plane: MIT-licensed `samuelgursky/davinci-resolve-mcp`. Install/configure it only in an isolated environment; never ComfyUI/global Python. Pin the exact upstream version/commit that passes the local live probe.
7. Do not install multiple competing Resolve stacks unless the primary candidate hits a concrete blocker.
8. Execute FT2 safe live mutation only on a disposable/generated timeline. `REEL_MASTER` must remain unchanged.
9. Execute FT3 minimal user-facing surface using the existing FastAPI backend: Probe Resolve, Dry Run PUNCH_IN, Apply to Duplicate.
10. Only after FT1–FT3 are green, attempt the optional MIT AutoBroll/Pexels stretch goal if required credentials/transcript already exist.
11. Publish logical commits through GitHub API after tests/live verification. Never force-update or merge.

## Tonight completion gate

A successful tonight slice must demonstrate on the actual machine:

- live Resolve structured read-back;
- zero-mutation Dry Run;
- collision-safe generated duplicate timeline;
- one deterministic PUNCH_IN applied only to the duplicate;
- read-back verification of the transform and unchanged source;
- direct user-triggerable RAMBLA surface;
- no ComfyUI/global Python modification.

Fake Resolve, full ArtifactStore/orchestration, SSE/idempotency breadth and final UI are deferred debt, not removed requirements.
