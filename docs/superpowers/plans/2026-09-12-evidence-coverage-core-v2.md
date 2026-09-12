# Evidence Coverage Core V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade RAMBLA from beat-level, portrait-only stock selection to short evidence-first coverage slots with A/B proposals, mixed-aspect crop safety, long-video scene localization, and bounded partial acquisition, while keeping Resolve completely out of Analyze.

**Architecture:** Keep the existing modular backend and online-sourcing pipeline. Add focused domain modules for coverage planning, crop safety, scene localization, and acquisition; adapt the existing provider/ranking path rather than replacing it. This plan implements the V2 engine core only; transcription benchmarking and the Resolve panel/Apply adapters are intentionally separate follow-on plans so each subsystem remains independently testable.

**Tech Stack:** Python 3.12, dataclasses/Protocol, asyncio/httpx, pytest/pytest-asyncio, FFmpeg/yt-dlp behind injectable process adapters, existing Qwen3-VL-Embedding-2B ranker, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-12-resolve-panel-evidence-sourcing-v2-design.md`

## Global Constraints

- Analyze must never mutate DaVinci Resolve.
- Source media may be portrait, landscape, square, or 4:3; no portrait-only eligibility rule.
- Default coverage target is 3.5 s with a soft 2.5–4.5 s range; these values must be configurable inputs, not magic constants scattered through the codebase.
- Every successful coverage slot should preserve at least proposal A and proposal B when two usable candidates exist.
- Evidence/repertory sources outrank generic stock when semantic/evidence relevance is stronger.
- Long-video acquisition should fetch bounded windows or stills rather than full media when supported.
- Remote cuts do not need frame-perfect boundaries; wider bounded fetch + local trim is acceptable.
- Qwen ranks lightweight preview/scene evidence before large media acquisition.
- Persist source page, source time range, rights/provenance state, crop score, Qwen score, and selected proposal.
- No credentials, signed URLs, model weights, downloaded B-roll, or social cookies in Git.
- Heavy runtime/model/cache artifacts remain under `Z:\APP REEL TEST` in local runs.
- PR #1 and PR #4 remain draft; no merge without explicit user approval.

---

## File Structure

- Create `backend/app/coverage.py` — `CoverageSlot` schema plus deterministic V1 coverage planner boundary.
- Create `backend/app/crop_safety.py` — geometry-only crop feasibility/scoring contract; later vision tracking can replace internals.
- Modify `backend/app/online_assets.py` — remove portrait-only provider contract and allow `orientation=None`/mixed aspect.
- Modify `backend/app/online_sourcing.py` — source per coverage slot, attach crop evidence, retain diverse A/B proposals.
- Modify `backend/app/director_engine.py` — persist `coverage_slots[]` without breaking legacy beat/caption validation during migration.
- Modify `backend/app/director_preview.py` — render slot-level A/B proposal cards and crop/source-time evidence.
- Create `backend/app/scene_locator.py` — coarse-to-fine scene window contract and deterministic scorer over lightweight evidence.
- Create `backend/app/acquisition.py` — provider-neutral `AcquisitionAdapter`, FFmpeg trim helper, and yt-dlp command builder/process wrapper.
- Create `backend/app/youtube_source.py` — YouTube discovery metadata normalization plus bounded-section acquisition adapter; no full-profile/social scraping.
- Modify `backend/app/asset_cache.py` — persist bounded windows/stills separately from full selected stock media.
- Tests: create `tests/unit/test_coverage.py`, `test_crop_safety.py`, `test_scene_locator.py`, `test_acquisition.py`, `test_youtube_source.py`; modify existing online-sourcing/director/preview tests.

---

### Task 1: Mixed-aspect candidates and crop-safety contract

**Files:**
- Create: `backend/app/crop_safety.py`
- Modify: `backend/app/online_assets.py`
- Test: `tests/unit/test_crop_safety.py`
- Test: `tests/unit/test_online_assets.py`

**Interfaces:**
- Consumes: existing `RemoteCandidate` width/height metadata.
- Produces: `CropAssessment(score: float, crop_box: tuple[float,float,float,float], needs_tracking: bool, usable: bool, reason: str)` and `evaluate_static_crop(width: int, height: int, target_aspect: float = 9/16) -> CropAssessment`.
- Provider `search(..., orientation: str | None, ...)`; `None` means mixed aspect and sends no orientation filter upstream.

- [ ] **Step 1: Write failing crop-safety tests**

```python
from backend.app.crop_safety import evaluate_static_crop


def test_landscape_can_survive_center_9x16_crop():
    result = evaluate_static_crop(1920, 1080)
    assert result.usable is True
    assert 0.0 < result.score < 1.0
    assert result.crop_box[2] - result.crop_box[0] < 1.0


def test_portrait_9x16_is_high_confidence():
    result = evaluate_static_crop(1080, 1920)
    assert result.usable is True
    assert result.score >= 0.95
```

- [ ] **Step 2: Run crop test and verify RED**

Run: `pytest tests/unit/test_crop_safety.py -q`
Expected: FAIL because `backend.app.crop_safety` does not exist.

- [ ] **Step 3: Implement deterministic geometry evaluator**

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CropAssessment:
    score: float
    crop_box: tuple[float, float, float, float]
    needs_tracking: bool
    usable: bool
    reason: str


def evaluate_static_crop(width: int, height: int, target_aspect: float = 9 / 16) -> CropAssessment:
    if width <= 0 or height <= 0 or target_aspect <= 0:
        raise ValueError("positive source geometry and target aspect required")
    source_aspect = width / height
    if source_aspect >= target_aspect:
        normalized_width = target_aspect / source_aspect
        left = (1.0 - normalized_width) / 2.0
        crop = (left, 0.0, left + normalized_width, 1.0)
        retained = normalized_width
    else:
        normalized_height = source_aspect / target_aspect
        top = (1.0 - normalized_height) / 2.0
        crop = (0.0, top, 1.0, top + normalized_height)
        retained = normalized_height
    score = max(0.05, min(1.0, retained))
    return CropAssessment(
        score=round(score, 4),
        crop_box=crop,
        needs_tracking=score < 0.75,
        usable=score >= 0.18,
        reason="static center-crop geometry",
    )
```

- [ ] **Step 4: Add failing mixed-aspect provider tests**

```python
@pytest.mark.asyncio
async def test_pexels_mixed_aspect_omits_orientation_query(mock_transport):
    source = PexelsSource("secret", transport=mock_transport)
    rows = await source.search("Olimpia Peroni interview", orientation=None, min_duration=1, max_duration=90, limit=10)
    assert {row.orientation for row in rows} >= {"portrait", "landscape"}
```

Also assert that `filter_candidates(..., orientation=None, ...)` keeps valid rows regardless of aspect.

- [ ] **Step 5: Modify `online_assets.py` minimally**

Change signatures to `orientation: str | None`; validate only when non-`None`; omit the Pexels `orientation` query parameter when `None`; make `_best_rendition()` prefer source-orientation match but not require it; make `filter_candidates()` skip orientation equality when `None`.

- [ ] **Step 6: Run focused tests**

Run: `pytest tests/unit/test_crop_safety.py tests/unit/test_online_assets.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/crop_safety.py backend/app/online_assets.py tests/unit/test_crop_safety.py tests/unit/test_online_assets.py
git commit -m "feat: allow mixed-aspect evidence candidates"
```

---

### Task 2: Coverage-slot domain model and 3–4 second planning

**Files:**
- Create: `backend/app/coverage.py`
- Modify: `backend/app/director_engine.py`
- Test: `tests/unit/test_coverage.py`
- Modify: `tests/unit/test_director_engine.py`

**Interfaces:**
- Consumes: normalized beat `start_seconds`, `end_seconds`, `intent`, transcript context, and `broll_queries`.
- Produces: immutable `CoverageSlot` records and `plan_coverage_slots(beats, *, target_seconds=3.5, min_seconds=2.5, max_seconds=4.5, min_gap_seconds=1.0) -> list[CoverageSlot]`.
- `build_edit_plan(..., coverage_slots_by_beat: dict[str, list[dict]] | None = None)` persists slot records while retaining legacy beat fields during migration.

- [ ] **Step 1: Write failing coverage tests**

```python
from backend.app.coverage import plan_coverage_slots


def test_long_beat_gets_short_slot_not_full_beat():
    beats = [{"id": "b1", "start_seconds": 10.0, "end_seconds": 18.0,
              "intent": "show named event", "broll_queries": ["named event"]}]
    slots = plan_coverage_slots(beats)
    assert len(slots) == 1
    assert 2.5 <= slots[0].end_seconds - slots[0].start_seconds <= 4.5
    assert slots[0].start_seconds >= 10.0
    assert slots[0].end_seconds <= 18.0
    assert slots[0].minimum_proposals == 2


def test_short_beat_is_not_extended_outside_beat():
    beats = [{"id": "b1", "start_seconds": 2.0, "end_seconds": 4.0,
              "intent": "show source", "broll_queries": ["source"]}]
    slots = plan_coverage_slots(beats)
    assert slots[0].start_seconds == 2.0
    assert slots[0].end_seconds == 4.0
```

- [ ] **Step 2: Run and verify RED**

Run: `pytest tests/unit/test_coverage.py -q`
Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement `CoverageSlot` and deterministic planner**

Use:

```python
@dataclass(frozen=True, slots=True)
class CoverageSlot:
    id: str
    beat_id: str
    start_seconds: float
    end_seconds: float
    visual_intent: str
    queries: tuple[str, ...]
    evidence_class: str
    minimum_proposals: int = 2
```

V1 rule: only beats with non-empty `broll_queries` produce slots; center a target-length window inside the beat; clamp to beat boundaries; never manufacture multiple slots from one beat yet unless the beat exceeds `2 * target_seconds + min_gap_seconds`, in which case make two non-overlapping target windows near the first and last third.

- [ ] **Step 4: Add migration tests to `test_director_engine.py`**

Assert the plan contains `coverage_slots`, slot ranges lie inside source duration, and legacy `beats`/captions remain valid and reproducible.

- [ ] **Step 5: Modify `director_engine.py`**

Add optional `coverage_slots_by_beat`; persist normalized slots under top-level `coverage_slots`; add validation for positive duration, no slot overlap, slot inside owning beat, and `minimum_proposals >= 1`. Do not remove old beat fields in this task.

- [ ] **Step 6: Run focused tests**

Run: `pytest tests/unit/test_coverage.py tests/unit/test_director_engine.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/coverage.py backend/app/director_engine.py tests/unit/test_coverage.py tests/unit/test_director_engine.py
git commit -m "feat: plan short evidence coverage slots"
```

---

### Task 3: A/B proposal selection with crop-aware diversity

**Files:**
- Modify: `backend/app/online_sourcing.py`
- Create: `backend/app/proposals.py`
- Test: `tests/unit/test_proposals.py`
- Modify: `tests/unit/test_online_sourcing.py`

**Interfaces:**
- Consumes: Qwen-ranked candidate dictionaries containing `score`, source/provider identity, width/height, and provenance.
- Produces: `select_proposals(candidates: list[dict], *, minimum=2, target_aspect=9/16) -> dict` returning `proposal_A`, `proposal_B`, optional `proposal_C`, and `review_state`.

- [ ] **Step 1: Write failing proposal tests**

```python
from backend.app.proposals import select_proposals


def test_two_distinct_proposals_are_retained():
    rows = [
        {"id": "youtube:1", "score": .91, "source": "youtube", "width": 1920, "height": 1080, "provider_id": "1"},
        {"id": "pexels:2", "score": .84, "source": "pexels", "width": 1080, "height": 1920, "provider_id": "2"},
    ]
    result = select_proposals(rows)
    assert result["proposal_A"]["id"] == "youtube:1"
    assert result["proposal_B"]["id"] == "pexels:2"
    assert result["review_state"] == "READY"


def test_single_candidate_is_explicitly_marked():
    result = select_proposals([{"id": "one", "score": .8, "source": "pexels", "width": 1080, "height": 1920, "provider_id": "1"}])
    assert result["proposal_B"] is None
    assert result["review_state"] == "SINGLE_PROPOSAL"
```

- [ ] **Step 2: Run RED**

Run: `pytest tests/unit/test_proposals.py -q`
Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement proposal selector**

For each row call `evaluate_static_crop`; compute `final_score = 0.8 * semantic_score + 0.2 * crop_score`; sort descending; A is top. B is first candidate with a different `(source, provider_id)` and not the same `preview_sha256`; C is next distinct candidate. Persist `crop_score`, `crop_box`, `needs_tracking`, and `final_score` into returned proposal dictionaries.

- [ ] **Step 4: Wire `OnlineSourcingEngine.source_beat()` to mixed aspect and proposal sets**

Call providers with `orientation=None`; retain raw ranked candidates but also return a `proposals` object from `select_proposals()`. Keep provider errors isolated.

- [ ] **Step 5: Add online-sourcing integration assertions**

Assert mixed portrait/landscape results survive, proposal A/B are different, Qwen score remains inspectable, and crop score exists.

- [ ] **Step 6: Run focused tests**

Run: `pytest tests/unit/test_proposals.py tests/unit/test_online_sourcing.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/proposals.py backend/app/online_sourcing.py tests/unit/test_proposals.py tests/unit/test_online_sourcing.py
git commit -m "feat: retain diverse A B b-roll proposals"
```

---

### Task 4: Persist slot-level proposals and render review cards

**Files:**
- Modify: `backend/app/director_engine.py`
- Modify: `backend/app/director_preview.py`
- Modify: `backend/app/online_sourcing_cli.py`
- Test: `tests/unit/test_director_online_candidates.py`
- Test: `tests/unit/test_director_preview.py`

**Interfaces:**
- Consumes: `CoverageSlot` plus `OnlineSourcingEngine` result with `proposals`.
- Produces: Edit Plan `coverage_slots[]` with proposal A/B/C, selected proposal ID, review state, crop metadata, and provenance; review HTML cards switchable at the data level without rerunning discovery.

- [ ] **Step 1: Add failing plan test**

Create a slot result with landscape A and portrait B. Assert serialized plan preserves both, selected defaults to A, `review_state == "READY"`, and source/crop/Qwen fields are present.

- [ ] **Step 2: Run RED**

Run: `pytest tests/unit/test_director_online_candidates.py -q`
Expected: FAIL on missing slot proposal fields.

- [ ] **Step 3: Extend Edit Plan migration schema**

Normalize each proposal to fields:

```python
{
    "id": "youtube:abc@452.0-456.0",
    "source": "youtube",
    "source_page": "https://...",
    "source_start_seconds": 452.0,
    "source_end_seconds": 456.0,
    "preview_path": "...",
    "qwen_score": 0.88,
    "crop_score": 0.72,
    "final_score": 0.848,
    "crop_box": [0.34, 0.0, 0.66, 1.0],
    "rights_state": "review_required",
}
```

Validator must require selected proposal to be one of the slot proposals.

- [ ] **Step 4: Add failing HTML tests**

Assert `review.html` contains slot time range, `Proposal A`, `Proposal B`, Qwen score, crop score, source timestamp when present, and public source link; untrusted text remains escaped.

- [ ] **Step 5: Update `director_preview.py`**

Render one card group per coverage slot; use `<img>` for preview images when present; render A/B/C labels and selected state; never embed temporary download URLs.

- [ ] **Step 6: Update CLI orchestration**

Have `_source_outline()` source each planned coverage slot rather than entire beat duration, then pass slot result map into `build_edit_plan()`.

- [ ] **Step 7: Run focused tests**

Run: `pytest tests/unit/test_director_online_candidates.py tests/unit/test_director_preview.py -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/director_engine.py backend/app/director_preview.py backend/app/online_sourcing_cli.py tests/unit/test_director_online_candidates.py tests/unit/test_director_preview.py
git commit -m "feat: persist slot-level evidence proposals"
```

---

### Task 5: Scene locator contract for long videos

**Files:**
- Create: `backend/app/scene_locator.py`
- Test: `tests/unit/test_scene_locator.py`

**Interfaces:**
- Consumes: lightweight `SceneEvidence(timestamp_seconds, text, image_path, metadata_score)` samples plus a query and an injected similarity callable.
- Produces: ranked `SceneWindow(start_seconds, end_seconds, score, evidence_timestamps)` windows; no network/download logic.

- [ ] **Step 1: Write failing coarse-to-fine tests**

```python
from backend.app.scene_locator import SceneEvidence, locate_windows


def test_locator_builds_short_window_around_best_evidence():
    evidence = [
        SceneEvidence(10, "intro", None, .1),
        SceneEvidence(75, "robot factory", None, .9),
        SceneEvidence(80, "robot closeup", None, .8),
    ]
    windows = locate_windows("industrial robot", evidence, target_seconds=3.5, source_duration=600)
    assert 72 <= windows[0].start_seconds <= 78
    assert 2.5 <= windows[0].end_seconds - windows[0].start_seconds <= 4.5
```

- [ ] **Step 2: Run RED**

Run: `pytest tests/unit/test_scene_locator.py -q`
Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement deterministic locator**

Define:

```python
@dataclass(frozen=True, slots=True)
class SceneEvidence:
    timestamp_seconds: float
    text: str
    image_path: str | None
    metadata_score: float

@dataclass(frozen=True, slots=True)
class SceneWindow:
    start_seconds: float
    end_seconds: float
    score: float
    evidence_timestamps: tuple[float, ...]
```

Cluster evidence timestamps within 8 seconds; cluster score is max score + 0.1 * supporting-sample count capped at 1.0; center a target-length window around weighted mean; clamp to `[0, source_duration]`; return top 3 non-overlapping windows.

- [ ] **Step 4: Add edge tests**

Test source-start/source-end clamping, duplicate evidence timestamps, and no evidence returns `[]`.

- [ ] **Step 5: Run focused tests**

Run: `pytest tests/unit/test_scene_locator.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/scene_locator.py tests/unit/test_scene_locator.py
git commit -m "feat: add long-video scene locator"
```

---

### Task 6: Bounded acquisition and YouTube section adapter

**Files:**
- Create: `backend/app/acquisition.py`
- Create: `backend/app/youtube_source.py`
- Modify: `backend/app/asset_cache.py`
- Test: `tests/unit/test_acquisition.py`
- Test: `tests/unit/test_youtube_source.py`
- Modify: `tests/unit/test_asset_cache.py`

**Interfaces:**
- Produces `AcquisitionRequest(source_url, start_seconds, end_seconds, margin_seconds, mode)` and `AcquiredArtifact(path, kind, source_start_seconds, source_end_seconds, sha256, cache_hit)`.
- `YtDlpAcquisitionAdapter.build_command(request, output_path) -> list[str]` must use bounded section syntax and never include credentials/cookies in persisted metadata.
- `trim_with_ffmpeg(input_path, output_path, start_seconds, end_seconds, runner)` provides precise local trim after a wider remote fetch.

- [ ] **Step 1: Write command-builder tests first**

```python
from backend.app.acquisition import AcquisitionRequest, YtDlpAcquisitionAdapter


def test_ytdlp_fetches_bounded_window_with_margin(tmp_path):
    req = AcquisitionRequest(
        source_url="https://www.youtube.com/watch?v=abc",
        start_seconds=452.0,
        end_seconds=456.0,
        margin_seconds=2.0,
        mode="video_window",
    )
    cmd = YtDlpAcquisitionAdapter().build_command(req, tmp_path / "window.mp4")
    joined = " ".join(cmd)
    assert "--download-sections" in cmd
    assert "*450.000-458.000" in joined
    assert "--force-keyframes-at-cuts" not in cmd
```

- [ ] **Step 2: Run RED**

Run: `pytest tests/unit/test_acquisition.py -q`
Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement pure command builders and injected runner**

`YtDlpAcquisitionAdapter.acquire()` calls an injected async/sync process runner; production default uses `subprocess.run(..., check=True, capture_output=True, text=True)` and raises sanitized `AcquisitionError(code)` without echoing raw URLs with query strings. Build command with `yt-dlp --download-sections *START-END --merge-output-format mp4 -o OUTPUT URL`.

- [ ] **Step 4: Add FFmpeg trim tests**

Assert command uses `-ss START -to END -i INPUT -c copy OUTPUT`; tests inject a runner and never require system FFmpeg in CI.

- [ ] **Step 5: Implement YouTube discovery normalization**

`backend/app/youtube_source.py` defines `YouTubeCandidate` with public watch URL, video ID, title, duration, creator, optional transcript/storyboard evidence, rights state default `review_required`, and no assumption of publishability. Discovery itself must be an injectable protocol so unit tests use fixture payloads; do not add API secrets to CI.

- [ ] **Step 6: Add cache support for windows/stills**

Extend `AssetCache` with `materialize_acquired_window()` metadata sidecar containing provider/source page/source start/end/content hash, but never persisted signed media URL.

- [ ] **Step 7: Run focused tests**

Run: `pytest tests/unit/test_acquisition.py tests/unit/test_youtube_source.py tests/unit/test_asset_cache.py -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/acquisition.py backend/app/youtube_source.py backend/app/asset_cache.py tests/unit/test_acquisition.py tests/unit/test_youtube_source.py tests/unit/test_asset_cache.py
git commit -m "feat: acquire bounded online video windows"
```

---

### Task 7: End-to-end fake long-video evidence slice and CI gate

**Files:**
- Create: `tests/integration/test_evidence_coverage_pipeline.py`
- Modify: `.github/workflows/online-sourcing-tests.yml`
- Modify: `backend/app/online_sourcing_cli.py`

**Interfaces:**
- Consumes all Tasks 1–6 with fake discovery/network/process adapters.
- Produces one deterministic complete plan containing a 3–4 s coverage slot, mixed-aspect A/B proposals, one long-video timestamped proposal, and one bounded acquired artifact; Resolve call count remains zero.

- [ ] **Step 1: Write failing integration test**

The test fixture must model a 12-second talking-head clip with one evidence beat. Fake sources return: YouTube landscape exact evidence, Pexels portrait generic fallback, and a second distinct source. Fake Qwen scores YouTube highest. Assert:

```python
assert 2.5 <= slot["end_seconds"] - slot["start_seconds"] <= 4.5
assert slot["proposal_A"]["source"] == "youtube"
assert slot["proposal_B"] is not None
assert slot["proposal_A"]["source_start_seconds"] == 75.0
assert slot["proposal_A"]["acquired_path"].endswith(".mp4")
assert plan["resolve_calls"] == 0
```

- [ ] **Step 2: Run RED**

Run: `pytest tests/integration/test_evidence_coverage_pipeline.py -q`
Expected: FAIL until orchestration wires slot sourcing, proposals, scene location, and acquisition together.

- [ ] **Step 3: Wire orchestration minimally**

In `online_sourcing_cli.py`, plan coverage slots first, source each slot, call a scene locator only for candidates carrying scene evidence, acquire only selected A and optionally B according to `--acquire-alternates`, then persist plan/report/benchmark. Default `--acquire-alternates` is false to minimize bandwidth.

- [ ] **Step 4: Add benchmark fields**

Persist `coverage_slot_count`, `proposal_count`, `scene_localization_seconds`, `acquisition_seconds`, `downloaded_bytes` when known, `crop_tracking_required_count`, and `resolve_calls: 0`.

- [ ] **Step 5: Run full verification locally/CI**

Run:

```bash
pytest -q
python -m compileall backend
```

Expected: all tests PASS; compileall exits 0.

- [ ] **Step 6: Ensure GitHub Actions runs the same gates**

Workflow must install test dependencies, run `pytest -q`, then `python -m compileall backend`. Do not add real network/provider secrets.

- [ ] **Step 7: Commit**

```bash
git add backend/app/online_sourcing_cli.py tests/integration/test_evidence_coverage_pipeline.py .github/workflows/online-sourcing-tests.yml
git commit -m "test: prove evidence coverage pipeline"
```

---

## Follow-on plans intentionally separated from this plan

### Plan B — Transcription provider benchmark

Implement a common `TranscriptionProvider` result schema, adapters for existing local/faster-whisper artifacts and programmatically retrievable Resolve transcription, benchmark accuracy/timing/timestamp quality on the same reel fixture, and select default/fallback by measured result. This plan must not be coupled to sourcing or Resolve Apply.

### Plan C — Resolve panel and Apply adapters

Build localhost API/control plane plus Resolve Workflow Integration thin panel for Analyze/progress/slot A/B review/disable/regenerate/approve. Separately implement `MCPResolveApplyAdapter`, `NativeResolveApplyAdapter`, and fake CI adapter consuming only a frozen plan. Resolve mutation remains frozen until an explicit later user approval enables a smoke test on a duplicate timeline.

## Plan self-review

- Spec coverage in this plan: mixed aspect, 3–4 s slots, A/B alternatives, crop safety, evidence-first proposal scoring boundary, long-video scene localization, partial acquisition, screengrab/window-ready acquisition interface, provenance, speed-by-bounded-download, zero Resolve mutation.
- Deliberately deferred with explicit follow-on plans: Resolve-vs-local ASR benchmark; Resolve panel; MCP/native Apply adapters.
- No placeholders (`TBD`, `TODO`, “implement later”) are used as implementation instructions.
- Type names are consistent across tasks: `CoverageSlot`, `CropAssessment`, proposal dictionaries, `SceneEvidence`, `SceneWindow`, `AcquisitionRequest`, `AcquiredArtifact`.
