# RAMBLA Editorial Intelligence + StyleDNA V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade RAMBLA from semantic-only B-roll ranking to an evidence-first editorial selection engine that can distinguish a merely relevant clip from a strong, specific, visually useful insert and can reproduce two independent reference style families: Factanza-like evidence/editorial and Olimpia-like social/kinetic.

**Architecture:** Extend the existing Taste/VisualRoute/online-sourcing stack rather than replacing it. Add an `EvidenceIntent` layer before search, a source-class strategy, multi-axis editorial scoring with hard quality gates, composition-aware coverage/presentation modes, richer review persistence, and an offline reference StyleDNA fingerprint analyzer. Existing Qwen embedding, SceneLocator, bounded acquisition, A/B proposals, provenance, client isolation, and zero-Resolve analysis remain intact.

**Tech Stack:** Python 3.12, dataclasses, stdlib `json/hashlib/pathlib/subprocess/statistics`, existing Qwen adapters, FFmpeg/ffprobe through injected runners, existing online source adapters, pytest/pytest-asyncio, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-14-editorial-intelligence-style-dna-v1-design.md`

## Global Constraints

- Branch implementation from `feat/resolve-panel-safe-v1`; use implementation branch `feat/editorial-intelligence-style-dna-v1`.
- Keep the original dirty local checkout untouched. Work in the clean RAMBLA smoke/worktree or another isolated worktree.
- Never mutate Resolve during this plan. Every test/smoke must report or preserve `resolve_calls=0`.
- Never modify ComfyUI, global Python, unrelated user files, credentials, or system configuration.
- Do not commit the supplied Factanza/Olimpia media, downloaded B-roll, Qwen weights, caches, previews, runtime logs, or client assets.
- No individual download may exceed the user's 5 GiB autonomy boundary.
- Preserve client isolation and existing provenance/rights fields.
- Exact evidence / exact subject outranks generic semantic similarity. Generic stock is a last fallback.
- Style/taste may break a close editorial tie; it may never rescue a semantically wrong candidate.
- A normal successful B-roll slot retains at least two meaningfully different proposals A/B. If fewer than two pass the quality floor, escalate search before degrading.
- If nothing strong passes, persist `NO_BROLL_QUALITY_FLOOR` rather than weak filler.
- Existing behavior without editorial context remains backward-compatible where current tests depend on it.
- Use red/green TDD for every task. Run focused tests before each commit and full `pytest -q` plus `python -m compileall backend` at the completion gate.
- Keep the implementation PR draft and target the unified branch `feat/resolve-panel-safe-v1`; do not merge autonomously and do not update `main`.

---

### Task 1: Add StyleDNA schema and EvidenceIntent planning

**Files:**
- Modify: `backend/app/taste_profile.py`
- Create: `backend/app/evidence_intent.py`
- Modify: `backend/app/visual_routing.py`
- Modify: `tests/unit/test_taste_profile.py`
- Create: `tests/unit/test_evidence_intent.py`
- Modify: `.github/workflows/online-sourcing-tests.yml`

**Interfaces:**
- Produces `ReferenceStyleProfile`, `StyleDNA`, and `TasteContext.style_dna`.
- Produces `EvidenceIntent` and `plan_evidence_intent(slot, context, route, taste) -> EvidenceIntent`.
- Consumes the existing `VisualRouteDecision`; does not invoke a model or provider.

- [ ] **Step 1: Write failing StyleDNA tests**

Add tests proving independent reference fingerprints remain independent, style mix is validated/canonicalized, and the canonical taste hash changes when StyleDNA changes but stays stable across equivalent objects.

```python
from dataclasses import replace

from backend.app.taste_profile import ReferenceStyleProfile, StyleDNA, TasteProfile, canonical_taste_hash


def _style() -> StyleDNA:
    return StyleDNA(
        reference_profiles=(
            ReferenceStyleProfile(
                id="factanza_evidence_editorial",
                speaker_persistence=0.82,
                coverage_density=0.58,
                median_insert_seconds=3.9,
                route_mix={"RECEIPT": 0.42, "ARCHIVAL": 0.22, "STOCK": 0.02},
                presentation_mix={"SPEAKER_PLUS_EVIDENCE_TOP": 0.45, "FULL_FRAME_CUTAWAY": 0.25},
            ),
            ReferenceStyleProfile(
                id="olimpia_social_kinetic",
                speaker_persistence=0.62,
                coverage_density=0.82,
                median_insert_seconds=1.2,
                route_mix={"ENTITY": 0.30, "CULTURAL": 0.20, "STOCK": 0.01},
                presentation_mix={"FULL_FRAME_CUTAWAY": 0.72},
            ),
        ),
        active_style_mix={"factanza_evidence_editorial": 0.7, "olimpia_social_kinetic": 0.3},
        generic_stock_penalty=0.35,
        exact_evidence_bonus=0.20,
        source_native_bonus=0.10,
        minimum_editorial_quality=0.55,
        minimum_evidence_specificity_by_route={"RECEIPT": 0.75, "ENTITY": 0.65},
        maximum_repetition_by_source_or_motif=1,
    )


def test_style_dna_participates_in_canonical_hash():
    base = TasteProfile(client_id="c", version=1, approved=True, style_dna=_style())
    assert canonical_taste_hash(base) == canonical_taste_hash(replace(base))
    changed = replace(base, style_dna=replace(_style(), generic_stock_penalty=0.5))
    assert canonical_taste_hash(base) != canonical_taste_hash(changed)
```

- [ ] **Step 2: Run RED**

Run: `pytest tests/unit/test_taste_profile.py -q`
Expected: FAIL because StyleDNA types/field do not exist.

- [ ] **Step 3: Implement immutable StyleDNA primitives**

Add frozen dataclasses with validation. All bounded scalar preferences are `0..1`; `median_insert_seconds > 0`; style mix keys must reference a known profile and positive mix weights must normalize deterministically to sum `1.0`. Extend `_profile_payload()` and `TasteContext` so the active immutable style snapshot participates in `canonical_taste_hash()`.

Required shape:

```python
@dataclass(frozen=True)
class ReferenceStyleProfile:
    id: str
    speaker_persistence: float
    coverage_density: float
    median_insert_seconds: float
    route_mix: Mapping[str, float] = field(default_factory=dict)
    presentation_mix: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class StyleDNA:
    reference_profiles: tuple[ReferenceStyleProfile, ...] = ()
    active_style_mix: Mapping[str, float] = field(default_factory=dict)
    generic_stock_penalty: float = 0.0
    exact_evidence_bonus: float = 0.0
    source_native_bonus: float = 0.0
    still_document_tolerance: float = 0.5
    cultural_reference_tolerance: float = 0.5
    split_layout_preference: float = 0.5
    full_screen_preference: float = 0.5
    visual_grit_tolerance: float = 0.5
    minimum_editorial_quality: float = 0.5
    minimum_evidence_specificity_by_route: Mapping[str, float] = field(default_factory=dict)
    maximum_repetition_by_source_or_motif: int = 1
```

- [ ] **Step 4: Write failing EvidenceIntent tests**

```python
from backend.app.evidence_intent import plan_evidence_intent


def test_quote_requires_exact_receipt(taste):
    intent = plan_evidence_intent(
        {"transcript": 'Ha scritto "non venderemo i dati"', "intent": "show the claim"},
        "Si parla del post ufficiale della società.",
        "RECEIPT",
        taste,
    )
    assert intent.evidence_intent_type == "EXACT_RECEIPT"
    assert intent.specificity_required >= 0.75
    assert "generic stock" in intent.unacceptable_substitutions
    assert intent.can_use_still is True


def test_named_product_prefers_exact_ui_not_generic_tutorial(taste):
    intent = plan_evidence_intent(
        {"transcript": "In ComfyUI collego questi due nodi", "intent": "show actual workflow"},
        "software workflow",
        "PRODUCT_UI",
        taste,
    )
    assert intent.evidence_intent_type == "PRODUCT_UI_DEMO"
    assert "generic software tutorial" in intent.unacceptable_substitutions
```

- [ ] **Step 5: Implement `EvidenceIntent`**

Use deterministic routing first. Persist exactly these fields: `evidence_intent_type`, `target_entities`, `target_event_or_claim`, `acceptable_visual_forms`, `unacceptable_substitutions`, `specificity_required`, `can_use_still`, `can_use_composite_with_speaker`, `fallback_route_order`. No provider call occurs here.

- [ ] **Step 6: Run GREEN and commit**

Run: `pytest tests/unit/test_taste_profile.py tests/unit/test_visual_routing.py tests/unit/test_evidence_intent.py -q`
Expected: PASS.

Also add `feat/editorial-intelligence-style-dna-v1` to `.github/workflows/online-sourcing-tests.yml`.

Commit:

```bash
git add backend/app/taste_profile.py backend/app/evidence_intent.py backend/app/visual_routing.py tests/unit/test_taste_profile.py tests/unit/test_evidence_intent.py .github/workflows/online-sourcing-tests.yml
git commit -m "feat: add StyleDNA and evidence intent planning"
```

---

### Task 2: Add source-class strategy and escalation order

**Files:**
- Create: `backend/app/source_strategy.py`
- Modify: `backend/app/online_assets.py`
- Modify: `backend/app/youtube_source.py`
- Create: `tests/unit/test_source_strategy.py`
- Modify: `tests/unit/test_online_assets.py`
- Modify: `tests/unit/test_youtube_source.py`

**Interfaces:**
- Produces source classes: `EXACT_RECEIPT`, `EXACT_ENTITY_EVENT`, `SOURCE_NATIVE_SOCIAL`, `ARCHIVAL_REPERTORY`, `PRODUCT_UI_DEMO`, `CULTURAL_REFERENCE`, `CLOSE_SEMANTIC_EDITORIAL`, `GENERIC_STOCK`.
- Produces `SourceStrategy(classes, query_families)` and `plan_source_strategy(intent, route, taste)`.
- Candidate metadata gains `source_class` and optional `source_authenticity` hints. A provider name is not a source class.

- [ ] **Step 1: Write RED tests for strategy order**

```python
from backend.app.source_strategy import plan_source_strategy


def test_receipt_strategy_never_starts_with_stock(receipt_intent, taste):
    strategy = plan_source_strategy(receipt_intent, "RECEIPT", taste)
    assert strategy.classes[0] == "EXACT_RECEIPT"
    assert strategy.classes[-1] == "GENERIC_STOCK"


def test_product_ui_prefers_exact_demo_before_related_editorial(product_intent, taste):
    strategy = plan_source_strategy(product_intent, "PRODUCT_UI", taste)
    assert strategy.classes.index("PRODUCT_UI_DEMO") < strategy.classes.index("CLOSE_SEMANTIC_EDITORIAL")
```

- [ ] **Step 2: Implement source strategy**

`query_families` must be explicit and inspectable, for example exact entity/claim, event/context, source-native social, and generic fallback. Generic fallback is generated but executed only after stronger classes do not yield enough eligible proposals.

- [ ] **Step 3: Normalize candidate source class metadata**

- Pexels/Pixabay/Coverr normalize to `GENERIC_STOCK`.
- YouTube adapter accepts optional discovery metadata `source_class` and defaults to `CLOSE_SEMANTIC_EDITORIAL`, never to `EXACT_*` merely because it is YouTube.
- Original/official/source-native classifications must come from explicit adapter/discovery evidence, not guessed from provider name.

- [ ] **Step 4: Run GREEN and commit**

Run: `pytest tests/unit/test_source_strategy.py tests/unit/test_online_assets.py tests/unit/test_youtube_source.py -q`
Expected: PASS.

Commit:

```bash
git add backend/app/source_strategy.py backend/app/online_assets.py backend/app/youtube_source.py tests/unit/test_source_strategy.py tests/unit/test_online_assets.py tests/unit/test_youtube_source.py
git commit -m "feat: add evidence-first source strategy"
```

---

### Task 3: Add multi-axis EditorialQuality scoring and hard gates

**Files:**
- Create: `backend/app/editorial_quality.py`
- Modify: `backend/app/proposals.py`
- Create: `tests/unit/test_editorial_quality.py`
- Modify: `tests/unit/test_taste_proposals.py`
- Modify: `tests/unit/test_proposals.py`

**Interfaces:**
- Produces `EditorialScore` and `score_editorial_candidate(candidate, *, intent, taste, recent_context=())`.
- Adds inspectable score components: `semantic_relevance`, `evidence_specificity`, `editorial_quality`, `source_authority_authenticity`, `style_fit`, `composition_usability`, `technical_quality`, `diversity_novelty`.
- Adds `eligible`, `rejection_reasons`, `recommended_presentation_mode`, `editorial_final_score`.
- `select_proposals()` accepts optional `evidence_intent` and `recent_context`; the legacy no-intent path remains compatible.

- [ ] **Step 1: Write RED tests for exact evidence vs clean generic stock**

```python
from backend.app.editorial_quality import score_editorial_candidate


def test_exact_evidence_beats_pristine_generic_stock(receipt_intent, taste):
    exact = score_editorial_candidate({
        "id":"exact", "semantic_score":0.84, "source_class":"EXACT_RECEIPT",
        "evidence_specificity":1.0, "source_authenticity":0.95,
        "editorial_quality":0.72, "composition_usability":0.80, "technical_quality":0.65,
        "source":"web", "motif_id":"article-receipt",
    }, intent=receipt_intent, taste=taste)
    stock = score_editorial_candidate({
        "id":"stock", "semantic_score":0.91, "source_class":"GENERIC_STOCK",
        "evidence_specificity":0.25, "source_authenticity":0.55,
        "editorial_quality":0.90, "composition_usability":0.95, "technical_quality":0.95,
        "source":"pexels", "motif_id":"person-laptop",
    }, intent=receipt_intent, taste=taste)
    assert exact.eligible is True
    assert exact.final_score > stock.final_score
```

- [ ] **Step 2: Write RED tests for hard quality floor and semantic guard**

```python
def test_low_editorial_quality_is_ineligible(entity_intent, taste):
    score = score_editorial_candidate({
        "id":"dead", "semantic_score":0.86, "source_class":"EXACT_ENTITY_EVENT",
        "evidence_specificity":0.8, "editorial_quality":0.25,
        "source_authenticity":0.8, "composition_usability":0.8, "technical_quality":0.8,
    }, intent=entity_intent, taste=taste)
    assert score.eligible is False
    assert "editorial_quality_below_floor" in score.rejection_reasons


def test_style_cannot_rescue_semantically_wrong_candidate(entity_intent, taste):
    score = score_editorial_candidate({
        "id":"pretty-wrong", "semantic_score":0.18, "source_class":"SOURCE_NATIVE_SOCIAL",
        "evidence_specificity":0.9, "editorial_quality":0.95, "style_fit":1.0,
        "source_authenticity":1.0, "composition_usability":1.0, "technical_quality":1.0,
    }, intent=entity_intent, taste=taste)
    assert score.eligible is False
    assert "semantic_relevance_below_floor" in score.rejection_reasons
```

- [ ] **Step 3: Implement scoring with fixed initial weights**

After eligibility gates, use the spec weights:

```python
WEIGHTS = {
    "semantic_relevance": 0.25,
    "evidence_specificity": 0.25,
    "editorial_quality": 0.15,
    "source_authority_authenticity": 0.10,
    "style_fit": 0.10,
    "composition_usability": 0.08,
    "technical_quality": 0.04,
    "diversity_novelty": 0.03,
}
```

Default semantic eligibility floor for editorial mode is `0.40`; exact-route specificity comes from `StyleDNA.minimum_evidence_specificity_by_route`; editorial floor comes from `StyleDNA.minimum_editorial_quality`. Keep those values explicit in the returned reasons/components.

`recommended_presentation_mode` is chosen from: `FULL_FRAME_CUTAWAY`, `SPEAKER_PLUS_EVIDENCE_TOP`, `SPEAKER_PLUS_EVIDENCE_SPLIT`, `PIP_EVIDENCE`, `DOCUMENT_CARD`, `SOCIAL_POST_CARD`, `ARCHIVE_FRAME`, `STILL_WITH_MOTION`.

- [ ] **Step 4: Integrate into proposal selection and meaningful A/B diversity**

When editorial context is supplied:

1. score every candidate;
2. remove ineligible rows from proposal slots but retain them in an inspectable `rejected_candidates` list;
3. proposal B must differ from A by source ID or motif ID where an alternative exists;
4. if zero pass: `review_state="NO_BROLL_QUALITY_FLOOR"`;
5. if one passes: `review_state="SINGLE_PROPOSAL_QUALITY_FLOOR"` so Task 4/online sourcing can escalate instead of silently accepting it.

- [ ] **Step 5: Run GREEN and commit**

Run: `pytest tests/unit/test_editorial_quality.py tests/unit/test_taste_proposals.py tests/unit/test_proposals.py -q`
Expected: PASS.

Commit:

```bash
git add backend/app/editorial_quality.py backend/app/proposals.py tests/unit/test_editorial_quality.py tests/unit/test_taste_proposals.py tests/unit/test_proposals.py
git commit -m "feat: gate B-roll by editorial quality"
```

---

### Task 4: Integrate editorial strategy into online sourcing with automatic escalation

**Files:**
- Modify: `backend/app/online_sourcing.py`
- Modify: `backend/app/online_sourcing_cli.py`
- Modify: `tests/unit/test_online_sourcing.py`
- Modify: `tests/unit/test_taste_online_sourcing.py`
- Modify: `tests/integration/test_evidence_coverage_pipeline.py`

**Interfaces:**
- `OnlineSourcingEngine.source_beat()` gains optional `evidence_intent` and `source_strategy` while retaining existing callers.
- Result persists `source_strategy`, `searched_source_classes`, `rejected_candidates`, and quality-floor state.
- Search escalation stops as soon as at least `minimum_proposals` eligible, meaningfully diverse proposals exist; stronger source classes are searched before stock.

- [ ] **Step 1: Write RED integration tests**

Add a fake exact-evidence source and fake stock source. Assert:

```python
result = await engine.source_beat(..., evidence_intent=receipt_intent, source_strategy=receipt_strategy)
assert result["proposals"]["proposal_A"]["source_class"] == "EXACT_RECEIPT"
assert result["searched_source_classes"][0] == "EXACT_RECEIPT"
assert result["proposals"]["proposal_B"]["id"] != result["proposals"]["proposal_A"]["id"]
```

Add a second test where the first class yields one strong candidate and the next class supplies B; assert generic stock is never queried if two strong non-stock candidates are already available.

Add a third test where all candidates fail editorial quality; assert `NO_BROLL_QUALITY_FLOOR`, no fabricated proposal, and no Resolve call.

- [ ] **Step 2: Refactor search into source-class rounds**

Keep current provider concurrency *inside* each source-class round. Do not serialize every provider/query pair. The engine must preserve its bounded `max_queries`, `max_results_per_query`, `max_preview_candidates`, and preview concurrency.

Sources may expose `supported_source_classes`; sources without it are treated as compatible with `CLOSE_SEMANTIC_EDITORIAL` plus any explicit candidate-level source class they return. This avoids breaking existing adapters.

- [ ] **Step 3: Run final-segment/localization flow unchanged for eligible A/B**

Do not regress `SceneLocator`, bounded-window acquisition, or Qwen final-segment verification. Editorial scoring consumes the final selected-window semantic score when present; thumbnail/coarse score is not allowed to masquerade as final semantic evidence.

- [ ] **Step 4: Persist benchmark counters**

Extend `online-sourcing-benchmark.json` with:

- `eligible_candidate_count`
- `rejected_candidate_count`
- `quality_floor_no_broll_count`
- `source_class_search_rounds`
- `generic_stock_selected_count`
- `distinct_proposal_source_count`

- [ ] **Step 5: Run GREEN and commit**

Run: `pytest tests/unit/test_online_sourcing.py tests/unit/test_taste_online_sourcing.py tests/integration/test_evidence_coverage_pipeline.py -q`
Expected: PASS.

Commit:

```bash
git add backend/app/online_sourcing.py backend/app/online_sourcing_cli.py tests/unit/test_online_sourcing.py tests/unit/test_taste_online_sourcing.py tests/integration/test_evidence_coverage_pipeline.py
git commit -m "feat: escalate sourcing until strong A/B exists"
```

---

### Task 5: Make coverage and review composition-aware and editorially inspectable

**Files:**
- Modify: `backend/app/coverage.py`
- Modify: `backend/app/director_engine.py`
- Modify: `backend/app/director_preview.py`
- Modify: `tests/unit/test_coverage.py`
- Modify: `tests/unit/test_taste_edit_plan.py`
- Modify: `tests/unit/test_taste_preview.py`
- Modify: `tests/integration/test_evidence_coverage_pipeline.py`

**Interfaces:**
- Coverage/Edit Plan persists `evidence_intent`, `source_strategy`, `presentation_mode`, score components, `rejection_reasons`, and explicit quality-floor result.
- A slot is allowed to keep the speaker visible; B-roll no longer semantically implies full-frame replacement.

- [ ] **Step 1: Write RED tests for presentation mode**

For a receipt/document candidate under Factanza-heavy StyleDNA, assert `DOCUMENT_CARD` or `SPEAKER_PLUS_EVIDENCE_TOP`; for source-native vertical social under Olimpia-heavy StyleDNA, assert `FULL_FRAME_CUTAWAY` is eligible/preferred.

- [ ] **Step 2: Extend CoverageSlot persistence without breaking timing**

Do not change the existing safe timing math. Add optional metadata fields to the serialized slot rather than forcing callers to construct new required arguments.

- [ ] **Step 3: Extend Edit Plan validation/persistence**

Every editorial-mode coverage slot must retain:

- full local transcript/context, not truncated text;
- visual route and route reason;
- serialized EvidenceIntent;
- source strategy order and classes actually searched;
- proposal A/B with all eight score axes;
- source URL/creator/range/rights;
- `presentation_mode`;
- rejected candidate IDs/reasons;
- `review_state` including `NO_BROLL_QUALITY_FLOOR`.

Keep taste snapshot/hash reproducibility and `resolve_calls=0`.

- [ ] **Step 4: Upgrade `review.html`**

The review surface must show a timeline/editorial row per semantic chunk/coverage decision and side-by-side A/B cards. For every proposal display: final Qwen/semantic score, evidence specificity, editorial quality, source authority, style fit, composition usability, technical quality, diversity, final score, source class, presentation mode, source time, creator, rights. Show rejected reasons below the slot without pretending they are selectable.

Explicit `NO_BROLL` and `NO_BROLL_QUALITY_FLOOR` rows remain visible with rationale; do not hide chunks just because no proposal exists.

- [ ] **Step 5: Run GREEN and commit**

Run: `pytest tests/unit/test_coverage.py tests/unit/test_taste_edit_plan.py tests/unit/test_taste_preview.py tests/integration/test_evidence_coverage_pipeline.py -q`
Expected: PASS.

Commit:

```bash
git add backend/app/coverage.py backend/app/director_engine.py backend/app/director_preview.py tests/unit/test_coverage.py tests/unit/test_taste_edit_plan.py tests/unit/test_taste_preview.py tests/integration/test_evidence_coverage_pipeline.py
git commit -m "feat: persist editorial quality in coverage review"
```

---

### Task 6: Add offline reference StyleDNA fingerprint analyzer

**Files:**
- Create: `backend/app/style_fingerprint.py`
- Create: `backend/app/style_fingerprint_cli.py`
- Create: `tests/unit/test_style_fingerprint.py`

**Interfaces:**
- Produces `StyleFingerprint` compatible with `ReferenceStyleProfile`.
- Uses injected command runner / media probe so unit tests never require the user's private reference files.
- Real local smoke may read the two supplied reference media only from an approved local RAMBLA working/data root; reference bytes are never committed.

- [ ] **Step 1: Write RED tests against synthetic cut/classification fixtures**

The test fixture represents known cut intervals and classified visual states. Assert exact metrics:

```python
fingerprint = build_style_fingerprint(
    exemplar_id="factanza-fixture",
    duration_seconds=20.0,
    intervals=[
        VisualInterval(0.0, 4.0, "TALKING_HEAD", "FULL_FRAME"),
        VisualInterval(4.0, 7.5, "RECEIPT", "SPEAKER_PLUS_EVIDENCE_TOP"),
        VisualInterval(7.5, 10.0, "TALKING_HEAD", "FULL_FRAME"),
        VisualInterval(10.0, 14.0, "ARCHIVAL", "FULL_FRAME_CUTAWAY"),
        VisualInterval(14.0, 20.0, "TALKING_HEAD", "FULL_FRAME"),
    ],
)
assert fingerprint.insert_count == 2
assert fingerprint.speaker_return_count >= 2
assert fingerprint.route_mix["RECEIPT"] > 0
assert fingerprint.presentation_mix["SPEAKER_PLUS_EVIDENCE_TOP"] > 0
```

- [ ] **Step 2: Implement pure aggregation first**

`style_fingerprint.py` owns pure dataclasses/statistics: duration, visual-change count, cuts/minute, mean/median insert duration, talking-head persistence, coverage density, return-to-speaker intervals, route mix, presentation mix, still/video ratio, hook/body/end density, source-native overlay tolerance metadata, and classification confidence summary.

- [ ] **Step 3: Add FFmpeg/ffprobe extraction adapter behind injected runner**

CLI flow:

1. ffprobe duration/fps/dimensions;
2. FFmpeg scene-cut timestamps / representative frames into output directory;
3. optional injected/local visual classifier returns route + presentation classifications;
4. pure aggregator writes `style-fingerprint.json` and representative-frame manifest.

No model auto-download, no global installation, no browser automation.

- [ ] **Step 4: Preserve independent exemplar identities**

The real local smoke must produce two separate files/profile IDs:

- `factanza_evidence_editorial`
- `olimpia_social_kinetic`

Do not average them during analysis. A later `StyleDNA.active_style_mix` combines them by explicit weights.

- [ ] **Step 5: Run GREEN and commit**

Run: `pytest tests/unit/test_style_fingerprint.py -q`
Expected: PASS.

Commit:

```bash
git add backend/app/style_fingerprint.py backend/app/style_fingerprint_cli.py tests/unit/test_style_fingerprint.py
git commit -m "feat: analyze reference reels into StyleDNA fingerprints"
```

---

### Task 7: Add editorial benchmark and end-to-end acceptance gate

**Files:**
- Create: `backend/app/editorial_benchmark.py`
- Create: `tests/unit/test_editorial_benchmark.py`
- Create: `tests/integration/test_editorial_intelligence_pipeline.py`
- Modify: `.github/workflows/online-sourcing-tests.yml` only if branch trigger was not completed in Task 1.

**Interfaces:**
- Compares current semantic-only proposal ordering with editorial-intelligence ordering on the same deterministic candidate fixture.
- Produces inspectable metrics, not a single opaque quality number.

- [ ] **Step 1: Write RED benchmark tests**

Fixture must contain at least:

1. exact evidence with slightly lower cosine but strong specificity/authenticity;
2. pristine generic stock with higher cosine;
3. visually dead/repetitive semantically matching footage;
4. a distinct valid B alternative.

Assert new path selects exact evidence A, distinct B, rejects dead filler, and baseline remains measurable rather than overwritten.

- [ ] **Step 2: Implement benchmark metrics**

Persist:

- `slot_count`
- `slots_with_two_eligible_proposals`
- `quality_floor_no_broll_rate`
- `mean_evidence_specificity_selected`
- `mean_editorial_quality_selected`
- `generic_stock_selection_rate`
- `duplicate_source_or_motif_rate`
- `exact_or_source_native_selection_rate`
- baseline vs editorial candidate IDs per slot
- zero-Resolve invariant

- [ ] **Step 3: Add deterministic end-to-end integration test**

Test the path:

`semantic chunk -> EvidenceIntent -> SourceStrategy -> fake discovery -> Qwen-like semantic scores -> editorial gates/ranking -> A/B -> Edit Plan -> review.html`

Assertions: exact evidence outranks cleaner generic stock; A/B are meaningfully distinct; all eight score axes visible in plan/review; low-quality-only slot becomes `NO_BROLL_QUALITY_FLOOR`; no full source acquisition is required by the fake long-source path; `resolve_calls == 0`.

- [ ] **Step 4: Run full verification**

Run:

```bash
pytest -q
python -m compileall backend
```

Expected: all tests PASS; compileall PASS.

Then run the real local non-mutating smoke using the existing long transcript plus the already validated Qwen3-VL-Embedding-2B runtime. Use the two reference fingerprints only as local StyleDNA inputs. Keep YouTube/Shorts-first for the first comparison unless the EvidenceIntent requires a source class that the current providers cannot satisfy; record unsupported source classes instead of silently pretending YouTube is the whole internet.

Real smoke acceptance:

- full/substantial transcript semantic chunks, not one beat;
- every B-roll slot has >=2 eligible A/B or explicit quality-floor/no-B-roll state;
- final Qwen verification on actual selected clip frames;
- no whole-video download;
- no single download >5 GiB;
- no Resolve/ComfyUI/global changes;
- exact `review.html`, edit-plan and benchmark paths reported;
- compare old semantic-only vs editorial-intelligence choices in the same report.

- [ ] **Step 5: Commit, push, and open draft stacked PR**

Commit:

```bash
git add backend/app/editorial_benchmark.py tests/unit/test_editorial_benchmark.py tests/integration/test_editorial_intelligence_pipeline.py .github/workflows/online-sourcing-tests.yml
git commit -m "test: benchmark editorial intelligence selection"
```

Push `feat/editorial-intelligence-style-dna-v1` and open a **draft** PR with base `feat/resolve-panel-safe-v1`. Include tests, real-smoke artifact paths, baseline-vs-editorial metrics, known provider/source-class gaps, and explicit statement `Resolve calls: 0`. Do not merge.

---

## Completion Gate

This plan is complete only when:

- StyleDNA stores two independent exemplar fingerprints and a deterministic active mix;
- EvidenceIntent and source-class strategy are persisted before search;
- editorial candidates expose all eight score components and rejection reasons;
- generic stock cannot beat exact evidence simply by being cleaner or having a slightly higher semantic score;
- taste/style cannot rescue a semantically wrong clip;
- A/B are meaningfully distinct or the system escalates search;
- weak-only candidate pools produce explicit `NO_BROLL_QUALITY_FLOOR`;
- presentation mode supports speaker+evidence/document/social layouts without requiring portrait-only sources;
- `review.html` makes intent, source class, A/B, scores, rejection reasons, rights and presentation mode inspectable;
- the fingerprint analyzer produces separate Factanza-like and Olimpia-like profiles from local references without committing source media;
- deterministic benchmark demonstrates improvement over semantic-only ranking on evidence specificity/editorial quality without reducing factual relevance;
- full `pytest -q` and `python -m compileall backend` pass;
- a real local non-mutating smoke is produced with bounded acquisition and `resolve_calls=0`;
- implementation is pushed on `feat/editorial-intelligence-style-dna-v1` and a draft stacked PR targets `feat/resolve-panel-safe-v1`;
- no merge occurs without explicit user approval.
