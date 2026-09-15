# RAMBLA Project Memory

Updated: 2026-09-15
Canonical live handoff: Issue #3

## Product goal

RAMBLA Reel Director is a local-first reel editing system. The backend should analyze a talking-head/source video, build a complete timed transcript, split it into coherent short semantic phrases, decide where visual coverage is useful, discover strong online evidence/B-roll, let the editor review/curate it, and later apply a frozen Edit Plan to a duplicate DaVinci Resolve timeline.

The intended mutation flow is:

`ANALYZE -> complete Edit Plan -> REVIEW -> APPLY`

Resolve remains a thin client/panel. The heavy work stays in the local RAMBLA backend: ASR, semantic planning, sourcing, Qwen ranking, cache, bounded downloads, scene localization, preview generation, curation and Edit Plan generation.

## Editorial principles

- Exact evidence / exact subject / exact event / exact post / interview / article beats generic semantic stock.
- Source priority: `EXACT_RECEIPT -> EXACT_ENTITY_EVENT -> SOURCE_NATIVE_SOCIAL -> ARCHIVAL_REPERTORY -> PRODUCT_UI_DEMO -> CULTURAL_REFERENCE -> CLOSE_SEMANTIC_EDITORIAL -> GENERIC_STOCK`.
- Landscape/square media are allowed when composition/crop works in 9:16.
- A successful visual slot should normally have at least two meaningfully different proposals; otherwise search more source classes and, if quality is still insufficient, use explicit `NO_BROLL_QUALITY_FLOOR` rather than filler.
- Factanza-like evidence/editorial and Olimpia-like social/kinetic are separate StyleDNA fingerprints, not averaged into one style.

Reference pacing already measured:
- Factanza: evidence/editorial, roughly 3-5s major visual changes, speaker persists more often, overlays/splits/source screenshots.
- Olimpia: social/kinetic, roughly 0.8-2.5s changes, more replacement cuts/social-native source texture.

## Transcript / chunking

Canonical transcript architecture:

`complete timed ASR -> punctuation/sentence repair -> coherent semantic phrases -> coverage slots -> candidate shelf`

Current phrase target is approximately 3-4s maximum. Previous 82.28s smoke was rebuilt into 28 semantic phrases with max 3.84s while preserving all words exactly once and keeping sentence-ending punctuation as a hard boundary.

## Current local stack

- GPU context: RTX 4090 available for tests.
- Local Qwen visual embedding model already tested: `Qwen3-VL-Embedding-2B` under the approved `Z:\APP REEL TEST\qwen-embedding-smoke` runtime area.
- ASR: `faster-whisper==1.2.1`, multilingual `large-v3-turbo`, cached under the approved RAMBLA test root.
- CUDA/float16 faster-whisper attempt hit a local Windows runtime/DLL issue; current working ASR fallback is CPU/int8. No global PATH/CUDA/system mutation was made.
- Standard runtime should not require GPT/OpenAI calls. Local Whisper/Qwen/FFmpeg/FastAPI/cache plus provider APIs/search are sufficient. Provider quotas are separate from GPT/Codex/Work usage.

## KURA real smoke status

Input (read-only):
`Z:\APP REEL TEST\VIDEO BASE\KURA_Finto etico_draft 1.mp4`

Output root:
`Z:\APP REEL TEST\qwen-embedding-smoke\kura-finto-etico-smoke\run`

Current real KURA checkpoint:
- duration probed: ~102.25s;
- ASR: 23 segments, 324 words;
- semantic phrases/chunks: 27, <=4s;
- final discovery run: 27 coverage slots, 46 candidates, 24 proposals;
- selected/downloaded final media in that smoke: 0;
- 12 preview/runtime failures were retained in artifacts and reduced proposal coverage;
- `review.html` exists;
- `edit-plan.json` exists;
- `resolve_calls=0`;
- Resolve and ComfyUI untouched.

Current local Debug Runner entrypoint:
`http://127.0.0.1:8765/debug`

Local command profile:
`Z:\APP REEL TEST\qwen-embedding-smoke\debug-runner-command.json`

Known user-facing artifacts:
- `Z:\APP REEL TEST\qwen-embedding-smoke\kura-finto-etico-smoke\run\review.html`
- `Z:\APP REEL TEST\qwen-embedding-smoke\kura-finto-etico-smoke\run\edit-plan.json`

Important: the latest Debug Runner/ASR integration changes were still local/uncommitted at the last checkpoint. Local working HEAD reported `91c2135`; remote `feat/editorial-intelligence-style-dna-v1` was still at `307df4ed631f6ae240ca48da26c26ccac81a3f89`. Preserve local work; do not reset/clean it.

## Debug Runner architecture

Existing runner is a local FastAPI server with SSE/live progress. It tracks stages such as prepare, ASR, semantic chunking, coverage, evidence intent, source strategy, online search, Qwen coarse/final, bounded acquisition, Edit Plan and review. It is explicitly separated from Resolve.

Support branch already exists:
`support/debug-runner-v1`

Important files from that support branch include:
- `backend/app/debug_server.py`
- `tests/test_debug_server.py`
- `tools/start_rambla_debug_runner.ps1`
- `docs/RAMBLA_DEBUG_RUNNER.md`

## Provider strategy

Primary test priority is YouTube / YouTube Shorts. Pexels is optional/fallback and must never gate the runner.

Long-video strategy:
- coarse storyboard / scene evidence first;
- localize a short useful source window;
- use bounded partial acquisition (roughly 3-4s plus padding) rather than whole-video download where practical;
- still/screenshot fallback when static evidence is enough.

Pexels credential handling:
- a credential exists out-of-band;
- NEVER commit, log, print, persist or copy its value into GitHub, artifacts, `CURRENT_STATE.md`, command profiles or review HTML;
- read only from environment variable `PEXELS_API_KEY` when present.

## Codex / execution mode

Canonical coordination channel:
Issue #3 — `RAMBLA live handoff — NORMAL CHAT <-> Codex`.

Convention:
- a single `.` in Normal Chat means sync the latest Issue #3 handoff and inspect relevant branch/PR/CI;
- Codex should post concise substantive HANDOFFs only.

LOW-CREDIT mode is the default:
- single worker only;
- no routine delegated reviewer/subagent;
- Normal Chat acts as external reviewer/orchestrator;
- read only relevant files/plan sections;
- focused tests during development;
- full pytest + compileall only at meaningful checkpoint/completion;
- reuse ASR/Qwen/provider/FFmpeg caches and artifacts;
- dedupe queries/provider calls;
- no repeated whole-Issue rereads;
- no >5 GiB single download without explicit user approval;
- no merge to `main` autonomously.

## Codex Desktop permissions / Windows sandbox

Current intended unattended setup:
- `approval_policy = "never"`;
- `approvals_reviewer = "user"` in config where applicable;
- `sandbox_mode = "workspace-write"`;
- network enabled for RAMBLA sourcing/Git work;
- `[windows] sandbox = "unelevated"` to bypass the Windows elevated ACL/setup-refresh regression.

A previous custom `default_permissions = "rambla-autonomous"` setup caused/covered a Windows sandbox helper initialization failure (`helper_unknown_error: setup refresh had errors`) before `AGENTS.md` could load. Do not return to that profile on this machine unless separately revalidated.

Do not recommend Full Access.

## Curation UI V1 — APPROVED

The user approved a new human-in-the-loop V1 where RAMBLA becomes a curation assistant before full autonomous editing.

For every semantic phrase/chunk, the UI should show:
- up to 3 real video candidates;
- up to 4 real image candidates;
- real visual previews, not only links;
- multi-select;
- explicit `NO_BROLL`.

Video preview UX:
- lightweight local MP4/WebM loop, ~1.5-3s;
- poster immediately visible;
- muted;
- lazy-loaded;
- hover/focus playback rather than page-wide autoplay;
- cached by stable source/window/settings key.

Image UX:
- real thumbnail;
- click/lightbox;
- provider/source/provenance preserved.

Selection semantics:
- one asset -> V2;
- multiple assets for the same phrase -> stacked V2, V3, V4... in stable selection order;
- base speaker video conceptually remains on V1;
- `NO_BROLL` is mutually exclusive with selected visuals.

New artifact:
`selection-plan.json`

It must preserve chunk timing, selected asset metadata, local materialized path when available, source/provenance/rights, stable selection order and stacked track assignment.

Runtime rule:
- standard use must not require GPT/OpenAI credits;
- full-resolution acquisition only after user selection (or if already required by existing finalist verification);
- broken previews fail per-card, not per-page/run.

Modern GUI direction:
- dark neutral, polished and visual;
- sticky top toolbar;
- phrase cards in transcript order;
- filters like All / Selected / Needs choice / NO_BROLL / Errors;
- big visual shelves for VIDEO and IMMAGINI;
- clear selected state via border/check overlay;
- local autosave;
- lightbox/player for inspection;
- existing technical `/debug` page remains available.

## Curation UI V1 design + plan

Design branch:
`design/curation-ui-v1`

Approved design:
`docs/superpowers/specs/2026-09-15-curation-ui-v1-design.md`

Implementation plan:
`docs/superpowers/plans/2026-09-15-curation-ui-v1.md`

Latest plan commit after self-review:
`532215059f47202f26f69103801fa865b3ac9cb3`

The user explicitly approved both the design (`approvo`) and the implementation plan (`APPROVO PIANO`). Execution is therefore authorized, but implementation should begin only after preserving/checkpointing the current local Debug Runner/KURA work so it is not lost.

Planned implementation sequence:
1. provider-neutral curation contracts + 3 video / 4 image shelf;
2. image discovery adapters (credentialless Wikimedia + optional Pexels photo source; room for Bing/image-search adapter later);
3. lightweight cached real preview materialization with per-card failure isolation;
4. hydration of curation data from existing KURA artifacts without rerunning expensive stages;
5. selection persistence + deterministic `selection-plan.json` stacked track mapping;
6. modern FastAPI curation page/API with real thumbnails/looping video previews, filters, lightbox and local autosave;
7. smoke using existing KURA artifacts first, with focused tests and no unnecessary ASR/provider/Qwen reruns.

## Hard safety boundaries

- Never modify `REEL_MASTER`; future Apply must target a duplicate timeline only.
- No Resolve mutation during analysis/reasoning/review.
- No ComfyUI mutation.
- No global Python/system/CUDA/PATH mutation.
- No credentials committed or echoed.
- No user media moved/renamed/deleted.
- No merge to `main` without explicit user authorization.
- Keep client isolation and provenance/rights metadata first-class.
