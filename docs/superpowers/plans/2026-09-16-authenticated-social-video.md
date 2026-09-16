# Authenticated Social Video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent authenticated TikTok/Instagram discovery and graceful preview/link fallback so RAMBLA keeps useful social/news video candidates even when automatic download fails.

**Architecture:** Add a CPU-only browser-profile layer, browser-backed social source adapters, authenticated yt-dlp acquisition fallback, and an additive candidate/UI contract for `CLIP_READY`, `PREVIEW_ONLY`, and `MANUAL_LINK`. Existing public-web discovery remains fallback; only verified local clips remain selectable.

**Tech Stack:** Python 3.12, FastAPI, Playwright Python, yt-dlp, httpx, existing RAMBLA sourcing/Qwen/curation stack.

**Spec:** `docs/superpowers/specs/2026-09-16-authenticated-social-video-design.md`

## Global Constraints

- Dedicated RAMBLA browser profiles only; never automate the user's normal Chrome/Edge profile.
- Never persist or log username/password/2FA/cookie values.
- Social discovery/acquisition must work without GPU/Qwen loaded.
- Download failure must preserve a visible candidate with source link.
- Only verified local video clips are selectable final B-roll.
- Existing projects open without Analyze rerun.
- Resolve remains frozen: `resolve_calls = 0`.

---

### Task 1: Persistent browser profile manager

**Files:**
- Create: `backend/app/browser_profiles.py`
- Test: `tests/unit/test_browser_profiles.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: `BrowserProfileConfig`, `BrowserProfileManager`, `profile_dir(provider)`, `open_login(provider, start_url)`, `run_in_profile(provider, callback)`.
- Depends on: Playwright persistent contexts and `RAMBLA_BROWSER_PROFILE_ROOT`.

- [ ] **Step 1: Write failing unit tests**

Cover deterministic provider directories, rejection of unsupported provider names, no password/token fields, serialization of concurrent profile access, and injectable fake Playwright launcher.

- [ ] **Step 2: Run focused test and verify RED**

Run: `pytest -q tests/unit/test_browser_profiles.py`
Expected: import/module failures.

- [ ] **Step 3: Add Playwright dependency and minimal manager**

Use `playwright>=1.54,<2` in project dependencies. `BrowserProfileManager` must accept an injected launcher for tests and default to headed Chromium persistent context with a dedicated `user_data_dir`.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `pytest -q tests/unit/test_browser_profiles.py`
Expected: pass.

- [ ] **Step 5: Commit**

Commit message: `feat: add persistent social browser profiles`

---

### Task 2: Browser-backed TikTok and Instagram discovery

**Files:**
- Create: `backend/app/social_browser_source.py`
- Modify: `backend/app/vertical_social.py`
- Test: `tests/unit/test_social_browser_source.py`
- Test: `tests/unit/test_vertical_social.py`

**Interfaces:**
- Consumes: `BrowserProfileManager.run_in_profile(provider, callback)`.
- Produces: `BrowserSocialSource(provider, profile_manager)` implementing the same async `search(...) -> list[VerticalRemoteCandidate]` shape as current vertical sources.
- Adds helper: `extract_social_result_links(provider, anchors)` with canonical URL parsing.

- [ ] **Step 1: Write failing extraction/source tests**

Use fake page/context objects. Verify TikTok `/@user/video/id` and Instagram `/reel/code/` canonicalization, bounded scrolls, dedupe, rank preservation, authentication-required diagnostics, and fallback to existing public-web source when browser discovery fails.

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest -q tests/unit/test_social_browser_source.py tests/unit/test_vertical_social.py`

- [ ] **Step 3: Implement browser source adapter**

TikTok search URL: `https://www.tiktok.com/search/video?q=<query>`.
Instagram search starts at `https://www.instagram.com/explore/search/keyword/?q=<query>` and extracts only Reel URLs; when no usable browser hits are found, retain existing public-web discovery as fallback.

Use DOM attributes/links, not coordinates. Bound scrolling and waits. Do not inspect or store password fields.

- [ ] **Step 4: Wire default vertical sources**

When `RAMBLA_ENABLE_SOCIAL_BROWSER=1`, prepend browser-backed TikTok and Instagram sources before public-web fallbacks. Keep YouTube Shorts and all old sources operational.

- [ ] **Step 5: Run tests and commit**

Run: `pytest -q tests/unit/test_social_browser_source.py tests/unit/test_vertical_social.py tests/unit/test_vertical_social_style_v2.py`
Commit message: `feat: add authenticated social discovery`

---

### Task 3: Acquisition-state contract and authenticated yt-dlp fallback

**Files:**
- Modify: `backend/app/quality_video.py`
- Modify: `backend/app/curation.py`
- Modify: `backend/app/curation_artifacts.py`
- Create: `backend/app/social_acquisition.py`
- Test: `tests/unit/test_social_acquisition.py`
- Test: `tests/unit/test_retrieval_quality.py`
- Test: `tests/unit/test_curation.py`

**Interfaces:**
- Produces: `SocialAcquisitionResult(acquisition_state, preview_path, poster_path, manual_reason, source_page, ...)`.
- Produces: `acquire_social_candidate(candidate, profile_dir, user_agent, ...)`.
- Candidate states: `CLIP_READY`, `PREVIEW_ONLY`, `MANUAL_LINK`.

- [ ] **Step 1: Write failing tests**

Cases: yt-dlp authenticated success -> `CLIP_READY`; yt-dlp failure + thumbnail -> `PREVIEW_ONLY`; no local preview but source URL -> `MANUAL_LINK`; cookie/profile command arguments are redacted from errors/log strings; preview/manual candidates remain non-selectable.

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest -q tests/unit/test_social_acquisition.py tests/unit/test_curation.py`

- [ ] **Step 3: Implement authenticated acquisition helper**

Use yt-dlp cookie loading from the dedicated profile path only. Never write a cookie export file into the repo or project. Return structured failure codes rather than throwing provider-wide failures.

- [ ] **Step 4: Update `quality_video.source_video_beat`**

For TikTok/Instagram, preserve discovery candidates after clip failure as preview/manual rows. Qwen may rank their poster/thumbnail metadata, but `clip_verified=False` and `selectable=False`. Verified portrait local clips remain the only `CLIP_READY` rows.

- [ ] **Step 5: Update curation artifact mapping**

Expose `acquisition_state`, `manual_reason`, `source_page`, remote preview URL and selectability to the API/UI candidate model.

- [ ] **Step 6: Run tests and commit**

Run: `pytest -q tests/unit/test_social_acquisition.py tests/unit/test_retrieval_quality.py tests/unit/test_curation.py tests/unit/test_curation_product_v2.py`
Commit message: `feat: preserve social preview and manual candidates`

---

### Task 4: Social login API and provider diagnostics

**Files:**
- Modify: `backend/app/curation_server.py`
- Test: `tests/unit/test_social_login_api.py`
- Modify: `backend/app/project_config.py` if provider flags need surfacing.

**Interfaces:**
- Adds: `POST /api/curation/social/{provider}/login` for `tiktok|instagram`.
- Adds: `GET /api/curation/social/status`.
- Login endpoint launches the provider browser profile and returns immediately with structured status; no Analyze/ASR/Qwen/Resolve.

- [ ] **Step 1: Write failing API tests**

Inject fake `BrowserProfileManager`. Verify allowed providers, no credentials accepted, login route calls headed profile open, status exposes profile readiness but no cookie/path secrets, and `resolve_calls=0`.

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest -q tests/unit/test_social_login_api.py`

- [ ] **Step 3: Implement endpoints and dependency injection**

Keep browser launch injectable for CI and never launch a real browser during tests.

- [ ] **Step 4: Run tests and commit**

Run: `pytest -q tests/unit/test_social_login_api.py tests/unit/test_project_maintenance_api.py`
Commit message: `feat: expose social browser login controls`

---

### Task 5: Curation UI provider shelves and fallback cards

**Files:**
- Modify: `backend/app/curation_ui_v2.py`
- Test: `tests/unit/test_curation_management_ui.py`
- Create or modify: `tests/unit/test_social_curation_ui.py`

**Interfaces:**
- UI consumes candidate `provider`, `acquisition_state`, `selectable`, `preview_url`, `source_page`, `manual_reason`.
- Adds controls: `TIKTOK LOGIN`, `INSTAGRAM LOGIN`.
- Provider shelves: `TIKTOK`, `INSTAGRAM REELS`, `YOUTUBE SHORTS`, `WEB / NEWS VIDEO`, existing general/stock/images.

- [ ] **Step 1: Write failing HTML/JS contract tests**

Verify provider shelf labels, login buttons, `CLIP READY/PREVIEW/MANUAL` badges, `OPEN SOURCE`, non-selectable manual cards, and no `startStage('analyze')` in login functions.

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest -q tests/unit/test_social_curation_ui.py tests/unit/test_curation_management_ui.py`

- [ ] **Step 3: Implement UI**

Cards with remote thumbnail still render when local media is absent. Login calls only the new social login endpoint. Show provider-local failure messages in diagnostics.

- [ ] **Step 4: Run focused tests and commit**

Run: `pytest -q tests/unit/test_social_curation_ui.py tests/unit/test_curation_management_ui.py tests/unit/test_curation_product_v2.py`
Commit message: `feat: add social source shelves and login UI`

---

### Task 6: CI and launcher integration

**Files:**
- Modify: `.github/workflows/online-sourcing-tests.yml`
- Modify: `tools/start_curation_acceptance.ps1`
- Test: existing launcher/product contract tests plus new static tests as needed.

**Interfaces:**
- Launcher sets `RAMBLA_ENABLE_SOCIAL_BROWSER=1` and a dedicated `RAMBLA_BROWSER_PROFILE_ROOT` outside project folders.
- CI installs Playwright Python package but does not download/run Chromium; browser integration stays fake-injected in unit tests.

- [ ] **Step 1: Add new focused tests to workflow**

Include browser profile, browser source, social acquisition, login API and UI test files.

- [ ] **Step 2: Update launcher environment**

Set browser-profile root under `Z:\APP REEL TEST\qwen-embedding-smoke\browser-profiles` unless already overridden.

- [ ] **Step 3: Run final verification**

Run focused workflow equivalent, embedded UI `node --check`, and `python -m compileall backend`.
Expected: all pass, no browser/GPU required.

- [ ] **Step 4: Commit**

Commit message: `test: verify authenticated social video workflow`
