# Online Sourcing Engine V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first real online B-roll slice: transcript beat -> semantic query -> Pexels search -> normalized candidates -> lightweight preview cache -> official Qwen3-VL-Embedding-2B ranking -> selected remote B-roll -> persisted Edit Plan -> inspectable HTML review, with no Resolve mutation.

**Architecture:** Keep the existing modular monolith. Add one provider-neutral remote-candidate boundary, a Pexels adapter, a filesystem preview/provenance cache, and a small sourcing orchestrator. Preserve the existing Director/Qwen ranking ports and extend `build_edit_plan` so each beat can consume an externally sourced candidate set without changing local-only callers.

**Tech Stack:** Python 3.12, httpx 0.27.x, pytest, Pydantic-compatible dictionaries for persisted plan data, official Apache-2.0 `QwenLM/Qwen3-VL-Embedding` loader in the isolated Qwen runtime.

**Spec:** `docs/superpowers/specs/2026-09-12-online-sourcing-engine-v1-design.md`

## Global Constraints

- `REEL_MASTER` is never mutated by Analyze.
- This plan makes zero Resolve API calls.
- Runtime media, API keys, previews, model weights, and downloaded B-roll stay outside Git.
- Ordinary unit tests make zero real network calls and load zero real Qwen weights.
- Pexels credentials come from explicit local configuration/environment only and must never appear in logs, plan JSON, HTML, or provenance records.
- Persist public source page URLs, provider asset IDs, creator attribution when available, query, dimensions, duration, and rights/provider-policy state.
- Full-resolution media is not downloaded until after ranking selects a candidate.
- B-Roll-Finder is behavior/architecture reference only because its repository has no license; do not copy substantial source verbatim.
- MIT/Apache-2.0 source may be adapted only with required attribution/notices when substantial code is reused.
- PR #1 remains draft; no merge is authorized by this plan.

---

### Task 1: Provider-neutral candidates and real Pexels search

**Files:**
- Create: `backend/app/online_assets.py`
- Modify: `pyproject.toml`
- Test: `tests/unit/test_online_assets.py`

**Interfaces:**
- Produces: `RemoteCandidate`, `ProviderError`, `PexelsSource.search(...)`, `filter_candidates(...)`, `dedupe_candidates(...)`.
- Consumes later: Task 2 preview materializer and Task 4 sourcing orchestrator.

- [ ] **Step 1: Write failing normalization/filter tests**

Create tests that inject `httpx.MockTransport` and assert that a Pexels response is normalized without leaking the API key:

```python
async def test_pexels_search_normalizes_vertical_video(tmp_path):
    payload = {
        "videos": [{
            "id": 42,
            "url": "https://www.pexels.com/video/42/",
            "duration": 8,
            "width": 1080,
            "height": 1920,
            "user": {"id": 7, "name": "Alice", "url": "https://www.pexels.com/@alice"},
            "image": "https://images.pexels.com/videos/42/free-video-42.jpg",
            "video_files": [
                {"id": 1, "width": 540, "height": 960, "quality": "sd", "file_type": "video/mp4", "link": "https://cdn.pexels.com/preview.mp4"},
                {"id": 2, "width": 1080, "height": 1920, "quality": "hd", "file_type": "video/mp4", "link": "https://cdn.pexels.com/full.mp4"},
            ],
        }]
    }
    source = PexelsSource(api_key="SECRET", transport=mock_json(payload))
    rows = await source.search("night computer work", orientation="portrait", min_duration=2, max_duration=20, limit=10)
    assert rows[0].provider == "pexels"
    assert rows[0].provider_id == "42"
    assert rows[0].source_page == "https://www.pexels.com/video/42/"
    assert rows[0].preview_url == "https://images.pexels.com/videos/42/free-video-42.jpg"
    assert rows[0].selected_rendition_url == "https://cdn.pexels.com/full.mp4"
    assert "SECRET" not in repr(rows[0])
```

Add tests for missing key, HTTP 401, 429, timeout, non-portrait filtering, duration filtering, deterministic provider-ID dedupe, and stable ordering.

- [ ] **Step 2: Run the focused test file and confirm failure**

Run: `pytest tests/unit/test_online_assets.py -q`

Expected: import/function failures because `online_assets.py` does not exist.

- [ ] **Step 3: Add `httpx` as a runtime dependency**

Move `httpx>=0.27,<0.28` from dev-only to `[project].dependencies`; do not add `requests`.

- [ ] **Step 4: Implement minimal provider contract**

`backend/app/online_assets.py` should define immutable candidate data and one real source:

```python
@dataclass(frozen=True)
class RemoteCandidate:
    provider: str
    provider_id: str
    query: str
    source_page: str
    creator_name: str | None
    creator_page: str | None
    title: str
    description: str
    duration: float
    width: int
    height: int
    orientation: str
    preview_url: str
    selected_rendition_url: str
    rendition_width: int
    rendition_height: int
    rights_state: str
    provider_rank: int


class ProviderError(RuntimeError):
    def __init__(self, provider: str, code: str, message: str):
        super().__init__(f"{provider}:{code}: {message}")
        self.provider = provider
        self.code = code


class PexelsSource:
    endpoint = "https://api.pexels.com/videos/search"

    def __init__(self, api_key: str | None, *, transport=None, timeout: float = 10.0):
        self.api_key = api_key
        self.transport = transport
        self.timeout = timeout

    async def search(self, query: str, *, orientation: str, min_duration: float,
                     max_duration: float, limit: int) -> list[RemoteCandidate]:
        ...
```

Use `httpx.AsyncClient` with `Authorization` header, `params={"query": query, "orientation": "portrait", "per_page": min(limit, 80)}`, bounded timeout, and provider-specific error mapping. Choose the best MP4 rendition deterministically: portrait first, highest dimensions not exceeding provider response availability, then stable ID tie-break.

Never persist request headers or signed/temporary rendition URLs as public provenance; they stay in the in-memory candidate until materialization.

- [ ] **Step 5: Implement deterministic filter/dedupe helpers**

```python
def dedupe_candidates(rows: list[RemoteCandidate]) -> list[RemoteCandidate]:
    seen: set[tuple[str, str]] = set()
    out = []
    for row in rows:
        key = (row.provider, row.provider_id)
        if key not in seen:
            seen.add(key)
            out.append(row)
    return out
```

`filter_candidates` must reject wrong orientation, duration outside bounds, non-positive dimensions, missing public source page, missing preview, and unsupported/non-MP4 rendition metadata before expensive preview/Qwen work.

- [ ] **Step 6: Run focused tests**

Run: `pytest tests/unit/test_online_assets.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

Commit message: `feat: add normalized Pexels candidate search`

---

### Task 2: Safe preview/provenance cache

**Files:**
- Create: `backend/app/asset_cache.py`
- Test: `tests/unit/test_asset_cache.py`

**Interfaces:**
- Consumes: `RemoteCandidate` from Task 1.
- Produces: `PreviewAsset`, `AssetCache.materialize_preview(...)`, `AssetCache.persist_selected(...)`, `public_provenance(...)`.

- [ ] **Step 1: Write failing cache tests**

Tests must verify one preview download per stable key, cache hit on second request, atomic write, deterministic filename, SHA-256 recording, and that public provenance strips query strings/userinfo from source URLs and never contains rendition/download URLs.

```python
async def test_preview_cache_hits_without_second_download(tmp_path):
    cache = AssetCache(tmp_path)
    candidate = candidate_fixture(preview_url="https://img.example/a.jpg")
    calls = 0
    async def fetch(url):
        nonlocal calls
        calls += 1
        return b"jpeg-bytes"
    first = await cache.materialize_preview(candidate, fetch=fetch)
    second = await cache.materialize_preview(candidate, fetch=fetch)
    assert first.path == second.path
    assert calls == 1
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `pytest tests/unit/test_asset_cache.py -q`
Expected: FAIL because cache module is missing.

- [ ] **Step 3: Implement cache paths and atomic materialization**

Use a stable key `sha256(f"{provider}:{provider_id}:{preview_url}")`. Write bytes to `*.tmp`, hash them, then `Path.replace()` into the final location. Store a sidecar JSON containing provider, ID, query, public source page, creator, dimensions, duration, SHA-256, and retrieval timestamp; do not store API keys or auth headers.

- [ ] **Step 4: Implement safe provenance**

`public_provenance(candidate)` returns only public provider metadata and a sanitized source page. Keep the selected rendition URL only in transient download state; once a full asset is cached, durable provenance stores the provider page and content hash/local filename instead.

- [ ] **Step 5: Run focused tests**

Run: `pytest tests/unit/test_asset_cache.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

Commit message: `feat: add remote asset preview and provenance cache`

---

### Task 3: Replace the invalid SentenceTransformer Qwen loader with the official implementation

**Files:**
- Modify: `backend/app/qwen_stack.py`
- Modify: `tests/unit/test_qwen_stack.py`
- Modify: `tests/unit/test_qwen_integration.py`
- Add documentation/notice if official implementation code is vendored: `THIRD_PARTY_NOTICES.md`

**Interfaces:**
- Existing public callable remains: `LocalQwenEmbedder(items: list[Any]) -> list[list[float]]`.
- Internal loader switches to official `Qwen3VLEmbedder.process(...)` behavior documented by Apache-2.0 `QwenLM/Qwen3-VL-Embedding`.

- [ ] **Step 1: Write failing loader-contract tests**

Inject a fake official embedder class so ordinary tests load no model:

```python
def test_local_qwen_embedder_uses_official_input_shape(tmp_path, monkeypatch):
    fake = FakeOfficialEmbedder()
    embedder = LocalQwenEmbedder(config_fixture(tmp_path), factory=lambda path: fake)
    vectors = embedder(["semantic query", str(tmp_path / "frame.jpg")])
    assert fake.seen == [
        {"text": "semantic query", "instruction": RETRIEVAL_INSTRUCTION},
        {"image": str(tmp_path / "frame.jpg")},
    ]
    assert vectors == [[1.0, 0.0], [0.0, 1.0]]
```

Add a regression test proving `sentence_transformers.SentenceTransformer` is never imported by `LocalQwenEmbedder`.

- [ ] **Step 2: Run the Qwen tests and confirm regression failure**

Run: `pytest tests/unit/test_qwen_stack.py tests/unit/test_qwen_integration.py -q`
Expected: FAIL against the current SentenceTransformer loader.

- [ ] **Step 3: Implement factory-based official loader**

Preserve lazy loading. Constructor becomes:

```python
RETRIEVAL_INSTRUCTION = "Retrieve images or videos relevant to the user's visual search query."

class LocalQwenEmbedder(_LocalModel):
    role = "embedding"

    def __init__(self, config: QwenConfig, factory: Callable[[Path], Any] | None = None):
        super().__init__(config)
        self.factory = factory or _load_official_qwen_vl_embedder

    def load(self) -> "LocalQwenEmbedder":
        self.model = self.factory(self._local_path())
        return self

    def __call__(self, items: list[Any]) -> list[list[float]]:
        if self.model is None:
            self.load()
        payload = []
        for index, item in enumerate(items):
            if isinstance(item, str) and Path(item).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                payload.append({"image": item})
            else:
                row = {"text": str(item)}
                if index == 0:
                    row["instruction"] = RETRIEVAL_INSTRUCTION
                payload.append(row)
        result = self.model.process(payload)
        vectors = result.detach().float().cpu().tolist() if hasattr(result, "detach") else result.tolist()
        self.completed_calls += 1
        return vectors
```

`_load_official_qwen_vl_embedder` must import the installed official package/source from the isolated Qwen runtime, not silently fall back to SentenceTransformer. If the official implementation is unavailable, raise `ModelUnavailable` with the exact required package/source name.

- [ ] **Step 4: Update capability detection**

The embedding role must no longer report readiness merely because `sentence_transformers` exists. Capability detection must require the official Qwen VL embedding implementation plus complete local weights.

- [ ] **Step 5: Run Qwen unit tests**

Run: `pytest tests/unit/test_qwen_stack.py tests/unit/test_qwen_integration.py -q`
Expected: PASS with fake/injected loader; no real CUDA load.

- [ ] **Step 6: Preserve one isolated manual smoke command**

Document a command that uses the already approved isolated runtime under `Z:\APP REEL TEST\qwen-embedding-smoke` and prints vector count/dimension/finite check/load time/inference time. It is not part of ordinary pytest.

- [ ] **Step 7: Commit**

Commit message: `fix: use official Qwen VL embedding loader`

---

### Task 4: Source and rank remote candidates per beat

**Files:**
- Create: `backend/app/online_sourcing.py`
- Modify: `backend/app/director_engine.py`
- Test: `tests/unit/test_online_sourcing.py`
- Modify: `tests/unit/test_director_engine.py`

**Interfaces:**
- Produces: `OnlineSourcingEngine.source_beat(...) -> SourcedBeatCandidates` and `source_outline(...)`.
- `build_edit_plan(..., candidate_assets_by_beat: dict[str, list[dict[str, Any]]] | None = None)` remains backward compatible.

- [ ] **Step 1: Write failing orchestration tests**

Use fake Pexels results, fake preview materializer, and fake embedder. Assert that:

1. 2–4 generated queries can fan out concurrently;
2. duplicate provider IDs collapse deterministically;
3. only filtered survivors get previewed;
4. the Qwen ranker receives local preview paths, not remote URLs;
5. the selected candidate contains remote provenance and Qwen score;
6. provider failure yields a safe empty candidate set rather than fabricating B-roll.

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `pytest tests/unit/test_online_sourcing.py tests/unit/test_director_engine.py -q`

- [ ] **Step 3: Implement `OnlineSourcingEngine`**

The orchestrator accepts explicit dependencies:

```python
class OnlineSourcingEngine:
    def __init__(self, *, sources, cache, ranker, max_results_per_query=12, max_preview_candidates=12): ...

    async def source_beat(self, *, beat_id: str, client_id: str,
                          queries: list[str], min_duration: float,
                          max_duration: float) -> dict[str, Any]: ...
```

Search queries concurrently with `asyncio.gather(..., return_exceptions=True)`, normalize/filter/dedupe, materialize a bounded preview pool concurrently, convert previews to the existing asset shape (`kind="image"`, `keyframe_path=<cached preview>`, remote provenance fields), then call `QwenMultimodalRanker.rank` once per beat so query + candidates are embedded as a batch.

Do not download full-resolution media in this task.

- [ ] **Step 4: Extend `build_edit_plan` without breaking local callers**

Add optional `candidate_assets_by_beat`. For a beat with an explicit candidate set, rank/use that set rather than `LocalAssetProvider` output. Persist `source`, `source_page`, `provider_id`, `creator`, `rights_state`, `preview_path`, `embedding_score`, and `selected_full_download=False` in candidate rows.

A remote candidate is client-scoped to the current run/client at normalization time so existing client isolation validation remains meaningful.

- [ ] **Step 5: Run focused tests**

Run: `pytest tests/unit/test_online_sourcing.py tests/unit/test_director_engine.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

Commit message: `feat: rank online B-roll candidates per beat`

---

### Task 5: Enhanced HTML review with thumbnails, provenance, scores, and alternatives

**Files:**
- Modify: `backend/app/director_preview.py`
- Modify: `tests/unit/test_director_preview.py`

**Interfaces:**
- Existing `render_report(plan) -> str` remains the public function.

- [ ] **Step 1: Add failing HTML tests**

Construct a plan with one Pexels candidate and assert the report contains escaped transcript/query, a thumbnail using the local cached preview path or safe file URI, Pexels provider label, public source page, creator attribution, embedding/final score, rights state, selected badge, and alternate rows. Assert it does not contain `Authorization`, API keys, or selected rendition URL.

- [ ] **Step 2: Run preview tests and confirm failure**

Run: `pytest tests/unit/test_director_preview.py -q`

- [ ] **Step 3: Render a compact candidate gallery per B-roll beat**

Keep the existing table summary, but add a `Candidate review` section with cards. Each card must show score/provenance text and use only sanitized links. Do not add JS frameworks or a frontend build step.

- [ ] **Step 4: Run preview tests**

Run: `pytest tests/unit/test_director_preview.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat: show online B-roll evidence in review report`

---

### Task 6: End-to-end offline harness and real Pexels/Qwen smoke boundary

**Files:**
- Create: `backend/app/online_sourcing_cli.py`
- Create: `tests/integration/test_online_sourcing_pipeline.py`
- Modify: `docs/QWEN_DIRECTOR_RUNTIME.md`
- Modify or create: `docs/ONLINE_SOURCING_RUNTIME.md`

**Interfaces:**
- CLI dry-run reads existing transcript/outline artifacts, requires `PEXELS_API_KEY` only for real provider mode, writes `edit-plan.json`, `review.html`, and `online-sourcing-benchmark.json` under an explicit output directory.
- No Resolve calls.

- [ ] **Step 1: Write an integration test with fake network/model dependencies**

Test the whole flow with injected fake source/cache/embedder and assert a complete valid plan plus HTML are written and contain selected remote provenance.

- [ ] **Step 2: Run integration test and confirm failure**

Run: `pytest tests/integration/test_online_sourcing_pipeline.py -q`

- [ ] **Step 3: Implement CLI/harness**

Required arguments:

```text
--transcript PATH
--outline PATH
--client-id ID
--source-frames N
--output-dir PATH
--model-root PATH
--pexels-key-env PEXELS_API_KEY
--max-candidates 12
```

The harness records wall time for search, preview downloads, Qwen load/inference/ranking, cache hits, candidate counts, and final selected score. It refuses to start real Pexels mode without a key and never prints the key.

- [ ] **Step 4: Run all ordinary tests**

Run: `pytest -q`
Expected: all tests pass with no real network/model load.

Run: `python -m compileall backend`
Expected: exit 0.

- [ ] **Step 5: Run the approved real smoke only when credentials/runtime are available**

Use one beat from the existing real reel, Pexels, and the already downloaded Qwen3-VL-Embedding-2B runtime. Record query, result count, preview count, vector dimension, selected provider asset ID, selected score, per-stage timing, VRAM/RAM if available, and cache paths. Do not call Resolve.

- [ ] **Step 6: Verify safety artifacts**

Search generated plan/report/log output for the Pexels API key and `Authorization`; both must be absent. Verify `REEL_MASTER`/Resolve was never touched.

- [ ] **Step 7: Commit**

Commit message: `feat: add Pexels to Qwen sourcing dry run`

---

## Completion Gate

The first slice is complete only when:

1. all ordinary pytest tests pass with network/model doubles;
2. `compileall` passes;
3. the official Qwen loader regression is fixed;
4. a real Pexels search can be normalized and previewed when a key is supplied;
5. a real Qwen smoke ranks those previews using the isolated model runtime;
6. the generated Edit Plan preserves candidates, scores, selection, query, and public provenance;
7. `review.html` visually exposes selected candidate plus alternatives;
8. no secret appears in tracked source or generated review artifacts;
9. no Resolve mutation occurs;
10. changes are published to a review branch/PR and not merged autonomously.

## Follow-on Plan (not part of this completion gate)

After this slice is green: add Pixabay, Coverr, concurrent multi-provider fan-out, selected full-resolution download/reuse cache, Qwen3-VL-Reranker-2B benchmark, multi-frame verification, real Qwen Director/query planner, YouTube discovery with explicit rights gate, then Resolve-panel review/apply controls.
