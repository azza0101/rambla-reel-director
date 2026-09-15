# Next Task — Finish Professional Curation UI Redesign

Current phase: **implementation authorized for the approved Professional Curation UI Redesign**.

Authoritative approval/spec/plan:

- `docs/approvals/2026-09-15-curation-ui-professional-redesign-plan-approved.md`
- `docs/superpowers/specs/2026-09-15-curation-ui-professional-redesign.md`
- `docs/superpowers/plans/2026-09-15-curation-ui-professional-redesign.md`

Implementation branch:

`feat/curation-ui-v1`

The earlier debug-style Curation UI contract and older Editorial Intelligence + StyleDNA execution instructions are superseded wherever they conflict with this file and the approved redesign plan.

## Resume rule

Resume from the **existing local working state**. Preserve all completed/uncommitted work, especially the professional ordered selection implementation in `curation_selection.py`. Never reset or redo completed tasks merely because the remote branch lags.

Because the Codex client/harness has demonstrated a finite per-turn execution budget even while account/week quota remains available, execute the approved plan in the following **three coherent turn batches**. This is an execution scheduling change only; product scope and acceptance criteria are unchanged.

## TURN BATCH A — previews + hydration

Execute remaining Plan Task 3 and Task 4 only:

- real lightweight video previews + poster generation;
- real image thumbnail materialization;
- stable preview cache and per-card failure isolation;
- max concurrency 4;
- artifact hydration into genuinely separate video and image shelves;
- max 3 video + 4 image candidates per phrase;
- asset-id candidate index;
- focused tests for Task 3 + 4;
- preserve all work in files/commit/checkpoint before ending the turn.

Do not rerun ASR/Qwen/provider discovery just to test these components.

Valid end state for this turn: `BATCH_A_COMPLETE` or a real `HARD_BLOCKER`.

## TURN BATCH B — API + professional HTML product

On the next turn resume without redoing Batch A. Execute Plan Task 5 and Task 6:

- professional project/curation API;
- safe asset-id media routes, never arbitrary browser filesystem paths;
- source-video project API wiring needed by the product shell;
- rewrite `/curation` as the professional product;
- source-video picker/drag-drop + advanced local-path flow;
- real source-video player + metadata;
- real playable video cards;
- real image cards + lightbox;
- phrase rail, filters, save state, selection tray;
- ordered mixed-media multi-select and V2/V3/V4 chips;
- mutually exclusive NO BROLL;
- autosave/retry/refresh persistence;
- focused API + UI tests;
- preserve all work in files/commit/checkpoint before ending the turn.

Valid end state for this turn: `BATCH_B_COMPLETE` or a real `HARD_BLOCKER`.

## TURN BATCH C — guide audio + integration + acceptance

On the next turn resume without redoing A/B. Execute Plan Task 7 and final acceptance work:

- source audio extraction/cache as normalized guide audio;
- optional replacement guide audio;
- guide-audio-aware analysis while timeline remains source-video based;
- reuse-first behavior for transcript/chunks/candidates/edit-plan;
- KURA acceptance smoke using existing artifacts where valid;
- real video/image preview counts and error/cache evidence;
- mixed video+image selection proving V2/V3 persistence;
- separate NO BROLL proof;
- full fresh pytest + backend compileall once at final gate;
- exact local `/curation` URL and `selection-plan.json` path;
- `resolve_calls=0`.

Valid end state: `TESTABLE=YES` or a real `HARD_BLOCKER`.

## Per-turn execution rules

1. Single worker, sequential, LOW-CREDIT.
2. Read only this file, the approved plan section for the active batch, and directly relevant source/tests. Do not reread old Issue #3 history.
3. No routine subagents/reviewers; Normal Chat is the external reviewer.
4. TDD/focused tests while iterating. Full suite only in Batch C final gate.
5. Inside a batch, do **not** send user-visible progress after individual tasks/tests/commits; continue until the batch is complete or a real blocker occurs.
6. At a batch boundary, a concise final message is allowed because the per-turn budget is finite. It must contain only batch result, files/commit/test evidence, blocker if any, and exact next batch.
7. Reuse existing KURA artifacts and caches aggressively.
8. `/debug` remains engineering-only; `/curation` is the professional product.
9. Resolve frozen: `resolve_calls=0`.
10. No ComfyUI/global Python/PATH/CUDA/system/credential changes. No main merge or auto-merge.

## Final product target

`TESTABLE=YES` still requires:

- professional `/curation` surface;
- source video choose/upload/local-path registration;
- source player + metadata;
- original/external guide audio;
- reuse-first analysis;
- up to 3 real playable video previews + 4 real image thumbnails per phrase;
- real media preview UX + image lightbox;
- ordered mixed-media multi-select;
- deterministic V2/V3/V4... mapping;
- NO BROLL exclusivity;
- autosave + refresh persistence;
- atomic `<run>/selection-plan.json`;
- asset-id safe media routes;
- no GPT/OpenAI/Codex calls at standard runtime;
- `resolve_calls=0`.
