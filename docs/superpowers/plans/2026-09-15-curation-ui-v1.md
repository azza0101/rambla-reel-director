# RAMBLA Curation UI V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans in single-agent sequential mode to implement this plan task-by-task. Do not spawn routine subagents/reviewers; Normal Chat is the external reviewer. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a modern local curation interface that shows up to 3 real playable video previews and 4 real image thumbnails for every semantic phrase, lets the user multi-select visuals or `NO_BROLL`, and writes a deterministic `selection-plan.json` with stacked V2/V3/V4… track assignments.

**Architecture:** Keep the existing Debug Runner and Editorial Intelligence pipeline intact. Add a provider-neutral curation layer that hydrates phrase/candidate data from current run artifacts, materializes lightweight cached previews, stores user selections atomically, and exposes a dedicated FastAPI curation page/API. Runtime remains local-first and does not require GPT/OpenAI calls.

**Tech Stack:** Python 3.13, FastAPI, Pydantic/dataclasses, httpx, FFmpeg, yt-dlp, existing local Qwen stack, faster-whisper, vanilla HTML/CSS/JavaScript.

**Spec:** `docs/superpowers/specs/2026-09-15-curation-ui-v1-design.md`

## Global Constraints

- Standard runtime must not require GPT/OpenAI model calls or Codex/Work credits.
- Preserve the existing `/debug` progress page and current Debug Runner behavior.
- No Resolve mutation in V1; `resolve_calls=0` remains mandatory.
- No ComfyUI, global Python, system PATH/CUDA, or unrelated filesystem changes.
- Input video remains read-only.
- Preview/cache/runtime outputs remain under approved RAMBLA test roots.
- Video shelf cap: 3; image shelf cap: 4. These are maxima, not filler quotas.
- `NO_BROLL` is mutually exclusive with visual selections for the same chunk.
- Selected visuals map deterministically to V2, V3, V4… in stable selection order.
- Full-resolution acquisition happens only for selected assets or already-required finalist verification.
- Credentials stay out of Git, logs, command profiles, review artifacts, and selection artifacts.
- Pexels credentials are read only from `PEXELS_API_KEY`; image-provider credentials follow the same environment-only rule.
- Preview failures are isolated per card; one broken candidate must never fail a chunk/page.
- Reuse existing KURA ASR/chunks/candidate artifacts for the first UI smoke; do not rerun ASR/provider/Qwen just to render the curation page.
- Keep LOW-CREDIT development mode: focused tests after each task; one full suite/compile only at completion.

## Execution Preflight — preserve the working local Debug Runner

The current Codex worktree is known to have local HEAD `91c2135` plus uncommitted Debug Runner/KURA changes in these files:

- `backend/app/debug_run_cli.py`
- `backend/app/online_sourcing_cli.py`
- `tests/test_debug_run_cli.py`
- `tests/unit/test_online_sourcing.py`
- local `CURRENT_STATE.md`

Before Task 1, preserve that state without resetting or rebuilding it:

```powershell
git status --short
git push origin HEAD:feat/editorial-intelligence-style-dna-v1
git add backend/app/debug_run_cli.py backend/app/online_sourcing_cli.py tests/test_debug_run_cli.py tests/unit/test_online_sourcing.py
git commit -m "feat: checkpoint working KURA debug runner"
git push origin feat/editorial-intelligence-style-dna-v1
git switch -c feat/curation-ui-v1
```

If `CURRENT_STATE.md` is modified, keep it local rather than committing it:

```powershell
git stash push -m "local CURRENT_STATE before curation UI" -- CURRENT_STATE.md
```

Do not reset, clean, or delete local artifacts/models/cache.

---

### Task 1: Add provider-neutral curation contracts and shelf builder

**Files:**
- Create: `backend/app/curation.py`
- Create: `tests/unit/test_curation.py`

**Interfaces:**
- Produces: `CurationCandidate`, `CurationChunk`, `build_candidate_shelf()`.
- Later tasks consume these exact field names for preview materialization, API serialization, and selection persistence.

- [ ] **Step 1: Write failing tests for shelf caps, ordering, diversity and `NO_BROLL` metadata**

Create `tests/unit/test_curation.py` with these fixtures/tests:

```python
from backend.app.curation import CurationCandidate, build_candidate_shelf


def candidate(asset_id: str, kind: str, score: float, source_page: str) -> CurationCandidate:
    return CurationCandidate(
        asset_id=asset_id,
        chunk_id="chunk-1",
        kind=kind,
        provider="test",
        source_page=source_page,
        title=asset_id,
        description="",
        score=score,
        rights_state="review_required",
        orientation="landscape",
        source_start_seconds=10.0 if kind == "video" else None,
        source_end_seconds=12.5 if kind == "video" else None,
    )


def test_shelf_caps_three_videos_and_four_images_in_score_order():
    rows = [
        *(candidate(f"v{i}", "video", 1 - i / 10, f"https://v/{i}") for i in range(5)),
        *(candidate(f"i{i}", "image", 1 - i / 10, f"https://i/{i}") for i in range(6)),
    ]
    shelf = build_candidate_shelf(rows)
    assert [x.asset_id for x in shelf.video] == ["v0", "v1", "v2"]
    assert [x.asset_id for x in shelf.images] == ["i0", "i1", "i2", "i3"]


def test_shelf_dedupes_same_source_page_before_applying_caps():
    rows = [
        candidate("v-a", "video", .9, "https://same"),
        candidate("v-b", "video", .8, "https://same"),
        candidate("v-c", "video", .7, "https://other"),
    ]
    shelf = build_candidate_shelf(rows)
    assert [x.asset_id for x in shelf.video] == ["v-a", "v-c"]


def test_shelf_never_invents_fillers():
    shelf = build_candidate_shelf([candidate("v-a", "video", .9, "https://v/a")])
    assert len(shelf.video) == 1
    assert shelf.images == ()
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/unit/test_curation.py -q
```

Expected: import failure because `backend.app.curation` does not exist.

- [ ] **Step 3: Implement the minimal curation domain model**

Create `backend/app/curation.py` with these public contracts:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CandidateKind = Literal["video", "image"]


@dataclass(frozen=True, slots=True)
class CurationCandidate:
    asset_id: str
    chunk_id: str
    kind: CandidateKind
    provider: str
    source_page: str
    title: str
    description: str
    score: float
    rights_state: str
    orientation: str
    source_start_seconds: float | None = None
    source_end_seconds: float | None = None
    preview_path: str | None = None
    poster_path: str | None = None
    local_asset_path: str | None = None
    preview_status: str = "pending"
    preview_error: str | None = None


@dataclass(frozen=True, slots=True)
class CandidateShelf:
    video: tuple[CurationCandidate, ...]
    images: tuple[CurationCandidate, ...]


def _dedupe_source(rows: list[CurationCandidate]) -> list[CurationCandidate]:
    seen: set[tuple[str, str]] = set()
    out: list[CurationCandidate] = []
    for row in sorted(rows, key=lambda x: (-x.score, x.asset_id)):
        key = (row.kind, row.source_page.casefold())
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def build_candidate_shelf(
    rows: list[CurationCandidate], *, video_limit: int = 3, image_limit: int = 4
) -> CandidateShelf:
    if video_limit < 0 or image_limit < 0:
        raise ValueError("curation shelf limits must be non-negative")
    unique = _dedupe_source(rows)
    video = tuple(row for row in unique if row.kind == "video")[:video_limit]
    images = tuple(row for row in unique if row.kind == "image")[:image_limit]
    return CandidateShelf(video=video, images=images)
```

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the same pytest command. Expected: `3 passed`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/curation.py tests/unit/test_curation.py
git commit -m "feat: add curation candidate shelf contracts"
```

---

### Task 2: Add real image candidate providers without coupling the pipeline to one search vendor

**Files:**
- Create: `backend/app/image_sources.py`
- Create: `tests/unit/test_image_sources.py`
- Modify: `backend/app/debug_run_cli.py`

**Interfaces:**
- Produces: `RemoteImageCandidate`, `WikimediaImageSource.search()`, `PexelsPhotoSource.search()`, `search_image_candidates()`.
- `debug_run_cli.py` consumes `search_image_candidates()` after semantic chunks exist and writes `image-candidates.json` under the run output directory.

- [ ] **Step 1: Write failing normalization/provider tests**

Create `tests/unit/test_image_sources.py` covering both credentialless Wikimedia and env-driven Pexels photo normalization. Use `httpx.MockTransport`; no network in tests.

Required test assertions:

```python
assert row.kind == "image"
assert row.provider == "wikimedia"
assert row.source_page.startswith("https://commons.wikimedia.org/")
assert row.thumbnail_url.startswith("https://")
assert row.rights_state in {"known_public_license", "review_required"}
```

For Pexels:

```python
assert row.provider == "pexels"
assert row.source_page.startswith("https://www.pexels.com/photo/")
assert row.thumbnail_url.startswith("https://")
assert row.rights_state == "provider_stock_terms"
```

Also assert missing Pexels key raises sanitized `ProviderError("pexels_images", "credential_required", ...)` and never includes the key value.

- [ ] **Step 2: Run tests and verify RED**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/unit/test_image_sources.py -q
```

Expected: module import failure.

- [ ] **Step 3: Implement `RemoteImageCandidate` and two sources**

Create `backend/app/image_sources.py` with this public model:

```python
@dataclass(frozen=True, slots=True)
class RemoteImageCandidate:
    provider: str
    provider_id: str
    query: str
    source_page: str
    title: str
    description: str
    thumbnail_url: str
    full_url: str
    width: int
    height: int
    orientation: str
    rights_state: str
    provider_rank: int
    kind: str = "image"
```

Implement `WikimediaImageSource.search(query, *, limit)` using:

```text
GET https://commons.wikimedia.org/w/api.php
?action=query
&format=json
&generator=search
&gsrnamespace=6
&gsrsearch=<query>
&gsrlimit=<limit>
&prop=imageinfo
&iiprop=url|extmetadata
&iiurlwidth=640
```

Map `imageinfo[0].thumburl` to `thumbnail_url`, `descriptionurl` to `source_page`, `url` to `full_url`, and license metadata to `rights_state="known_public_license"` only when a license short name is present; otherwise use `review_required`.

Implement `PexelsPhotoSource.search(query, *, limit)` against:

```text
GET https://api.pexels.com/v1/search
Authorization: <PEXELS_API_KEY>
```

Use `src.medium` as thumbnail and `src.original` as full image URL. Read the key only from the constructor argument supplied by `os.environ.get("PEXELS_API_KEY")` in the caller.

Implement:

```python
async def search_image_candidates(
    query: str,
    *,
    sources: list[ImageSource],
    per_source_limit: int = 6,
) -> list[RemoteImageCandidate]:
```

Run sources concurrently, sanitize provider failures to `{provider, code}`, dedupe `(provider, provider_id)`, and return stable provider-rank order.

- [ ] **Step 4: Wire image discovery into `debug_run_cli.py` without making it a hard failure**

After current semantic chunks/outline are available, build one image query per chunk from the exact chunk text. Use `WikimediaImageSource` always and append `PexelsPhotoSource(os.environ.get("PEXELS_API_KEY"))` only when the env var is present.

Persist this shape to `image-candidates.json`:

```json
{
  "chunks": {
    "chunk_001": {
      "query": "exact semantic phrase",
      "candidates": []
    }
  },
  "errors": []
}
```

A provider error must add an error row and continue the run.

- [ ] **Step 5: Run focused tests**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/unit/test_image_sources.py tests/test_debug_run_cli.py -q
```

Expected: all focused tests pass; no live provider calls.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/image_sources.py backend/app/debug_run_cli.py tests/unit/test_image_sources.py tests/test_debug_run_cli.py
git commit -m "feat: add image discovery for curation shelves"
```

---

### Task 3: Materialize lightweight real previews with stable caching and per-card failure isolation

**Files:**
- Create: `backend/app/curation_preview.py`
- Create: `tests/unit/test_curation_preview.py`
- Modify: `backend/app/asset_cache.py`

**Interfaces:**
- Produces: `PreviewResult`, `CurationPreviewMaterializer.materialize()`.
- Later API/UI tasks consume only local preview/poster paths from `PreviewResult`; they never need provider credentials or transient signed URLs.

- [ ] **Step 1: Write failing cache-key, image, video-command and failure-isolation tests**

Create `tests/unit/test_curation_preview.py` with injected fake download/command functions. Required assertions:

```python
assert first.cache_hit is False
assert second.cache_hit is True
assert first.preview_path == second.preview_path
assert result.poster_path is not None
assert result.status == "ready"
```

For video command generation assert the command contains these exact functional constraints:

```text
-t 2.2
-an
-c:v libx264
-crf 28
-movflags +faststart
```

For one broken candidate assert:

```python
assert broken.status == "error"
assert healthy.status == "ready"
```

without raising from the batch materializer.

- [ ] **Step 2: Run tests and verify RED**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/unit/test_curation_preview.py -q
```

Expected: module import failure.

- [ ] **Step 3: Implement stable preview keys and output model**

Create:

```python
@dataclass(frozen=True, slots=True)
class PreviewResult:
    asset_id: str
    preview_path: Path | None
    poster_path: Path | None
    width: int | None
    height: int | None
    cache_hit: bool
    status: str
    error: str | None
    downloaded_bytes: int
```

Stable cache material must include:

```text
asset_id + kind + source_page + rounded start/end + preview version "v1-2.2s-480"
```

Hash with SHA-256 and store under:

```text
<cache_root>/curation-previews/<hash>.mp4
<cache_root>/curation-previews/<hash>.jpg
<cache_root>/curation-previews/<hash>.json
```

- [ ] **Step 4: Implement image thumbnail materialization**

For image candidates, fetch only the configured thumbnail URL with `httpx`, cap response size at 8 MiB, write atomically, and keep full-resolution acquisition deferred until selection.

Do not persist signed/transient URL query strings in metadata; persist source page/provider/id instead.

- [ ] **Step 5: Implement video loop materialization**

For YouTube/YouTube Shorts candidates with source window, acquire a bounded source window with existing yt-dlp tooling or `AssetCache.materialize_acquired_window()` and transcode a 2.2-second muted H.264 MP4 preview:

```powershell
ffmpeg -y -ss 0 -i <bounded_input> -t 2.2 -vf "scale='min(480,iw)':-2" -an -c:v libx264 -preset veryfast -crf 28 -movflags +faststart <preview.mp4>
```

Generate poster:

```powershell
ffmpeg -y -ss 0.2 -i <preview.mp4> -frames:v 1 -q:v 3 <poster.jpg>
```

For candidates already represented by a local MP4 window, reuse it as the input; do not reacquire the remote source.

For candidates lacking a materializable video source, return `PreviewResult(status="error", error="preview_unavailable", ...)` and continue.

- [ ] **Step 6: Add a batch helper with bounded concurrency**

Implement:

```python
async def materialize_batch(
    materializer: CurationPreviewMaterializer,
    candidates: list[CurationCandidate],
    *,
    concurrency: int = 4,
) -> list[PreviewResult]:
```

Use `asyncio.Semaphore(4)` and `asyncio.gather(..., return_exceptions=False)` because individual `materialize()` converts its own failure to `PreviewResult(status="error")`.

- [ ] **Step 7: Run focused tests and commit**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/unit/test_curation_preview.py tests/unit/test_asset_cache.py -q
git add backend/app/curation_preview.py backend/app/asset_cache.py tests/unit/test_curation_preview.py
git commit -m "feat: materialize lightweight curation previews"
```

---

### Task 4: Persist user selections and generate deterministic stacked `selection-plan.json`

**Files:**
- Create: `backend/app/curation_selection.py`
- Create: `tests/unit/test_curation_selection.py`

**Interfaces:**
- Produces: `SelectionStore`, `set_chunk_selection()`, `load_selection_plan()`.
- API task consumes these methods directly.

- [ ] **Step 1: Write failing tests for multi-select, `NO_BROLL`, refresh persistence and track assignment**

Create `tests/unit/test_curation_selection.py` with these assertions:

```python
store.set_chunk_selection("chunk-7", ["vid-2", "img-4"], no_broll=False)
plan = store.load()
rows = plan["chunks"]["chunk-7"]["selected_assets"]
assert [(x["asset_id"], x["track"], x["order"]) for x in rows] == [
    ("vid-2", "V2", 0),
    ("img-4", "V3", 1),
]
```

```python
store.set_chunk_selection("chunk-7", [], no_broll=True)
assert store.load()["chunks"]["chunk-7"]["no_broll"] is True
```

```python
with pytest.raises(ValueError, match="NO_BROLL"):
    store.set_chunk_selection("chunk-7", ["vid-2"], no_broll=True)
```

Recreate `SelectionStore` from disk and assert the selection survives process refresh.

- [ ] **Step 2: Run tests and verify RED**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/unit/test_curation_selection.py -q
```

- [ ] **Step 3: Implement atomic selection store**

Use exact artifact path:

```text
<run_output>/selection-plan.json
```

Public constructor:

```python
SelectionStore(
    output_dir: Path,
    *,
    input_video: str,
    timeline_fps: float,
    candidate_index: dict[str, CurationCandidate],
    chunk_ranges: dict[str, tuple[float, float]],
)
```

`set_chunk_selection(chunk_id, asset_ids, no_broll=False)` must:

1. reject unknown asset IDs;
2. reject candidates belonging to another chunk;
3. dedupe asset IDs preserving first-seen order;
4. enforce `NO_BROLL` exclusivity;
5. assign `V2 + index` deterministically;
6. preserve provider/source/rights/local path metadata for every selection;
7. write to a temp file then `replace()` atomically.

- [ ] **Step 4: Run focused tests and commit**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/unit/test_curation_selection.py -q
git add backend/app/curation_selection.py tests/unit/test_curation_selection.py
git commit -m "feat: persist curation selection plans"
```

---

### Task 5: Hydrate curation shelves from current run artifacts and expose safe FastAPI APIs/media routes

**Files:**
- Create: `backend/app/curation_artifacts.py`
- Create: `tests/unit/test_curation_artifacts.py`
- Modify: `backend/app/debug_server.py`
- Create: `tests/test_curation_api.py`

**Interfaces:**
- Produces: `load_curation_run(output_dir: Path) -> CurationRun`.
- Adds routes: `/debug/curation`, `/api/curation/run/{run_id}`, `/api/curation/run/{run_id}/selection`, `/api/curation/run/{run_id}/selection-plan`, `/api/curation/media/{asset_id}/{variant}`.

- [ ] **Step 1: Write failing artifact hydration tests using current filenames**

Fixtures must cover these existing artifacts when present:

```text
transcript-raw.json or transcript.json
semantic-chunks.json or semantic-beats.json
online-candidates.json or candidate-metrics.json
image-candidates.json
edit-plan.json
coverage-metrics.json
```

Required behavior:

```python
run = load_curation_run(tmp_path)
assert run.chunks[0].chunk_id == "chunk_001"
assert run.chunks[0].text == "Una frase completa"
assert len(run.chunks[0].shelf.video) <= 3
assert len(run.chunks[0].shelf.images) <= 4
```

Malformed candidate rows are skipped and reported in `run.errors`, not raised globally.

- [ ] **Step 2: Implement artifact adapters without changing the producer formats**

Create a `CurationRun` dataclass containing:

```python
run_id: str
input_video: str
output_dir: str
fps: float
chunks: tuple[CurationChunkView, ...]
errors: tuple[dict[str, str], ...]
```

Map current online candidate rows to `kind="video"`; map `image-candidates.json` rows to `kind="image"`. Prefer existing local `preview_path`/bounded-window paths before attempting new materialization.

Do not reinterpret video thumbnails as image candidates.

- [ ] **Step 3: Write failing FastAPI tests**

Create `tests/test_curation_api.py` with `TestClient`. Required assertions:

```python
response = client.get("/debug/curation")
assert response.status_code == 200
assert "RAMBLA Curation" in response.text
```

```python
response = client.get("/api/curation/run/default")
assert response.status_code == 200
assert "chunks" in response.json()
```

```python
response = client.post(
    "/api/curation/run/default/selection",
    json={"chunk_id": "chunk_001", "asset_ids": ["v1", "i1"], "no_broll": False},
)
assert response.status_code == 200
assert [x["track"] for x in response.json()["selected_assets"]] == ["V2", "V3"]
```

Add path traversal tests that `/api/curation/media/...` cannot serve any path outside the configured output/cache roots.

- [ ] **Step 4: Extend `debug_server.py` with safe curation routes**

Use `run_id="default"` as the persisted KURA/output-root fallback so the UI remains usable after the FastAPI process restarts and in-memory `RUNS` is empty.

Add Pydantic request:

```python
class SelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_id: str
    asset_ids: list[str] = []
    no_broll: bool = False
```

For media routes, never accept raw filesystem paths from the URL. Resolve `asset_id` through the loaded curation candidate index, choose only `preview_path` or `poster_path`, call `.resolve()`, and verify it is under the approved output/cache roots before returning `FileResponse`.

- [ ] **Step 5: Run focused API tests and commit**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/unit/test_curation_artifacts.py tests/test_curation_api.py tests/test_debug_server.py -q
git add backend/app/curation_artifacts.py backend/app/debug_server.py tests/unit/test_curation_artifacts.py tests/test_curation_api.py
git commit -m "feat: expose curation API and safe preview routes"
```

---

### Task 6: Build the modern visual HTML curation interface

**Files:**
- Create: `backend/app/curation_ui.py`
- Create: `tests/unit/test_curation_ui.py`
- Modify: `backend/app/debug_server.py`

**Interfaces:**
- Produces: `render_curation_page() -> str`.
- `/debug/curation` returns this page; all state comes from the Task 5 APIs.

- [ ] **Step 1: Write failing HTML contract tests**

Create `tests/unit/test_curation_ui.py` and assert the returned HTML contains these stable UI hooks:

```python
html = render_curation_page()
for token in (
    "RAMBLA Curation",
    'id="chunk-list"',
    'id="filter-selected"',
    'id="selection-summary"',
    'id="lightbox"',
    "IntersectionObserver",
    "data-preview-video",
    "NO BROLL",
):
    assert token in html
```

Assert there are no external framework/CDN dependencies:

```python
assert "cdn.jsdelivr.net" not in html
assert "unpkg.com" not in html
```

- [ ] **Step 2: Implement a self-contained modern dark UI**

Create `backend/app/curation_ui.py` with local CSS/JS only. Use these design tokens:

```css
:root {
  --bg: #090b0f;
  --panel: #11141a;
  --panel-2: #171b23;
  --line: #282e39;
  --text: #f6f7f9;
  --muted: #9ca6b5;
  --accent: #d8ff59;
  --accent-ink: #0c0f08;
  --good: #72e39a;
  --warn: #ffcc66;
  --bad: #ff7c82;
  --radius: 16px;
}
```

Required layout:

- sticky top toolbar with title, run status, filters and selection count;
- transcript-order phrase cards;
- phrase text visually dominant over metadata;
- two media shelves per phrase: `VIDEO` and `IMMAGINI`;
- 3-column video grid on desktop, responsive to one column on narrow screens;
- 4-column image grid on desktop;
- selected card uses accent border + check badge;
- unavailable preview card retains title/provider/source metadata and explicit error badge;
- `NO BROLL` control sits in phrase header and is mutually exclusive with visual cards.

- [ ] **Step 3: Implement lazy video preview behavior**

Every video card renders a poster immediately and a `<video muted loop playsinline preload="none">` element whose `src` is assigned only when its card enters the viewport using `IntersectionObserver`.

Hover/focus behavior:

```javascript
card.addEventListener('mouseenter', () => video.play().catch(() => {}));
card.addEventListener('mouseleave', () => { video.pause(); video.currentTime = 0; });
```

Do not autoplay every card simultaneously.

- [ ] **Step 4: Implement lightbox and autosaving selection UX**

Clicking media body opens `#lightbox`; clicking the select control toggles selection without opening the lightbox.

After every selection change, POST exactly this body:

```json
{
  "chunk_id": "chunk_001",
  "asset_ids": ["asset-a", "asset-b"],
  "no_broll": false
}
```

On success, update the card state, selection summary, and displayed `V2/V3/...` chips from the server response. On failure, keep the local visual state and show a retry banner; do not discard the user click.

- [ ] **Step 5: Add filters**

Implement client-side filters:

```text
All
Selected
Needs choice
NO_BROLL
Errors
```

`Needs choice` means no selected asset and `no_broll=false`.

- [ ] **Step 6: Run focused UI/API tests and commit**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/unit/test_curation_ui.py tests/test_curation_api.py tests/test_debug_server.py -q
git add backend/app/curation_ui.py backend/app/debug_server.py tests/unit/test_curation_ui.py tests/test_curation_api.py
git commit -m "feat: add modern visual curation UI"
```

---

### Task 7: Integrate preview generation into the KURA runner without repeating expensive upstream work

**Files:**
- Modify: `backend/app/debug_run_cli.py`
- Modify: `backend/app/online_sourcing_cli.py`
- Modify: `docs/RAMBLA_DEBUG_RUNNER.md`
- Modify: `tests/test_debug_run_cli.py`

**Interfaces:**
- Existing raw-video command remains unchanged:

```text
python -m backend.app.debug_run_cli --video <video> --output-dir <run-dir>
```

- Adds curation artifacts under the same run directory.

- [ ] **Step 1: Write failing integration tests using already-created fake artifacts**

Test that when transcript/chunks/candidate artifacts already exist, the curation post-processing path:

1. does not call ASR again;
2. does not rerun provider discovery for unchanged video candidates;
3. reuses cached image discovery when `image-candidates.json` already exists;
4. creates/updates local preview metadata;
5. leaves `resolve_calls=0`.

Use injected fakes/counters; no real Qwen/provider/yt-dlp in tests.

- [ ] **Step 2: Add a final `curation` stage to `debug_run_cli.py`**

After current Edit Plan/review creation, emit:

```text
RAMBLA_EVENT {"stage":"curation","progress":0,"message":"Preparazione preview curation"}
```

Then hydrate candidate shelves, materialize only missing lightweight previews, persist `curation-run.json`, and emit 100% with candidate/preview counts.

Do not change current ASR, Editorial Intelligence, Qwen scoring or source-strategy logic.

- [ ] **Step 3: Update runner docs**

Document both URLs:

```text
http://127.0.0.1:8765/debug
http://127.0.0.1:8765/debug/curation
```

Document that the curation page is the user-facing picker and `/debug` remains the engineering diagnostics page.

State clearly that standard runtime uses no GPT/OpenAI model calls.

- [ ] **Step 4: Run focused integration tests**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_debug_run_cli.py tests/test_curation_api.py tests/unit/test_curation_preview.py -q
```

Expected: all selected tests pass with no live network/model calls.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/debug_run_cli.py backend/app/online_sourcing_cli.py docs/RAMBLA_DEBUG_RUNNER.md tests/test_debug_run_cli.py
git commit -m "feat: integrate curation preview stage into debug runner"
```

---

### Task 8: KURA UI smoke, completion verification, push and draft PR

**Files:**
- No new product files expected; runtime artifacts remain untracked.

**Interfaces:**
- Final user entrypoint: `http://127.0.0.1:8765/debug/curation`.
- Final artifact: `Z:\APP REEL TEST\qwen-embedding-smoke\kura-finto-etico-smoke\run\selection-plan.json`.

- [ ] **Step 1: Reuse existing KURA artifacts before doing any live work**

Confirm these existing files are present and reuse them:

```text
transcript/chunks
online candidates
edit-plan.json
review.html
```

Do not rerun faster-whisper, Qwen or provider discovery merely to test the UI.

- [ ] **Step 2: Start the existing local Debug Runner**

```powershell
.\tools\start_rambla_debug_runner.ps1
```

Open:

```text
http://127.0.0.1:8765/debug/curation
```

- [ ] **Step 3: Materialize only missing lightweight previews**

Generate cached preview MP4/posters/images only where absent. Record counts:

```text
video candidates shown
image candidates shown
preview cache hits
new preview bytes
preview errors
```

Do not full-download unselected final assets.

- [ ] **Step 4: Perform the acceptance interaction**

For one chunk with at least two usable candidates:

1. select one video;
2. select one image;
3. verify chips show `V2` and `V3`;
4. refresh the page;
5. verify both selections persist;
6. verify `selection-plan.json` contains the same asset IDs/order/tracks;
7. set a different chunk to `NO_BROLL` and verify exclusivity.

If a chunk has fewer than the target candidate count, accept that state if the UI explains it and does not fabricate filler.

- [ ] **Step 5: Run completion verification once**

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m compileall -q backend
```

Then inspect:

```powershell
git status --short
git diff feat/editorial-intelligence-style-dna-v1...HEAD --stat
```

Verify no media/model/cache/runtime artifacts or credentials are staged.

- [ ] **Step 6: Push implementation branch**

```powershell
git push -u origin feat/curation-ui-v1
```

- [ ] **Step 7: Open a draft PR**

Base:

```text
feat/editorial-intelligence-style-dna-v1
```

Head:

```text
feat/curation-ui-v1
```

PR description must report:

- focused tests and full-suite result;
- compile result;
- exact curation URL;
- KURA preview counts/cache hits/errors;
- selection persistence proof;
- stacked V2/V3 mapping proof;
- `resolve_calls=0`;
- no GPT/OpenAI runtime dependency;
- any preview/provider limitations still unproven.

- [ ] **Step 8: Post one concise HANDOFF on Issue #3**

Include branch SHA, draft PR, `TESTABLE=YES`, exact local URL, artifact path, tests, preview counts/errors, and any real blocker. Do not merge.

---

## Self-review against the approved spec

Coverage mapping:

- 3 video / 4 image shelf: Tasks 1–2.
- Real playable video previews + image thumbnails: Task 3.
- Modern visual UI, lazy previews, lightbox, filters: Task 6.
- Multi-select / NO_BROLL / autosave: Tasks 4–6.
- Stacked V2/V3/V4 semantics: Task 4.
- `selection-plan.json`: Task 4.
- FastAPI API/media safety: Task 5.
- No GPT/OpenAI runtime dependency: Global Constraints + Tasks 2–8.
- Provider-neutral images: Task 2.
- Preview cache/failure isolation: Task 3.
- Rights/provenance retention: Tasks 1–5.
- Existing Debug Runner preserved: Tasks 5–7.
- No Resolve mutation: Global Constraints + completion proof.
- KURA reuse-first smoke: Task 8.

No implementation task requires a new frontend framework, a new database, or a new remote LLM dependency.
