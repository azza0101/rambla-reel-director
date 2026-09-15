# Dense Coverage + Vertical Social Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add dense visual-coverage guidance, stable local project reopening, and portrait vertical-social clip sourcing from YouTube Shorts plus best-effort TikTok/Instagram.

**Architecture:** Preserve the model-neutral imported visual plan. Extend retrieval with separate vertical-social providers that produce the same provider-neutral candidate contract as YouTube/Pexels, while keeping all final video cards as verified local clips. Persistence is fixed at the launcher/origin layer so existing on-disk projects and localStorage project IDs survive restarts without re-running ASR.

**Tech Stack:** FastAPI, Python 3.10/3.12, yt-dlp, httpx, FFmpeg, vanilla JS UI, PowerShell launcher.

**Spec:** `docs/superpowers/specs/2026-09-16-dense-coverage-vertical-social.md`

## Global Constraints
- `resolve_calls=0`.
- No OpenAI/GPT/Codex runtime dependency.
- No global Python/PATH/CUDA/ComfyUI changes.
- No browser cookies read automatically.
- No credentials in Git/logs/artifacts.
- Social providers fail independently.
- No merge to main.

---

### Task 1: Stable local project reopening + dense coverage contract

**Files:**
- Modify: `tools/start_curation_acceptance.ps1`
- Modify: `backend/app/editorial_import.py`
- Test: `tests/unit/test_editorial_import.py`
- Test: `tests/unit/test_curation_ui.py` or a new focused launcher-contract test if available.

**Interfaces:**
- Produces: stable acceptance origin `http://127.0.0.1:8765`.
- Produces: `visual_coverage_ratio(plan) -> float`.
- Produces: exported planner instructions requesting 90–98% `BROLL`/`CONTINUE_PREVIOUS_VISUAL` coverage.

- [ ] **Step 1: Write failing tests** for coverage ratio and dense-coverage instruction text.
- [ ] **Step 2: Verify tests fail** against current `editorial_import.py`.
- [ ] **Step 3: Implement** `visual_coverage_ratio()` and update `INSTRUCTIONS` without changing schema/validation semantics.
- [ ] **Step 4: Modify launcher** to stop the previous recorded acceptance process when safe and bind port 8765 deterministically; fail clearly if 8765 is occupied by an unrelated process.
- [ ] **Step 5: Run focused tests / PowerShell syntax checks** and commit.

### Task 2: Vertical-social provider layer

**Files:**
- Create: `backend/app/vertical_social.py`
- Modify: `backend/app/youtube_source.py`
- Modify: `backend/app/online_sourcing_cli.py`
- Test: `tests/unit/test_vertical_social.py`
- Test: `tests/unit/test_youtube_source.py`

**Interfaces:**
- `VerticalSocialSource.search(query, orientation, min_duration, max_duration, limit) -> list[RemoteCandidate-like]`
- Providers: `youtube_shorts`, `tiktok`, `instagram`.
- Final candidates retain provider, source page, duration, width/height, portrait orientation, thumbnail and bounded-window acquisition contract.

- [ ] **Step 1: Write failing tests** for DuckDuckGo result-link extraction, TikTok/Instagram URL filtering, portrait filtering, and YouTube Shorts provider identity.
- [ ] **Step 2: Verify tests fail** because providers do not exist.
- [ ] **Step 3: Implement** bounded public link discovery with `httpx` + stdlib HTML parsing; no new dependency.
- [ ] **Step 4: Implement** yt-dlp metadata probe for discovered public URLs and reject non-portrait/invalid-duration rows.
- [ ] **Step 5: Extend YouTube adapter** to accept a provider name so Shorts can share normalization/localization without masquerading as normal YouTube.
- [ ] **Step 6: Register** normal YouTube, YouTube Shorts, TikTok, Instagram and Pexels independently in `_real_engine()`.
- [ ] **Step 7: Run focused provider tests** and commit.

### Task 3: Clip localization compatibility + vertical shelf data

**Files:**
- Modify: `backend/app/quality_video.py`
- Modify: `backend/app/curation_artifacts.py`
- Modify: `backend/app/retrieval_diagnostics.py`
- Test: `tests/unit/test_retrieval_milestone.py`
- Test: `tests/unit/test_retrieval_diagnostics_states.py`

**Interfaces:**
- Generic bounded clip materializer accepts any yt-dlp-supported public source URL, not only YouTube.
- Vertical providers only yield selectable candidates if `orientation == portrait`, `preview_status == ready`, and `clip_verified == True`.

- [ ] **Step 1: Write failing tests** for TikTok/Instagram/Shorts provider classification and portrait-only final acceptance.
- [ ] **Step 2: Verify RED**.
- [ ] **Step 3: Generalize** `_youtube_clip` naming/usage to a social clip extractor while preserving cached range extraction.
- [ ] **Step 4: Add provider-specific diagnostics**; extraction failure becomes explicit and does not create discovery cards.
- [ ] **Step 5: Bump video retrieval contract version** so old artifacts are not mistaken for vertical-social results.
- [ ] **Step 6: Run focused retrieval tests** and commit.

### Task 4: Curation UI shelves + coverage indicator

**Files:**
- Modify: `backend/app/debug_server.py`
- Modify: `backend/app/curation_ui.py`
- Test: `tests/unit/test_curation_ui.py`
- Test: `tests/editorial_controller_test.cjs`

**Interfaces:**
- Curation payload exposes `visual_coverage_ratio` and vertical-provider assets using existing candidate fields.
- UI shelves: `VERTICAL SOCIAL`, `YOUTUBE / REPERTORY`, `STOCK / PEXELS`, `IMAGE SUGGESTIONS`.

- [ ] **Step 1: Write failing controller/UI assertions** for the vertical shelf and coverage percentage.
- [ ] **Step 2: Verify RED**.
- [ ] **Step 3: Add payload coverage ratio** computed from imported plan.
- [ ] **Step 4: Add vertical shelf** filtered to `youtube_shorts|tiktok|instagram` and portrait orientation; keep normal YouTube and Pexels shelves independent.
- [ ] **Step 5: Show provider labels, portrait marker, source range, and explicit empty/provider-error states.**
- [ ] **Step 6: Run JS/Python focused tests** and commit.

### Task 5: End-to-end verification and publication

**Files:**
- Update: `docs/GENERAL_PURPOSE_CURATOR_STATUS.md` or a new status note if appropriate.

- [ ] **Step 1: Run focused unit tests** for editorial import, vertical social, retrieval, curation UI and launcher helpers.
- [ ] **Step 2: Run full project tests and compileall** in the existing approved runtimes; do not install anything.
- [ ] **Step 3: Run local KURA acceptance** reusing the existing transcript/imported plan; verify Analyze returns reused.
- [ ] **Step 4: Verify at least one real YouTube Shorts provider attempt and playable portrait clip where the provider returns a usable result; record TikTok/Instagram real attempts or explicit extraction/provider errors.**
- [ ] **Step 5: Restart launcher and prove the same project reopens on 127.0.0.1:8765 without ASR rerun.**
- [ ] **Step 6: Fast-forward `feat/curation-ui-v1` only after verification, then report exact SHA/launcher and `resolve_calls=0`.**