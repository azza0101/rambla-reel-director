# RAMBLA Curation UI V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans in single-agent sequential mode. Do not spawn routine subagents/reviewers; Normal Chat is the external reviewer. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a modern local curation UI that shows up to 3 real playable video previews and 4 real image thumbnails for each semantic phrase, supports multi-select/`NO_BROLL`, and writes a deterministic `selection-plan.json` with V2/V3/V4… stacked-track assignments.

**Architecture:** Preserve the existing Debug Runner and Editorial Intelligence pipeline. Add a provider-neutral curation layer that hydrates existing run artifacts, discovers image candidates, materializes lightweight cached previews, persists selections atomically, and serves a dedicated FastAPI curation page/API. Standard runtime stays local-first and requires no GPT/OpenAI model call.

**Tech Stack:** Python 3.13, FastAPI, Pydantic/dataclasses, httpx, FFmpeg, yt-dlp, existing local Qwen stack, faster-whisper, vanilla HTML/CSS/JavaScript.

**Spec:** `docs/superpowers/specs/2026-09-15-curation-ui-v1-design.md`

## Global Constraints

- Standard runtime must not require GPT/OpenAI model calls or Codex/Work credits.
- Preserve `/debug` and current Debug Runner behavior.
- No Resolve mutation; `resolve_calls=0` remains mandatory.
- No ComfyUI, global Python, system PATH/CUDA, or unrelated filesystem changes.
- Input video remains read-only.
- Preview/cache/runtime outputs stay under approved RAMBLA test roots.
- Shelf caps are 3 video and 4 image candidates; never invent filler.
- `NO_BROLL` is mutually exclusive with visual selections for a chunk.
- Selection order maps deterministically to V2, V3, V4….
- Full-resolution acquisition happens only after user selection or already-required finalist verification.
- Credentials stay out of Git, logs, command profiles, review artifacts, and selection artifacts.
- Pexels credentials are read only from `PEXELS_API_KEY`.
- Preview failures are isolated per card.
- First UI smoke reuses existing KURA ASR/chunks/candidates; do not rerun ASR/provider/Qwen merely to render the page.
- LOW-CREDIT development mode: focused tests per task, one full suite/compile at completion.

## Execution Preflight — preserve the current working Debug Runner

Known local state: HEAD `91c2135` plus uncommitted changes in `backend/app/debug_run_cli.py`, `backend/app/online_sourcing_cli.py`, `tests/test_debug_run_cli.py`, `tests/unit/test_online_sourcing.py`, and local `CURRENT_STATE.md`.

- [ ] Stash only the scratch state before switching branches:

```powershell
git stash push -m "local CURRENT_STATE before curation UI" -- CURRENT_STATE.md
```

- [ ] Publish the existing local Debug Runner commit, checkpoint the current product changes, then branch:

```powershell
git status --short
git push origin HEAD:feat/editorial-intelligence-style-dna-v1
git add backend/app/debug_run_cli.py backend/app/online_sourcing_cli.py tests/test_debug_run_cli.py tests/unit/test_online_sourcing.py
git commit -m "feat: checkpoint working KURA debug runner"
git push origin feat/editorial-intelligence-style-dna-v1
git switch -c feat/curation-ui-v1
```

Do not reset, clean, or delete local artifacts/models/cache.

---

### Task 1: Provider-neutral curation contracts and shelf builder

**Files:**
- Create: `backend/app/curation.py`
- Test: `tests/unit/test_curation.py`

**Interfaces:**
- Produces: `CurationCandidate`, `CandidateShelf`, `build_candidate_shelf()`.

- [ ] **Step 1: Write failing tests**

```python
from backend.app.curation import CurationCandidate, build_candidate_shelf


def c(asset_id: str, kind: str, score: float, source: str) -> CurationCandidate:
    return CurationCandidate(
        asset_id=asset_id, chunk_id="chunk-1", kind=kind, provider="test",
        source_page=source, title=asset_id, description="", score=score,
        rights_state="review_required", orientation="landscape",
        source_start_seconds=10.0 if kind == "video" else None,
        source_end_seconds=12.5 if kind == "video" else None,
    )


def test_shelf_caps_and_orders():
    rows = [*(c(f"v{i}", "video", 1-i/10, f"https://v/{i}") for i in range(5)),
            *(c(f"i{i}", "image", 1-i/10, f"https://i/{i}") for i in range(6))]
    shelf = build_candidate_shelf(rows)
    assert [x.asset_id for x in shelf.video] == ["v0", "v1", "v2"]
    assert [x.asset_id for x in shelf.images] == ["i0", "i1", "i2", "i3"]


def test_shelf_dedupes_same_source():
    shelf = build_candidate_shelf([
        c("a", "video", .9, "https://same"),
        c("b", "video", .8, "https://same"),
        c("c", "video", .7, "https://other"),
    ])
    assert [x.asset_id for x in shelf.video] == ["a", "c"]


def test_shelf_never_invents_fillers():
    shelf = build_candidate_shelf([c("a", "video", .9, "https://a")])
    assert len(shelf.video) == 1
    assert shelf.images == ()
```

- [ ] **Step 2: Verify RED**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/unit/test_curation.py -q
```

Expected: import failure.

- [ ] **Step 3: Implement minimal domain model**

```python
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

def build_candidate_shelf(rows: list[CurationCandidate], *, video_limit: int = 3, image_limit: int = 4) -> CandidateShelf:
    if video_limit < 0 or image_limit < 0:
        raise ValueError("curation shelf limits must be non-negative")
    seen: set[tuple[str, str]] = set()
    ordered: list[CurationCandidate] = []
    for row in sorted(rows, key=lambda x: (-x.score, x.asset_id)):
        key = (row.kind, row.source_page.casefold())
        if key not in seen:
            seen.add(key)
            ordered.append(row)
    return CandidateShelf(
        video=tuple(x for x in ordered if x.kind == "video")[:video_limit],
        images=tuple(x for x in ordered if x.kind == "image")[:image_limit],
    )
```

- [ ] **Step 4: Verify GREEN and commit**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/unit/test_curation.py -q
git add backend/app/curation.py tests/unit/test_curation.py
git commit -m "feat: add curation candidate shelf contracts"
```

---

### Task 2: Real image discovery via credentialless Wikimedia plus optional Pexels Photos

**Files:**
- Create: `backend/app/image_sources.py`
- Test: `tests/unit/test_image_sources.py`
- Modify: `backend/app/debug_run_cli.py`

**Interfaces:**
- Produces: `RemoteImageCandidate`, `ImageSource`, `WikimediaImageSource`, `PexelsPhotoSource`, `search_image_candidates()`.
- Writes: `<run>/image-candidates.json`.

- [ ] **Step 1: Write failing provider/normalization tests using `httpx.MockTransport`**

Required assertions:

```python
assert row.kind == "image"
assert row.provider == "wikimedia"
assert row.source_page.startswith("https://commons.wikimedia.org/")
assert row.thumbnail_url.startswith("https://")
```

and for Pexels:

```python
assert row.provider == "pexels"
assert row.source_page.startswith("https://www.pexels.com/photo/")
assert row.rights_state == "provider_stock_terms"
```

Missing Pexels key must raise a sanitized `ProviderError` without echoing the credential.

- [ ] **Step 2: Verify RED**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/unit/test_image_sources.py -q
```

- [ ] **Step 3: Implement exact public contracts**

```python
from dataclasses import dataclass
from typing import Protocol

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

class ImageSource(Protocol):
    async def search(self, query: str, *, limit: int) -> list[RemoteImageCandidate]: ...
```

`WikimediaImageSource` uses `https://commons.wikimedia.org/w/api.php` with `generator=search`, namespace 6, `prop=imageinfo`, `iiprop=url|extmetadata`, and `iiurlwidth=640`. Use `known_public_license` only when license metadata is present; otherwise `review_required`.

`PexelsPhotoSource` uses `https://api.pexels.com/v1/search`, `Authorization` from constructor, `src.medium` for thumbnail and `src.original` for deferred full image.

Implement:

```python
async def search_image_candidates(query: str, *, sources: list[ImageSource], per_source_limit: int = 6) -> tuple[list[RemoteImageCandidate], list[dict[str, str]]]:
    ...
```

The implementation gathers sources concurrently, dedupes `(provider, provider_id)`, and sanitizes provider failures to `{provider, code}`.

- [ ] **Step 4: Wire one exact-phrase image query per semantic chunk**

`debug_run_cli.py` always uses Wikimedia and appends Pexels Photos only when `PEXELS_API_KEY` exists. Persist:

```json
{"chunks":{"chunk_001":{"query":"exact phrase","candidates":[]}},"errors":[]}
```

Provider failure is non-fatal.

- [ ] **Step 5: Verify and commit**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/unit/test_image_sources.py tests/test_debug_run_cli.py -q
git add backend/app/image_sources.py backend/app/debug_run_cli.py tests/unit/test_image_sources.py tests/test_debug_run_cli.py
git commit -m "feat: add image discovery for curation shelves"
```

---

### Task 3: Lightweight real preview materialization and cache

**Files:**
- Create: `backend/app/curation_preview.py`
- Modify: `backend/app/asset_cache.py`
- Test: `tests/unit/test_curation_preview.py`

**Interfaces:**
- Produces: `PreviewResult`, `CurationPreviewMaterializer.materialize()`, `materialize_batch()`.

- [ ] **Step 1: Write failing tests**

Cover stable cache reuse, poster creation, exact video transcode flags, and per-card failure isolation. Required assertions:

```python
assert first.cache_hit is False
assert second.cache_hit is True
assert first.preview_path == second.preview_path
assert result.poster_path is not None
assert broken.status == "error"
assert healthy.status == "ready"
```

- [ ] **Step 2: Verify RED**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/unit/test_curation_preview.py -q
```

- [ ] **Step 3: Implement output/cache model**

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

Cache key material is `asset_id + kind + source_page + rounded start/end + "v1-2.2s-480"`, SHA-256 hashed under `<cache_root>/curation-previews/`.

- [ ] **Step 4: Implement image thumbnails**

Fetch only thumbnail bytes, cap at 8 MiB, write atomically, persist no signed query string. Full image remains deferred until selection.

- [ ] **Step 5: Implement video previews**

Reuse an existing local bounded MP4 when available. Otherwise for YouTube/Shorts use existing bounded acquisition/yt-dlp path from `source_page` and `source_start_seconds/source_end_seconds`. Transcode:

```powershell
ffmpeg -y -ss 0 -i <bounded_input> -t 2.2 -vf "scale='min(480,iw)':-2" -an -c:v libx264 -preset veryfast -crf 28 -movflags +faststart <preview.mp4>
ffmpeg -y -ss 0.2 -i <preview.mp4> -frames:v 1 -q:v 3 <poster.jpg>
```

If a candidate cannot be materialized, return `status="error"` with sanitized `preview_unavailable`; do not raise across the batch.

- [ ] **Step 6: Bound batch concurrency to 4, verify and commit**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/unit/test_curation_preview.py tests/unit/test_asset_cache.py -q
git add backend/app/curation_preview.py backend/app/asset_cache.py tests/unit/test_curation_preview.py
git commit -m "feat: materialize lightweight curation previews"
```

---

### Task 4: Selection persistence and stacked timeline plan

**Files:**
- Create: `backend/app/curation_selection.py`
- Test: `tests/unit/test_curation_selection.py`

**Interfaces:**
- Produces: `SelectionStore.set_chunk_selection()` and `SelectionStore.load()`.
- Writes: `<run>/selection-plan.json`.

- [ ] **Step 1: Write failing tests**

```python
store.set_chunk_selection("chunk-7", ["vid-2", "img-4"], no_broll=False)
rows = store.load()["chunks"]["chunk-7"]["selected_assets"]
assert [(x["asset_id"], x["track"], x["order"]) for x in rows] == [
    ("vid-2", "V2", 0), ("img-4", "V3", 1)
]
```

Also test refresh persistence and:

```python
with pytest.raises(ValueError, match="NO_BROLL"):
    store.set_chunk_selection("chunk-7", ["vid-2"], no_broll=True)
```

- [ ] **Step 2: Verify RED**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/unit/test_curation_selection.py -q
```

- [ ] **Step 3: Implement atomic store**

Constructor:

```python
SelectionStore(output_dir: Path, *, input_video: str, timeline_fps: float, candidate_index: dict[str, CurationCandidate], chunk_ranges: dict[str, tuple[float, float]])
```

`set_chunk_selection()` rejects unknown/cross-chunk assets, dedupes preserving order, enforces `NO_BROLL`, maps first selection to V2, and writes via temp-file `replace()`.

- [ ] **Step 4: Verify and commit**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/unit/test_curation_selection.py -q
git add backend/app/curation_selection.py tests/unit/test_curation_selection.py
git commit -m "feat: persist curation selection plans"
```

---

### Task 5: Artifact hydration and safe FastAPI curation API

**Files:**
- Create: `backend/app/curation_artifacts.py`
- Modify: `backend/app/debug_server.py`
- Test: `tests/unit/test_curation_artifacts.py`
- Test: `tests/test_curation_api.py`

**Interfaces:**
- Produces: `load_curation_run(output_dir: Path) -> CurationRun`.
- Adds: `/debug/curation`, `/api/curation/run/{run_id}`, `/api/curation/run/{run_id}/selection`, `/api/curation/run/{run_id}/selection-plan`, `/api/curation/media/{asset_id}/{variant}`.

- [ ] **Step 1: Write failing artifact tests**

Fixtures cover current filenames: `transcript-raw.json`/`transcript.json`, `semantic-chunks.json`/`semantic-beats.json`, `online-candidates.json`/`candidate-metrics.json`, `image-candidates.json`, `edit-plan.json`, `coverage-metrics.json`.

Required assertions:

```python
run = load_curation_run(tmp_path)
assert run.chunks[0].chunk_id == "chunk_001"
assert run.chunks[0].text == "Una frase completa"
assert len(run.chunks[0].shelf.video) <= 3
assert len(run.chunks[0].shelf.images) <= 4
```

Malformed rows go to `run.errors` and do not abort hydration. Video thumbnails remain video preview metadata; they are never reclassified as image candidates.

- [ ] **Step 2: Implement `CurationRun` / `CurationChunkView` adapters**

`CurationChunkView` contains `chunk_id`, `text`, `start`, `end`, `duration`, `intent`, `source_strategy`, and `CandidateShelf`. `CurationRun` contains `run_id`, `input_video`, `output_dir`, `fps`, `chunks`, and `errors`.

- [ ] **Step 3: Write failing API tests**

```python
assert client.get("/debug/curation").status_code == 200
assert "chunks" in client.get("/api/curation/run/default").json()
response = client.post("/api/curation/run/default/selection", json={
    "chunk_id":"chunk_001", "asset_ids":["v1","i1"], "no_broll":False
})
assert [x["track"] for x in response.json()["selected_assets"]] == ["V2", "V3"]
```

Add path traversal tests for media serving.

- [ ] **Step 4: Implement safe endpoints**

Use `run_id="default"` as persisted KURA output fallback after server restart. Request model:

```python
from pydantic import BaseModel, ConfigDict, Field

class SelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_id: str
    asset_ids: list[str] = Field(default_factory=list)
    no_broll: bool = False
```

Media routes never accept raw filesystem paths. Resolve `asset_id` through candidate index, resolve the selected preview/poster path, and verify it is under approved output/cache roots before returning `FileResponse`.

- [ ] **Step 5: Verify and commit**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/unit/test_curation_artifacts.py tests/test_curation_api.py tests/test_debug_server.py -q
git add backend/app/curation_artifacts.py backend/app/debug_server.py tests/unit/test_curation_artifacts.py tests/test_curation_api.py
git commit -m "feat: expose curation API and safe preview routes"
```

---

### Task 6: Modern visual curation HTML

**Files:**
- Create: `backend/app/curation_ui.py`
- Modify: `backend/app/debug_server.py`
- Test: `tests/unit/test_curation_ui.py`

**Interfaces:**
- Produces: `render_curation_page() -> str`.

- [ ] **Step 1: Write failing HTML contract tests**

```python
html = render_curation_page()
for token in ("RAMBLA Curation", 'id="chunk-list"', 'id="filter-selected"',
              'id="selection-summary"', 'id="lightbox"', "IntersectionObserver",
              "data-preview-video", "NO BROLL"):
    assert token in html
assert "cdn.jsdelivr.net" not in html
assert "unpkg.com" not in html
```

- [ ] **Step 2: Implement self-contained dark UI**

Use these tokens:

```css
:root{--bg:#090b0f;--panel:#11141a;--panel2:#171b23;--line:#282e39;--text:#f6f7f9;--muted:#9ca6b5;--accent:#d8ff59;--good:#72e39a;--warn:#ffcc66;--bad:#ff7c82;--radius:16px}
```

Required structure: sticky toolbar; `All / Selected / Needs choice / NO_BROLL / Errors`; transcript-order phrase cards; dominant phrase text; 3-column video shelf; 4-column image shelf; accent selected state/check badge; clear unavailable state.

- [ ] **Step 3: Add real lazy video previews**

Poster paints immediately. `<video muted loop playsinline preload="none">` receives its `src` only via `IntersectionObserver`. Hover/focus plays; leave pauses and resets. No global autoplay storm.

- [ ] **Step 4: Add lightbox and autosave**

Card body opens lightbox. Select control toggles selection without opening it. Every change POSTs:

```json
{"chunk_id":"chunk_001","asset_ids":["asset-a","asset-b"],"no_broll":false}
```

Update V2/V3 chips from server response. On save failure retain local state and show retry banner.

- [ ] **Step 5: Verify and commit**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/unit/test_curation_ui.py tests/test_curation_api.py tests/test_debug_server.py -q
git add backend/app/curation_ui.py backend/app/debug_server.py tests/unit/test_curation_ui.py
git commit -m "feat: add modern visual curation UI"
```

---

### Task 7: Integrate curation stage without repeating expensive upstream work

**Files:**
- Modify: `backend/app/debug_run_cli.py`
- Modify: `backend/app/online_sourcing_cli.py`
- Modify: `docs/RAMBLA_DEBUG_RUNNER.md`
- Test: `tests/test_debug_run_cli.py`

**Interfaces:**
- Existing command remains `python -m backend.app.debug_run_cli --video <video> --output-dir <run-dir>`.

- [ ] **Step 1: Add failing reuse tests**

With existing fake transcript/chunks/candidates, assert curation post-processing does not call ASR again, does not rerun unchanged video discovery, reuses `image-candidates.json`, creates only missing preview metadata, and leaves `resolve_calls=0`.

- [ ] **Step 2: Add final `curation` stage**

Emit:

```text
RAMBLA_EVENT {"stage":"curation","progress":0,"message":"Preparazione preview curation"}
```

Hydrate shelves, materialize only missing previews, persist `curation-run.json`, then emit 100% with counts. Do not alter ASR, Qwen scoring, source strategy, or existing edit-plan logic.

- [ ] **Step 3: Document user URLs**

```text
http://127.0.0.1:8765/debug
http://127.0.0.1:8765/debug/curation
```

State explicitly that `/debug/curation` is the user picker and standard runtime uses no GPT/OpenAI model calls.

- [ ] **Step 4: Verify and commit**

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_debug_run_cli.py tests/test_curation_api.py tests/unit/test_curation_preview.py -q
git add backend/app/debug_run_cli.py backend/app/online_sourcing_cli.py docs/RAMBLA_DEBUG_RUNNER.md tests/test_debug_run_cli.py
git commit -m "feat: integrate curation stage into debug runner"
```

---

### Task 8: Reuse-first KURA acceptance smoke, completion verification and draft PR

**Files:** no new product files expected; runtime artifacts stay untracked.

**User entrypoint:** `http://127.0.0.1:8765/debug/curation`

**Selection artifact:** `Z:\APP REEL TEST\qwen-embedding-smoke\kura-finto-etico-smoke\run\selection-plan.json`

- [ ] **Step 1: Reuse existing KURA transcript/chunks/online candidates/edit-plan/review**

Do not rerun faster-whisper, Qwen or provider discovery just to exercise the UI.

- [ ] **Step 2: Start existing runner**

```powershell
.\tools\start_rambla_debug_runner.ps1
```

- [ ] **Step 3: Materialize only missing lightweight previews**

Record video candidates shown, image candidates shown, preview cache hits, new preview bytes, and preview errors. Do not full-download unselected assets.

- [ ] **Step 4: Acceptance interaction**

For one chunk: select one video + one image; verify V2/V3; refresh and confirm persistence; verify `selection-plan.json`; set another chunk to `NO_BROLL` and confirm exclusivity.

- [ ] **Step 5: Run completion verification once**

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m compileall -q backend
git status --short
git diff feat/editorial-intelligence-style-dna-v1...HEAD --stat
```

Verify no credential/media/model/cache/runtime artifact is staged.

- [ ] **Step 6: Push and open draft PR**

```powershell
git push -u origin feat/curation-ui-v1
```

Draft PR base: `feat/editorial-intelligence-style-dna-v1`; head: `feat/curation-ui-v1`. Report tests, compile, curation URL, preview counts/errors, selection persistence, V2/V3 proof, `resolve_calls=0`, and no GPT/OpenAI runtime dependency.

- [ ] **Step 7: Post concise HANDOFF on Issue #3**

Include branch SHA, draft PR, `TESTABLE=YES`, exact local URL, selection-plan path, tests, preview counts/errors, and any real blocker. Do not merge.

## Self-review against approved spec

- 3 video / 4 image shelf: Tasks 1–2.
- Real playable video previews + image thumbnails: Task 3.
- Modern visual UI, lazy playback, lightbox, filters: Task 6.
- Multi-select / `NO_BROLL` / autosave: Tasks 4–6.
- V2/V3/V4 stacking + `selection-plan.json`: Task 4.
- FastAPI API/media path safety: Task 5.
- Provider-neutral image discovery: Task 2.
- Preview cache/failure isolation: Task 3.
- Rights/provenance retained: Tasks 1–5.
- Existing Debug Runner preserved: Tasks 5–7.
- No Resolve mutation and no GPT/OpenAI runtime dependency: global constraints + Task 8 proof.
- KURA reuse-first acceptance: Task 8.

No task requires a new frontend framework, database, or remote LLM dependency.
