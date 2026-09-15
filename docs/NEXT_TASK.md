# Current direction — Retrieval quality, before product validation

Latest Issue #3 instruction accepts the external-plan import base; it does not accept sourcing quality or the KURA result. The user's next instruction prioritizes retrieval quality over UI polish. See [RETRIEVAL_QUALITY.md](RETRIEVAL_QUALITY.md) for the implementation, real regression evidence, limits, and reproduction commands. Do not call the product validated based on these fixtures.

Keep the model-neutral external-plan workflow from [EXTERNAL_EDITORIAL_PLAN.md](EXTERNAL_EDITORIAL_PLAN.md). No automatic KURA generation, generative runtime in the critical path, new packages/model downloads, stickers, or Resolve changes. Pexels credentials stay in ignored project `.env.local`, loaded by the backend and stage workers.

---

## Earlier implementation plan (historical)

# Next Task — Complete Professional Curation UI Redesign

Current phase: **implementation authorized for the approved Professional Curation UI Redesign**.

Implementation branch: `feat/curation-ui-v1`

Approved product target remains unchanged: professional `/curation`, source video/project flow, guide audio, real video/image previews, ordered mixed-media selection, NO BROLL, autosave/persistence, safe asset-id media routes, reuse-first analysis, zero GPT/OpenAI runtime dependency, `resolve_calls=0`.

## Active workspace / transport

Use the verified plain workspace:

`Z:\APP REEL TEST\qwen-embedding-smoke\curation-ui-plain`

Do not attempt `git clone`/fetch/pull in this sandbox. Git for Windows is blocked by the sandbox before credential-helper invocation. GitHub authentication itself works.

GitHub remote state is authoritative. Deliver each completed logical task to `feat/curation-ui-v1` through authenticated GitHub API / `gh api` as a real remote commit after focused verification. Verify expected parent before publication and verify new remote SHA + changed-file set after publication.

Preserve and continue from the existing local Curation work already in the plain workspace. Do not redo completed Task 1–4 work unless a focused failing test proves it is broken.

## Remaining implementation — execute continuously

### Task 5 — Professional project/curation API

Complete real end-to-end API behavior:
- project create/load/state;
- source video upload/registration flow;
- run/curation hydration from real artifact data;
- ordered selection endpoint backed by `SelectionStore`;
- atomic `selection-plan.json` persistence;
- safe media route by `project_id + asset_id + variant` only;
- unknown asset => 404;
- candidate resolving outside approved roots => reject;
- no arbitrary browser filesystem path serving;
- reuse-first analyze adapter.

Write behavior tests first. Compilation or one 200 smoke route is not enough. When focused Task 5 behavior tests pass, publish Task 5 as one GitHub API commit to `feat/curation-ui-v1`, verify the remote SHA, update the local ledger, and continue immediately.

### Task 6 — Professional `/curation` product

Replace the current shell with a functioning product wired to Task 5 APIs:
- New Reel setup;
- drag/drop / Choose video;
- advanced local-path registration;
- actual source player + metadata;
- Use original audio / Replace guide audio controls prepared for Task 7;
- ANALYZE REEL action;
- phrase rail with status and filters;
- active phrase content;
- max 3 real playable video candidate cards;
- max 4 real image thumbnails + lightbox;
- inspection separate from selection;
- ordered mixed video+image selection tray;
- deterministic V2/V3/V4... assignment;
- reorder controls;
- mutually exclusive NO BROLL;
- autosave with Saving/Saved/Error+Retry;
- refresh persistence from backend selection plan;
- CONFIRM PLAN validation state.

Tests must verify behavior/contracts, not only presence of strings. When focused Task 6 API/UI behavior tests pass, publish Task 6 as one GitHub API commit, verify remote SHA, update the ledger, and continue immediately.

### Task 7 — Guide audio + reuse integration

Complete:
- source audio extraction/cache to mono 16 kHz PCM s16le;
- replacement external guide audio normalization;
- duration mismatch warning;
- guide-audio-aware ASR input while source-video timeline remains authoritative;
- source+guide signature reuse behavior;
- preserve existing upstream artifacts when unchanged.

Publish Task 7 as one GitHub API commit when focused tests pass, verify remote SHA, update ledger, and continue immediately.

### Final acceptance

Use existing KURA artifacts where valid; do not rerun expensive analysis solely for acceptance.

Prove:
- `/curation` opens as professional product;
- source video flow works;
- guide audio flow works;
- real video/image previews render when candidates exist;
- mixed video+image selection persists with V2/V3/V4 ordering;
- another phrase can be NO BROLL;
- refresh/restart restores state;
- `selection-plan.json` exists at a known path;
- safe asset-id media routes are used;
- `/debug` still works;
- `resolve_calls=0`;
- standard runtime does not call GPT/OpenAI/Codex.

At final gate run fresh full pytest + backend compileall once. Publish final branch state and report `TESTABLE=YES` with exact local URL and evidence.

## Execution contract

Execute continuously, task by task, using RED -> GREEN -> REFACTOR and the tiny local ledger. Do not end for progress reporting, compilation-only success, one-route smoke success, WIP publication, token checks, Git transport status, or any `BATCH_*` checkpoint. Stop only at a genuine user-action blocker or final `TESTABLE=YES`.
