# RAMBLA Professional Curation UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans in single-agent sequential mode. Do not spawn routine subagents/reviewers; Normal Chat is the external reviewer. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current debug-style curation surface with a professional local application that starts from a source video/audio guide and provides real video + image curation, ordered multi-selection, NO BROLL, autosave, and deterministic V2/V3/V4 selection planning.

**Architecture:** Keep the existing RAMBLA analysis engine and `/debug` runner intact. Add focused project/media, preview, selection, hydration and API units, then rebuild `/curation` as the professional product. Browser uploads stay local-only; source-path registration remains available for large existing files. All media serving is asset-id based and reuse-first.

**Tech Stack:** Python 3.13, FastAPI, Pydantic/dataclasses, stdlib pathlib/json/hashlib/subprocess, httpx, FFmpeg/ffprobe, existing faster-whisper/Qwen runtime, vanilla HTML/CSS/JavaScript.

**Spec:** `docs/superpowers/specs/2026-09-15-curation-ui-professional-redesign.md`

## Global Constraints

- This plan supersedes conflicting UI/API behavior in `docs/superpowers/plans/2026-09-15-curation-ui-v1.md`.
- Work on `feat/curation-ui-v1`; preserve existing useful commits/history, but replace incorrect product/UI contracts rather than patching around them.
- `/debug` remains developer-facing and must continue to work.
- `/curation` is the professional user surface.
- Standard runtime requires no GPT/OpenAI/Codex call.
- Resolve remains frozen; `resolve_calls=0` is mandatory.
- No ComfyUI, global Python, PATH/CUDA or unrelated system mutation.
- Source media is read-only after registration.
- Browser upload is local-only and must not require a cloud service.
- Do not expose or accept arbitrary filesystem paths in media-serving URLs.
- Maximum shelf caps remain 3 video + 4 images; never invent filler.
- Ordered multi-selection maps deterministically to V2/V3/V4….
- NO BROLL is mutually exclusive with visual selections.
- Full-resolution acquisition remains deferred until selection where possible.
- Reuse existing KURA transcript/chunks/candidates/edit-plan; do not rerun expensive upstream stages merely to exercise the UI.
- LOW-CREDIT execution: focused tests per task, one full suite + compileall at completion.

---

### Task 1: Project/source-video and guide-audio domain

**Files:**
- Create: `backend/app/curation_project.py`
- Test: `tests/unit/test_curation_project.py`

**Interfaces:**
- Produces `CurationProject`, `SourceVideoInfo`, `GuideAudioInfo`.
- Produces `ProjectStore.create()`, `ProjectStore.load()`, `ProjectStore.register_local_video()`, `ProjectStore.write_uploaded_video()`, `ProjectStore.extract_source_audio()`, `ProjectStore.write_external_guide_audio()`.
- Uses injected `probe_runner`/`command_runner` so tests never require real FFmpeg.

- [ ] **Step 1: Write failing tests for project creation and local-video registration**

```python
from pathlib import Path
from backend.app.curation_project import ProjectStore


def test_register_local_video_keeps_source_read_only_and_persists_metadata(tmp_path):
    source = tmp_path / "input.mp4"
    source.write_bytes(b"video")
    store = ProjectStore(tmp_path / "projects", probe_runner=lambda p: {
        "duration": 12.5, "fps": 25.0, "width": 1920, "height": 1080, "has_audio": True,
    })
    project = store.create("Demo")
    updated = store.register_local_video(project.project_id, source)
    assert updated.source_video.path == str(source.resolve())
    assert updated.source_video.duration == 12.5
    assert updated.source_video.has_audio is True
    assert source.read_bytes() == b"video"
```

- [ ] **Step 2: Write failing tests for browser-upload storage**

Expose a pure store method that accepts an iterator of byte chunks and writes atomically under `<project>/source/`. Assert filename sanitization, max-size enforcement using the existing 5 GiB boundary, and source metadata persistence.

- [ ] **Step 3: Write failing tests for original-audio extraction cache**

```python
def test_source_audio_extracts_once_and_reuses_signature(tmp_path):
    calls = []
    def runner(cmd):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"wav")
    # create/register project using fake probe
    first = store.extract_source_audio(project.project_id, command_runner=runner)
    second = store.extract_source_audio(project.project_id, command_runner=runner)
    assert first.path == second.path
    assert len(calls) == 1
```

Assert exact FFmpeg normalization: mono, 16 kHz, PCM s16le.

- [ ] **Step 4: Implement project JSON persistence and source signature**

Store under:

```text
<projects-root>/<project-id>/project.json
<projects-root>/<project-id>/source/
<projects-root>/<project-id>/run/
```

`project.json` must not contain secrets. Source signature includes canonical path or uploaded file path + size + mtime_ns.

- [ ] **Step 5: Implement external guide-audio normalization**

Write upload bytes under project source, then normalize to `guide-audio.wav`. Persist mode=`external`. Do not time-stretch; persist a duration mismatch warning when absolute difference from video duration is greater than 0.25 s.

- [ ] **Step 6: Verify and commit**

Run:

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/unit/test_curation_project.py -q
```

Commit:

```powershell
git add backend/app/curation_project.py tests/unit/test_curation_project.py
git commit -m "feat: add curation project media model"
```

---

### Task 2: Correct ordered multi-selection and selection-plan persistence

**Files:**
- Create: `backend/app/curation_selection.py`
- Test: `tests/unit/test_curation_selection.py`

**Interfaces:**
- Produces `SelectionStore(output_dir, candidate_index, chunk_ranges)`.
- Produces `set_chunk_selection(chunk_id, asset_ids, *, no_broll)` and `load()`.
- Writes `<run>/selection-plan.json` atomically.

- [ ] **Step 1: Write failing mixed-media multi-select test**

```python
store.set_chunk_selection("chunk-1", ["video-a", "image-c", "video-b"], no_broll=False)
rows = store.load()["chunks"]["chunk-1"]["selected_assets"]
assert [(x["asset_id"], x["track"], x["order"]) for x in rows] == [
    ("video-a", "V2", 0), ("image-c", "V3", 1), ("video-b", "V4", 2)
]
```

- [ ] **Step 2: Write failing tests for reorder, refresh persistence and NO BROLL exclusivity**

Require unknown/cross-chunk assets to fail. Require duplicates to be removed preserving first occurrence.

- [ ] **Step 3: Implement atomic store**

Canonical request data is list-based, never `dict[chunk] -> string`.

- [ ] **Step 4: Verify and commit**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/unit/test_curation_selection.py -q
git add backend/app/curation_selection.py tests/unit/test_curation_selection.py
git commit -m "feat: persist ordered curation selections"
```

---

### Task 3: Real lightweight previews and asset-id media index

**Files:**
- Create: `backend/app/curation_preview.py`
- Modify: `backend/app/curation.py`
- Test: `tests/unit/test_curation_preview.py`
- Modify: `tests/unit/test_curation.py`

**Interfaces:**
- Produces `PreviewResult` and `CurationPreviewMaterializer.materialize()` / `materialize_batch()`.
- Extends `CurationCandidate` with safe preview/poster metadata used by hydration/API.

- [ ] **Step 1: Write failing cache and video-preview tests**

Assert first materialization cache miss, second cache hit, exact preview path reuse, poster creation, and FFmpeg flags `-t 2.2`, width 480, `-an`, `libx264`, `+faststart`.

- [ ] **Step 2: Write failing image-thumbnail test**

Fetch only thumbnail bytes; enforce 8 MiB limit; materialize a local thumbnail path; do not fetch full image.

- [ ] **Step 3: Write failing batch-isolation test**

One broken candidate returns `status="error"` / sanitized `preview_unavailable`; healthy candidates remain `ready`.

- [ ] **Step 4: Implement stable cache key**

Hash candidate id + kind + source page + rounded source range + preview version. Store under `<project-or-run-cache>/curation-previews/`.

- [ ] **Step 5: Implement video preview/poster and image thumbnail materialization**

Reuse existing local bounded MP4 when available. Do not full-download unselected remote media unless the existing bounded verification path already requires it.

- [ ] **Step 6: Bound concurrency to 4, verify and commit**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/unit/test_curation_preview.py tests/unit/test_curation.py -q
git add backend/app/curation_preview.py backend/app/curation.py tests/unit/test_curation_preview.py tests/unit/test_curation.py
git commit -m "feat: materialize real curation previews"
```

---

### Task 4: Artifact hydration with real video + image shelves

**Files:**
- Create: `backend/app/curation_artifacts.py`
- Test: `tests/unit/test_curation_artifacts.py`

**Interfaces:**
- Produces `CurationRunView`, `CurationChunkView`, `load_curation_run(project_or_run_dir)`.
- Builds an `asset_id -> CurationCandidate` index.

- [ ] **Step 1: Write failing fixtures for existing KURA artifact names**

Cover:

```text
semantic-chunks.json / semantic-beats.json
online-candidates.json / candidate-metrics.json
image-candidates.json
edit-plan.json
coverage-metrics.json
selection-plan.json
```

- [ ] **Step 2: Assert 3-video / 4-image caps and real separation**

```python
run = load_curation_run(tmp_path)
chunk = run.chunks[0]
assert len(chunk.video_candidates) <= 3
assert len(chunk.image_candidates) <= 4
assert all(x.kind == "video" for x in chunk.video_candidates)
assert all(x.kind == "image" for x in chunk.image_candidates)
```

Video thumbnails must never be misclassified as image candidates.

- [ ] **Step 3: Assert image rows retain thumbnail/full/source metadata**

Hydration must provide enough information for Task 3 preview materialization. Malformed candidates are appended to `errors` without aborting the whole run.

- [ ] **Step 4: Implement and commit**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/unit/test_curation_artifacts.py -q
git add backend/app/curation_artifacts.py tests/unit/test_curation_artifacts.py
git commit -m "feat: hydrate professional curation shelves"
```

---

### Task 5: Professional project/curation API and safe media routes

**Files:**
- Create: `backend/app/curation_api.py`
- Modify: `backend/app/debug_server.py`
- Test: `tests/test_curation_api.py`
- Modify: `tests/test_debug_server.py`

**Interfaces:**
- Mounts a FastAPI router onto the existing local app.
- Existing `/debug` routes remain intact.

- [ ] **Step 1: Write failing project API tests**

Required contracts:

```text
POST /api/curation/projects
POST /api/curation/projects/{id}/source/local-path
PUT  /api/curation/projects/{id}/source/upload?filename=...
POST /api/curation/projects/{id}/guide/source-audio
PUT  /api/curation/projects/{id}/guide/upload?filename=...
POST /api/curation/projects/{id}/analyze
GET  /api/curation/projects/{id}
GET  /api/curation/projects/{id}/run
POST /api/curation/projects/{id}/selection
GET  /api/curation/projects/{id}/selection-plan
GET  /api/curation/projects/{id}/media/{asset_id}/{variant}
```

For upload use `Request.stream()` and raw bytes so multipart is not required solely for this feature.

- [ ] **Step 2: Write failing selection API test**

```python
response = client.post(f"/api/curation/projects/{pid}/selection", json={
    "chunk_id": "chunk-1",
    "asset_ids": ["video-a", "image-c"],
    "no_broll": False,
})
assert [x["track"] for x in response.json()["selected_assets"]] == ["V2", "V3"]
```

- [ ] **Step 3: Write media security tests**

No query/path parameter may serve arbitrary filesystem paths. Unknown asset id => 404. Candidate preview outside approved roots => 403.

- [ ] **Step 4: Implement analysis reuse adapter**

`POST .../analyze` must start/reuse the existing `debug_run_cli` pipeline with project source video and project run directory. If transcript/chunks/candidates/edit plan already match source signature, reuse them; only missing image discovery/previews may run.

- [ ] **Step 5: Keep legacy `/api/curation/media?path=...` off the professional surface**

Remove it or retain only behind debug compatibility if existing tests require it; `/curation` must never generate that URL.

- [ ] **Step 6: Verify and commit**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_curation_api.py tests/test_debug_server.py -q
git add backend/app/curation_api.py backend/app/debug_server.py tests/test_curation_api.py tests/test_debug_server.py
git commit -m "feat: expose professional curation API"
```

---

### Task 6: Replace the current HTML with the professional product shell

**Files:**
- Rewrite: `backend/app/curation_ui.py`
- Test: `tests/unit/test_curation_ui.py`

**Interfaces:**
- Produces `render_curation_page() -> str`.
- Calls only Task 5 professional APIs.

- [ ] **Step 1: Write failing product-shell HTML tests**

Require these visible/product tokens:

```python
html = render_curation_page()
for token in (
    "New Reel", "Choose video", "Use original audio", "Replace guide audio",
    "ANALYZE REEL", 'id="phrase-list"', 'id="video-shelf"', 'id="image-shelf"',
    'id="selection-tray"', "NO BROLL", "CONFIRM PLAN", "IntersectionObserver",
):
    assert token in html
assert "/api/curation/media?path=" not in html
assert "cdn.jsdelivr.net" not in html
assert "unpkg.com" not in html
```

- [ ] **Step 2: Implement setup screen**

Provide drag/drop + file picker, advanced local-path registration, real local source-video player, metadata row, original-audio toggle, external guide control, and Analyze CTA.

No raw output-dir/path field in the normal UI.

- [ ] **Step 3: Implement professional workspace layout**

Desktop layout:

```text
left phrase rail | center active phrase/media | right selection tray
```

Top bar: project/source, curated count, filters, save status, Confirm Plan.

Use restrained dark neutral visual language; large media; no debug metrics/log windows.

- [ ] **Step 4: Implement real video cards**

Generate `<video muted loop playsinline preload="none">` with poster and `data-preview-src`. IntersectionObserver attaches source. Hover/focus play; leave/blur pause + seek to zero.

Media-body click opens inspector/lightbox; selection checkbox/button is a separate control with event propagation stopped.

- [ ] **Step 5: Implement real image cards/lightbox**

Use actual thumbnail `img` URLs. Separate selection control. Lightbox shows large preview and source metadata.

- [ ] **Step 6: Implement ordered multi-select tray and NO BROLL**

UI state per chunk is `asset_ids[] + no_broll`. Show V2/V3/V4 chips. Up/down controls reorder and immediately autosave.

- [ ] **Step 7: Implement autosave state and retry**

Header cycles `Saving...` -> `Saved`; failure keeps local state and exposes Retry.

- [ ] **Step 8: Implement filters and phrase progress**

All / Needs choice / Selected / NO BROLL / Errors. Show curated count.

- [ ] **Step 9: Verify and commit**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/unit/test_curation_ui.py tests/test_curation_api.py -q
git add backend/app/curation_ui.py tests/unit/test_curation_ui.py
git commit -m "feat: rebuild professional curation workspace"
```

---

### Task 7: Guide-audio-aware analysis and professional entrypoint

**Files:**
- Modify: `backend/app/debug_run_cli.py`
- Modify: `backend/app/curation_api.py`
- Modify: `docs/RAMBLA_DEBUG_RUNNER.md`
- Test: `tests/test_debug_run_cli.py`
- Modify: `tests/test_curation_api.py`

**Interfaces:**
- Existing raw-video CLI remains compatible.
- Project analysis may pass/use normalized guide audio for ASR while timeline remains based on source video.

- [ ] **Step 1: Write failing guide-audio reuse tests**

When project has `guide-audio.wav`, ASR input is guide audio; source-video probe remains source of timeline fps/dimensions/duration. Existing transcript cache is reused when source+guide signatures are unchanged.

- [ ] **Step 2: Preserve reuse-first editorial artifacts**

If `online-candidates.json`, `edit-plan.json` and `review.html` already match the project source signature, do not rerun sourcing/Qwen/provider. Existing user-reported reuse-first fix remains required.

- [ ] **Step 3: Update docs**

Document:

```text
http://127.0.0.1:8765/curation   professional product
http://127.0.0.1:8765/debug      engineering/debug surface
```

State explicitly that normal runtime uses no GPT/OpenAI call.

- [ ] **Step 4: Verify and commit**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_debug_run_cli.py tests/test_curation_api.py -q
git add backend/app/debug_run_cli.py backend/app/curation_api.py docs/RAMBLA_DEBUG_RUNNER.md tests/test_debug_run_cli.py tests/test_curation_api.py
git commit -m "feat: use project guide audio in curation analysis"
```

---

### Task 8: KURA reuse-first professional acceptance smoke

**Files:** no new product files expected.

- [ ] **Step 1: Start the current local server**

Use the existing launcher. Preserve KURA artifacts/cache.

- [ ] **Step 2: Open professional entrypoint**

`http://127.0.0.1:8765/curation`

Register the existing KURA local video using local-path mode; do not copy it unless required.

- [ ] **Step 3: Validate original-audio extraction/guide**

Confirm source metadata appears, original audio extracts/caches, and repeated load does not extract again.

- [ ] **Step 4: Reuse KURA analysis**

Confirm existing transcript/chunks/online candidates/edit-plan are reused; do not rerun Qwen/provider merely for UI verification.

- [ ] **Step 5: Validate video and image shelves**

For at least one phrase with candidates:

- real video preview plays from local lightweight preview;
- real image thumbnails are visible;
- image lightbox works;
- video/image inspection is separate from selection.

If image discovery produced no eligible rows for a phrase, show an honest empty state; do not invent filler.

- [ ] **Step 6: Validate mixed multi-selection**

Select one video + one image for the same phrase. Confirm tray shows V2/V3. Add/reorder a third candidate if available and confirm V4/order update.

- [ ] **Step 7: Validate NO BROLL and persistence**

Set another phrase to NO BROLL. Refresh browser/server and verify selections persist.

- [ ] **Step 8: Validate selection plan**

Inspect `selection-plan.json`; confirm ordered asset ids and V2/V3/V4 mapping.

- [ ] **Step 9: Final verification**

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m compileall -q backend
git status --short
git diff feat/editorial-intelligence-style-dna-v1...HEAD --stat
```

Verify no source media, guide audio, model, cache, credential or runtime artifact is staged.

- [ ] **Step 10: Push/update draft PR and HANDOFF**

Push `feat/curation-ui-v1`. Draft PR base remains `feat/editorial-intelligence-style-dna-v1` unless repository state requires the already-approved equivalent base.

HANDOFF must include:

- branch/head SHA;
- per-task commits;
- focused + full tests;
- exact professional URL;
- KURA source/audio-guide result;
- video/image preview counts and errors;
- proof of mixed V2/V3 selection;
- persistence proof;
- selection-plan path;
- `resolve_calls=0`;
- `GPT/OpenAI runtime calls=0`;
- anything genuinely unproven.

## Completion gate

Do not call the redesign complete merely because HTML renders. Completion requires the full source-video -> guide-audio -> reuse/analyze -> phrase navigation -> real video+image preview -> ordered mixed selection -> persistence -> selection-plan workflow to be testable in the browser on KURA with `resolve_calls=0`.