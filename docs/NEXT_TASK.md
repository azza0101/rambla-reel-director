# Next Task — Complete Professional Curation UI Redesign

Current phase: **implementation authorized for the approved Professional Curation UI Redesign**.

Implementation branch: `feat/curation-ui-v1`

Approved product target remains unchanged: professional `/curation`, source video/project flow, guide audio, real video/image previews, ordered mixed-media selection, NO BROLL, autosave/persistence, safe asset-id media routes, reuse-first analysis, zero GPT/OpenAI runtime dependency, `resolve_calls=0`.

## Immediate recovery: restore the proven working execution setup

The current slowdowns came from running in a plain non-Git workspace and allowing intermediate `BATCH_*_CHECKPOINT` exits. Restore the earlier successful execution pattern now.

1. Create a fresh **real Git clone/checkout** under the approved RAMBLA test root, e.g. `Z:\APP REEL TEST\qwen-embedding-smoke\curation-ui-git`, authenticated with the already-working GitHub account.
2. Check out `feat/curation-ui-v1` at the current remote head.
3. Do NOT use the old `editorial-intelligence-worktree` as the active workspace.
4. Treat these existing locations only as migration sources/backups:
   - `Z:\APP REEL TEST\qwen-embedding-smoke\curation-ui-plain`
   - `Z:\APP REEL TEST\qwen-embedding-smoke\curation-migration-backup`
5. Copy/reconcile only the actual Curation implementation/test changes from the migration source into the fresh Git checkout. Never copy `.git`, runtime media, models, caches, downloaded assets, or unrelated Editorial Intelligence files.
6. Run the smallest focused Curation tests needed to prove migrated Task 1–4 behavior still works. Fix migration conflicts if any; do not rerun ASR/Qwen/provider discovery just to verify migration.
7. Commit the migrated, verified Curation work as a real Git commit on `feat/curation-ui-v1` and push it. This gives Normal Chat a real diff to inspect.
8. Then continue immediately with the remaining approved implementation tasks. Do not stop after migration/push.

## Remaining implementation — execute continuously

### Task 5 — Professional project/curation API

Complete real end-to-end API behavior, including:
- project create/load/state;
- source video upload/registration flow needed by the professional product;
- run/curation hydration from real artifact data;
- ordered selection endpoint backed by `SelectionStore`;
- atomic `selection-plan.json` persistence;
- safe media route by `project_id + asset_id + variant` only;
- unknown asset => 404;
- candidate resolving outside approved roots => reject;
- no arbitrary browser-supplied filesystem path serving;
- reuse-first analyze adapter; no expensive upstream rerun merely to render/test UI.

Write behavior tests first. Passing compilation or a 200 on one route is not sufficient. Commit/push Task 5 when its focused behavior tests are green, then continue immediately.

### Task 6 — Professional `/curation` product

Replace the current debug/shell surface with a functioning user product, not token-only/static markup.

Must work end-to-end with Task 5 APIs:
- New Reel setup;
- drag/drop / Choose video;
- advanced local-path registration;
- actual source player + metadata;
- Use original audio / Replace guide audio controls prepared for Task 7;
- ANALYZE REEL action;
- timeline phrase rail with status and filters;
- active phrase content;
- max 3 real playable video candidate cards;
- max 4 real image thumbnails + lightbox;
- media inspection separate from selection;
- ordered mixed video+image selection tray;
- deterministic V2/V3/V4... assignment;
- reorder controls;
- mutually exclusive NO BROLL;
- autosave, Saving/Saved/Error+Retry state;
- refresh persistence by reloading the backend selection plan;
- CONFIRM PLAN validation state.

Tests must verify behavior/contracts, not only presence of strings such as `IntersectionObserver` or button labels. A token-presence test may supplement behavior tests but cannot be the completion proof.

Commit/push Task 6 when focused API/UI behavior tests are green, then continue immediately.

### Task 7 — Guide audio + reuse integration

Complete:
- source audio extraction/cache to mono 16 kHz PCM s16le guide audio;
- replacement external guide audio normalization;
- duration mismatch warning;
- guide-audio-aware ASR input while source-video timeline remains authoritative;
- source+guide signature reuse behavior;
- preserve existing upstream artifacts when unchanged.

Commit/push when focused tests are green, then continue immediately.

### Final acceptance

Use the existing KURA artifacts where valid; do not rerun expensive analysis solely for acceptance.

Prove:
- `/curation` opens as the professional product;
- source video flow works;
- guide audio flow works;
- real video/image candidate previews render when candidates exist;
- mixed video+image selection persists with V2/V3/V4 ordering;
- a different phrase can be NO BROLL;
- refresh/restart restores state;
- `selection-plan.json` path is known and valid;
- safe asset-id media routes are used;
- `/debug` still works;
- `resolve_calls=0`;
- standard runtime does not call GPT/OpenAI/Codex.

At the final gate run fresh full pytest + backend compileall once. Then push final branch state and report `TESTABLE=YES` with exact local URL and evidence.

## Execution contract

Execute continuously, task by task, using RED -> GREEN -> REFACTOR and a tiny local ledger. Do not end for progress reporting, migration completion, compilation-only success, one-route smoke success, WIP publication, or `BATCH_*` checkpoints. Stop only at a genuine user-action blocker or final `TESTABLE=YES`.
