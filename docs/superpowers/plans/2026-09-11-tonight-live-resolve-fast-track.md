# Tonight Live Resolve Fast Track

Date: 2026-09-11
Status: **approved by user priority override: a working software slice is required tonight**

## Goal

Deliver a usable RAMBLA prototype tonight that controls the user's real DaVinci Resolve safely. The minimum visible success is:

1. RAMBLA can connect to the running Resolve instance and inspect the active project/timeline.
2. RAMBLA produces a persisted one-decision Dry Run/Edit Plan for a deterministic `PUNCH_IN`.
3. Apply creates or targets a generated duplicate timeline (`REEL_AI_v01` or collision-safe successor), never `REEL_MASTER`.
4. Apply changes only the duplicate and verifies the result by reading Resolve state back.
5. A minimal user-facing trigger exists (simple local browser page, Resolve Scripts launcher, or equally direct command surface). Polished panel breadth is not required tonight.

This fast track temporarily supersedes the remaining order of `2026-09-11-foundation-safe-resolve-vertical-slice.md`. The original plan remains valid debt and resumes after the live slice works.

## Existing work to preserve

- Keep Task 0 and Task 1 as completed.
- Preserve all Task 2 work.
- If the current Task 2 review-fix is already in progress, finish only the two known blockers and publish that single fix commit. Do not start further contract expansion tonight.
- Defer original-plan Tasks 3+ unless a piece is strictly required for the live path.
- Do not discard or rewrite the existing contracts/backend merely to adopt an upstream project.

## Reuse-first policy

Do not reimplement mature Resolve plumbing tonight when an appropriate permissively licensed component already exists.

### Primary Resolve control plane: `samuelgursky/davinci-resolve-mcp`

Use this as the first candidate for live Resolve operations. It is MIT-licensed, exposes guarded timeline/timeline-item operations, supports transform writes, duplicate/copy helpers, capability probing, frame capture, transcription/subtitle surfaces, and has live-tested Resolve edit kernels.

Rules:

- Install in an isolated tool/virtual environment; never modify ComfyUI or global Python.
- Pin the exact upstream version/commit that passes the local probe.
- Prefer calling the upstream process/API/MCP surface from a thin RAMBLA adapter rather than copying large upstream subsystems.
- Record upstream name/version/license in project notices if distributed.
- If it cannot connect to this machine's Resolve build, fail over to the official `DaVinciResolveScript` API using the same capability-gated adapter boundary; do not spend hours repairing the upstream.

### Optional accelerators after the live punch-in works

- `legifx/resolve-ai-editor` (MIT): reuse/reference its Resolve Scripts launcher, localhost panel pattern, and defensive bridge conventions if that saves time. Do not replace RAMBLA's domain model with it.
- `shanawazvibecode/AutoBroll` (MIT): reuse/reference its transcript/SRT segmentation, Pexels search/download and Resolve placement path for a same-night B-roll stretch goal. Preserve MIT attribution for copied/substantial code.
- StoryToolkitAI is GPLv3. It may be run as a separate external tool or studied for ideas, but do not copy/embed its GPL code into RAMBLA during this fast track.
- Do not install multiple competing Resolve control stacks just to compare them. Probe the primary choice first and switch only on a concrete blocker.

## Execution order

### FT0 — Finish/checkpoint current Task 2 fix

If uncommitted Task 2 review fixes already exist, finish the two known blockers, run the contract tests, publish one fix commit via the existing GitHub API transport, and stop contract work. If no such local work exists, checkpoint Task 2 and continue; do not spend more time expanding schemas tonight.

### FT1 — Live Resolve probe first, not fake Resolve

1. Detect installed Resolve version/edition and whether Resolve is running.
2. Install/configure the primary Resolve control plane in an isolated environment.
3. Run its doctor/capability probe against the real machine.
4. Read only: active project, active timeline, FPS, video tracks, timeline items, and transform capability.
5. Persist a small sanitized capability report in the transient runtime area, not Git if it contains user project names/paths.

Success gate: structured read-back from the real Resolve instance.

If external scripting is unavailable but the upstream supports an in-Resolve bridge for the installed edition, use that documented bridge. Never use license circumvention or private Resolve internals.

### FT2 — Safe live mutation spike

Use either a disposable project/timeline or a generated duplicate of the active source. Never mutate `REEL_MASTER`.

1. Identify source timeline identity and first safe V1 clip (or explicit selected/current item if available).
2. Allocate collision-safe generated timeline name `REEL_AI_v01`, `REEL_AI_v02`, ...
3. Duplicate/rebuild into the generated timeline using the proven upstream/public API path.
4. Apply a deterministic punch-in to the duplicate only. For the first live proof, the decision range may equal the exact full duration of one clip so a whole-item transform is valid. Suggested initial transform: uniform zoom 1.08 with centered anchor unless the live probe requires another supported representation.
5. Read the transform back and confirm the source timeline is unchanged.
6. If the mutation result is ambiguous, do not retry blindly; create a fresh generated timeline or stop with evidence.

Success gate: the duplicate visibly/readably differs, source remains unchanged, and read-back confirms the expected transform.

### FT3 — Minimal RAMBLA usable surface

Wire the proven live operation into the existing RAMBLA backend through a thin adapter. Keep the existing Edit Plan as the mutation gate.

Minimum surface:

- `Probe Resolve` — reports connection/project/timeline/capabilities.
- `Dry Run PUNCH_IN` — generates and displays/persists one deterministic Edit Plan without mutation.
- `Apply to Duplicate` — requires that plan, creates collision-safe duplicate, applies, verifies.

Prefer the fastest surface that a non-developer can operate tonight:

1. simple localhost browser page served by the existing FastAPI backend, or
2. Resolve Workspace > Scripts launcher that starts/opens that page.

Do not spend time on styling, authentication beyond loopback/local use, packaging, or final UX tonight.

### FT4 — Stretch goal: useful B-roll path

Only after FT1–FT3 are green.

If an SRT/subtitle transcript and a Pexels API key are available, adapt the MIT AutoBroll flow to:

- segment transcript,
- create/search semantic-ish stock queries,
- download a very small number of portrait-compatible clips,
- present Dry Run choices,
- place approved B-roll on a dedicated track of the generated timeline while retaining original audio.

If credentials/transcript are missing, skip this stretch goal rather than block the live MVP.

## Tonight verification

Before claiming success, demonstrate on the actual machine:

- live Resolve connection is green;
- source timeline identity captured before Apply;
- Dry Run causes zero mutation;
- generated timeline name is distinct from source;
- one PUNCH_IN is applied to generated timeline only;
- transform read-back matches the plan within the supported representation;
- source timeline transform/state checked unchanged;
- the operation can be triggered from the minimal RAMBLA user-facing surface;
- no ComfyUI environment/global Python was modified.

## Deferred after tonight

Resume the original foundation plan after the live prototype works: immutable ArtifactStore, full run orchestration/leases, fake adapter contract suite, full HTTP/SSE/idempotency, retention/isolation suite, broader Resolve retry/cleanup behavior, final panel, real AI providers and full editorial action breadth.

Fake Resolve is deferred, not deleted: it remains valuable for deterministic CI, but it is no longer allowed to block the first live proof on a machine where real Resolve is available.
