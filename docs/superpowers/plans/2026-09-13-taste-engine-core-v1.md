# Taste Engine Core V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first working Taste Engine slice: versioned client-scoped taste profiles, deterministic visual routing, explicit guardrails, bounded taste scoring, and reproducible Taste metadata in the existing online sourcing/Edit Plan flow.

**Architecture:** Keep Taste as a policy layer around the existing Director/Qwen/coverage stack. Add focused `taste_profile.py` and `visual_routing.py` modules; pass an immutable `TasteContext` into online sourcing and proposal selection; preserve semantic relevance, provenance, and crop usability as higher-priority constraints. No fingerprint extraction, subscription import, source batching, or automatic learning in this tranche.

**Tech Stack:** Python 3.12, dataclasses, stdlib JSON/hashlib/pathlib, existing FastAPI backend, existing Qwen ranker, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-12-taste-engine-broll-finder-adaptation-design.md`

## Global Constraints

- Explicit user guardrails always override measured/imported taste.
- Taste never overrides factual/evidence relevance, rights/provenance acceptability, or crop/technical usability.
- Taste profiles are client-scoped and versioned; no cross-client reuse.
- Profile changes are proposed/approved explicitly; no silent permanent learning.
- The frozen Edit Plan stores a reproducible taste snapshot/hash.
- Existing A/B proposal behavior remains available.
- Resolve mutation remains frozen; this plan must make zero Resolve calls.
- B-Roll-Finder is MIT; any copied/substantially adapted implementation must retain attribution.

---

### Task 1: Versioned TasteProfile, canonical snapshot, and guardrail enforcement

**Files:**
- Create: `backend/app/taste_profile.py`
- Create: `tests/unit/test_taste_profile.py`
- Modify: `.github/workflows/online-sourcing-tests.yml`

**Interfaces:**
- Produces: `TasteProfile`, `TasteContext`, `canonical_taste_hash(profile) -> str`, `build_taste_context(profile, *, topic=None, genre=None) -> TasteContext`, `apply_guardrail_override(profile, override) -> TasteProfile`.
- Consumes: no model/runtime dependency; stdlib only.

- [ ] **Step 1: Write the failing tests**

```python
from dataclasses import replace

import pytest

from backend.app.taste_profile import (
    TasteProfile,
    apply_guardrail_override,
    build_taste_context,
    canonical_taste_hash,
)


def _profile() -> TasteProfile:
    return TasteProfile(
        client_id="client-a",
        version=3,
        approved=True,
        route_weights={"RECEIPT": 0.7, "ENTITY": 0.6, "STOCK": 0.2},
        guardrails={"memes": False, "audio_policy": "strip"},
        trusted_sources={"tech": ("youtube:OpenAI",)},
        default_proposal_count=2,
    )


def test_taste_hash_is_stable_and_client_scoped():
    profile = _profile()
    assert canonical_taste_hash(profile) == canonical_taste_hash(replace(profile))
    other = replace(profile, client_id="client-b")
    assert canonical_taste_hash(profile) != canonical_taste_hash(other)


def test_guardrail_override_creates_new_unapproved_version_without_mutating_input():
    profile = _profile()
    updated = apply_guardrail_override(profile, {"memes": True})
    assert profile.guardrails["memes"] is False
    assert updated.version == 4
    assert updated.approved is False
    assert updated.guardrails["memes"] is True


def test_context_exposes_only_client_profile_and_topic_sources():
    ctx = build_taste_context(_profile(), topic="tech", genre="explainer")
    assert ctx.client_id == "client-a"
    assert ctx.profile_version == 3
    assert ctx.trusted_sources == ("youtube:OpenAI",)
    assert ctx.guardrails["memes"] is False


def test_invalid_profile_rejects_bad_route_weight():
    with pytest.raises(ValueError, match="route weight"):
        TasteProfile(client_id="client-a", version=1, approved=True, route_weights={"STOCK": 1.5})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_taste_profile.py -q`
Expected: FAIL during collection with `ModuleNotFoundError: backend.app.taste_profile`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/taste_profile.py
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Mapping

ROUTES = frozenset({"RECEIPT", "ENTITY", "PRODUCT_UI", "ARCHIVAL", "CONCEPT", "CULTURAL", "STOCK"})


def _freeze_map(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


@dataclass(frozen=True)
class TasteProfile:
    client_id: str
    version: int
    approved: bool
    route_weights: Mapping[str, float] = field(default_factory=dict)
    guardrails: Mapping[str, Any] = field(default_factory=dict)
    trusted_sources: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    default_proposal_count: int = 2
    pacing: Mapping[str, float] = field(default_factory=dict)
    provenance: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.client_id or self.version < 1:
            raise ValueError("client identity and positive profile version are required")
        if self.default_proposal_count < 1:
            raise ValueError("default proposal count must be positive")
        bad = [name for name, value in self.route_weights.items() if name not in ROUTES or not 0.0 <= float(value) <= 1.0]
        if bad:
            raise ValueError("route weight must use a supported route and lie between 0 and 1")
        object.__setattr__(self, "route_weights", _freeze_map({k: float(v) for k, v in self.route_weights.items()}))
        object.__setattr__(self, "guardrails", _freeze_map(self.guardrails))
        object.__setattr__(self, "trusted_sources", _freeze_map({k: tuple(v) for k, v in self.trusted_sources.items()}))
        object.__setattr__(self, "pacing", _freeze_map({k: float(v) for k, v in self.pacing.items()}))


@dataclass(frozen=True)
class TasteContext:
    client_id: str
    profile_version: int
    profile_hash: str
    route_weights: Mapping[str, float]
    guardrails: Mapping[str, Any]
    trusted_sources: tuple[str, ...]
    default_proposal_count: int
    topic: str | None = None
    genre: str | None = None


def _profile_payload(profile: TasteProfile) -> dict[str, Any]:
    return {
        "client_id": profile.client_id,
        "version": profile.version,
        "approved": profile.approved,
        "route_weights": dict(sorted(profile.route_weights.items())),
        "guardrails": dict(sorted(profile.guardrails.items())),
        "trusted_sources": {k: list(profile.trusted_sources[k]) for k in sorted(profile.trusted_sources)},
        "default_proposal_count": profile.default_proposal_count,
        "pacing": dict(sorted(profile.pacing.items())),
        "provenance": list(profile.provenance),
    }


def canonical_taste_hash(profile: TasteProfile) -> str:
    raw = json.dumps(_profile_payload(profile), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_taste_context(profile: TasteProfile, *, topic: str | None = None, genre: str | None = None) -> TasteContext:
    return TasteContext(
        client_id=profile.client_id,
        profile_version=profile.version,
        profile_hash=canonical_taste_hash(profile),
        route_weights=profile.route_weights,
        guardrails=profile.guardrails,
        trusted_sources=tuple(profile.trusted_sources.get(topic or "", ())),
        default_proposal_count=profile.default_proposal_count,
        topic=topic,
        genre=genre,
    )


def apply_guardrail_override(profile: TasteProfile, override: Mapping[str, Any]) -> TasteProfile:
    merged = dict(profile.guardrails)
    merged.update(dict(override))
    return replace(profile, version=profile.version + 1, approved=False, guardrails=merged)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_taste_profile.py -q`
Expected: PASS.

- [ ] **Step 5: Extend CI branch allowlist and commit**

Add `feat/taste-engine-core-v1` to `.github/workflows/online-sourcing-tests.yml`, then commit:

```bash
git add backend/app/taste_profile.py tests/unit/test_taste_profile.py .github/workflows/online-sourcing-tests.yml
git commit -m "feat: add versioned TasteProfile core"
```

---

### Task 2: Deterministic VisualRoute planner before sourcing

**Files:**
- Create: `backend/app/visual_routing.py`
- Create: `tests/unit/test_visual_routing.py`

**Interfaces:**
- Consumes: `TasteContext` from Task 1 and one CoverageSlot-like mapping with transcript/context.
- Produces: `VisualRouteDecision(route: str, reason: str, confidence: float, search_hint: str)` and `plan_visual_route(slot, context, taste) -> VisualRouteDecision`.

- [ ] **Step 1: Write the failing tests**

```python
from backend.app.taste_profile import TasteProfile, build_taste_context
from backend.app.visual_routing import plan_visual_route


def _taste(**guardrails):
    return build_taste_context(TasteProfile(
        client_id="client-a", version=1, approved=True,
        route_weights={"RECEIPT": 0.8, "ENTITY": 0.7, "STOCK": 0.1},
        guardrails=guardrails,
    ))


def test_direct_quote_routes_to_receipt_before_generic_stock():
    decision = plan_visual_route(
        {"transcript": 'Ha scritto: "questa funzione cambia tutto"', "intent": "quote from a post"},
        "Contesto: si parla di un post pubblico di una startup.",
        _taste(),
    )
    assert decision.route == "RECEIPT"
    assert decision.confidence >= 0.8


def test_named_product_ui_routes_to_product_ui():
    decision = plan_visual_route(
        {"transcript": "Poi apro Notion e creo il database", "intent": "show workflow"},
        "Tutorial software",
        _taste(),
    )
    assert decision.route == "PRODUCT_UI"


def test_explicit_meme_ban_prevents_cultural_route():
    decision = plan_visual_route(
        {"transcript": "qui ci starebbe una reaction meme", "intent": "reaction punchline"},
        "Comedic beat",
        _taste(memes=False),
    )
    assert decision.route != "CULTURAL"
    assert "guardrail" in decision.reason.lower()
```

- [ ] **Step 2: Run RED**

Run: `pytest tests/unit/test_visual_routing.py -q`
Expected: FAIL with missing module.

- [ ] **Step 3: Implement the deterministic fallback router**

```python
# backend/app/visual_routing.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from .taste_profile import TasteContext


@dataclass(frozen=True)
class VisualRouteDecision:
    route: str
    reason: str
    confidence: float
    search_hint: str


def _text(slot: Mapping[str, Any], context: str) -> str:
    return " ".join([str(slot.get("transcript", "")), str(slot.get("intent", "")), context]).casefold()


def plan_visual_route(slot: Mapping[str, Any], context: str, taste: TasteContext) -> VisualRouteDecision:
    text = _text(slot, context)
    memes_allowed = bool(taste.guardrails.get("memes", True))
    if any(token in text for token in ("ha scritto", "tweet", "post", "articolo", "headline", "prezzo", "statistica", "studio", "ricerca mostra")) or '"' in text:
        return VisualRouteDecision("RECEIPT", "Concrete claim/quote should use the original receipt.", 0.9, "find authentic post/article/document")
    if any(token in text for token in ("app ", "software", "interfaccia", "ui", "dashboard", "apro ", "clicco ")):
        return VisualRouteDecision("PRODUCT_UI", "The beat describes a product/interface action.", 0.85, "find current official UI/demo")
    if any(token in text for token in ("nel 19", "nel 20", "storico", "archivio", "anni fa")):
        return VisualRouteDecision("ARCHIVAL", "Historical context benefits from archival evidence.", 0.8, "find authoritative archival footage/image")
    if any(token in text for token in ("meme", "reaction", "reazione", "punchline")):
        if memes_allowed:
            return VisualRouteDecision("CULTURAL", "Reaction beat and memes are allowed by the active profile.", 0.75, "find culturally matching reaction")
        return VisualRouteDecision("CONCEPT", "Cultural route blocked by explicit guardrail; fall back to concept/talking head.", 0.7, "use concept emphasis or no visual")
    proper_names = re.findall(r"\b[A-ZÀ-Ý][\wÀ-ÿ-]{2,}\b", " ".join([str(slot.get("transcript", "")), str(slot.get("intent", ""))]))
    if proper_names:
        return VisualRouteDecision("ENTITY", "Named entity detected; prefer exact subject/context footage.", 0.7, "find named entity in the described context")
    return VisualRouteDecision("CONCEPT", "No concrete artifact/entity detected; prefer explanatory concept over generic stock.", 0.55, "illustrate the underlying idea")
```

- [ ] **Step 4: Run GREEN and commit**

Run: `pytest tests/unit/test_visual_routing.py tests/unit/test_taste_profile.py -q`
Expected: PASS.

```bash
git add backend/app/visual_routing.py tests/unit/test_visual_routing.py
git commit -m "feat: route coverage slots before sourcing"
```

---

### Task 3: Taste-aware proposal scoring without letting taste beat relevance

**Files:**
- Modify: `backend/app/proposals.py`
- Create: `tests/unit/test_taste_proposals.py`

**Interfaces:**
- Consumes: existing ranked candidate rows plus optional `TasteContext` and `visual_route`.
- Changes: `select_proposals(candidates, *, minimum=2, target_aspect=9/16, taste=None, visual_route=None)`.
- Produces per proposal: `taste_score`, `taste_components`, and `final_score`, while preserving `semantic_score`, `qwen_score`, `crop_score`.

- [ ] **Step 1: Write the failing tests**

```python
from backend.app.proposals import select_proposals
from backend.app.taste_profile import TasteProfile, build_taste_context


def _taste():
    return build_taste_context(TasteProfile(
        client_id="client-a", version=1, approved=True,
        route_weights={"RECEIPT": 0.9, "STOCK": 0.1},
        guardrails={}, trusted_sources={"tech": ("youtube:OpenAI",)},
    ), topic="tech")


def test_taste_breaks_close_semantic_tie_but_cannot_overturn_large_relevance_gap():
    rows = [
        {"id":"stock","client_id":"client-a","score":0.90,"embedding_score":0.90,"width":1920,"height":1080,"source":"pexels","provider_id":"1","route":"STOCK"},
        {"id":"receipt","client_id":"client-a","score":0.88,"embedding_score":0.88,"width":1920,"height":1080,"source":"youtube","provider_id":"2","route":"RECEIPT","source_registry_key":"youtube:OpenAI"},
    ]
    close = select_proposals(rows, taste=_taste(), visual_route="RECEIPT")
    assert close["proposal_A"]["id"] == "receipt"

    rows[0]["score"] = rows[0]["embedding_score"] = 0.99
    rows[1]["score"] = rows[1]["embedding_score"] = 0.55
    far = select_proposals(rows, taste=_taste(), visual_route="RECEIPT")
    assert far["proposal_A"]["id"] == "stock"


def test_taste_components_are_exposed_not_opaque():
    result = select_proposals([
        {"id":"a","client_id":"client-a","score":0.8,"embedding_score":0.8,"width":1080,"height":1920,"source":"youtube","provider_id":"1","route":"RECEIPT","source_registry_key":"youtube:OpenAI"}
    ], taste=_taste(), visual_route="RECEIPT")
    proposal = result["proposal_A"]
    assert 0 <= proposal["taste_score"] <= 1
    assert set(proposal["taste_components"]) >= {"route_match", "trusted_source"}
```

- [ ] **Step 2: Run RED**

Run: `pytest tests/unit/test_taste_proposals.py -q`
Expected: FAIL because `select_proposals` does not accept `taste`/`visual_route` and proposals lack taste fields.

- [ ] **Step 3: Implement bounded taste scoring**

Add to `proposals.py`:

```python
from .taste_profile import TasteContext


def _taste_score(row: dict[str, Any], taste: TasteContext | None, visual_route: str | None) -> tuple[float, dict[str, float]]:
    if taste is None:
        return 0.5, {"route_match": 0.5, "trusted_source": 0.5}
    row_route = str(row.get("route") or "")
    route_match = 1.0 if visual_route and row_route == visual_route else float(taste.route_weights.get(row_route, 0.5))
    trusted_source = 1.0 if str(row.get("source_registry_key") or "") in taste.trusted_sources else 0.5
    score = max(0.0, min(1.0, 0.7 * route_match + 0.3 * trusted_source))
    return round(score, 4), {"route_match": round(route_match, 4), "trusted_source": round(trusted_source, 4)}
```

Then change proposal scoring to:

```python
# semantic relevance remains dominant; crop/taste can reorder close candidates only.
result["taste_score"], result["taste_components"] = _taste_score(result, taste, visual_route)
result["final_score"] = round(
    0.72 * semantic_score + 0.18 * assessment.score + 0.10 * result["taste_score"], 4
)
```

Add a relevance-gap guard after sorting: if the highest-semantic usable candidate exceeds the taste-favored first candidate by more than `0.20`, force the highest-semantic candidate back to proposal A. This implements the spec rule that taste cannot make a clearly less relevant asset win.

- [ ] **Step 4: Run GREEN and regression tests**

Run:

```bash
pytest tests/unit/test_taste_proposals.py tests/unit/test_proposals.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/proposals.py tests/unit/test_taste_proposals.py
git commit -m "feat: add bounded taste scoring to proposals"
```

---

### Task 4: Thread TasteContext + VisualRoute through online sourcing

**Files:**
- Modify: `backend/app/online_sourcing.py`
- Create: `tests/unit/test_taste_online_sourcing.py`

**Interfaces:**
- Changes: `OnlineSourcingEngine.source_beat(..., taste: TasteContext | None = None, visual_route: str | None = None)`.
- Behavior: provider contracts remain unchanged; Taste affects only proposal selection/minimum count and persisted metadata in the sourcing result.

- [ ] **Step 1: Write the failing async test**

Use small fake source/cache/ranker objects, then assert:

```python
result = await engine.source_beat(
    beat_id="beat-1", client_id="client-a", queries=["original post about launch"],
    min_duration=0, max_duration=60,
    taste=taste_context, visual_route="RECEIPT",
)
assert result["visual_route"] == "RECEIPT"
assert result["taste_profile_version"] == taste_context.profile_version
assert result["taste_profile_hash"] == taste_context.profile_hash
assert result["proposals"]["minimum_proposals"] == taste_context.default_proposal_count
assert "taste_score" in result["proposals"]["proposal_A"]
```

- [ ] **Step 2: Run RED**

Run: `pytest tests/unit/test_taste_online_sourcing.py -q`
Expected: FAIL because `source_beat` lacks Taste parameters.

- [ ] **Step 3: Implement minimal threading**

Update signature and selection call:

```python
async def source_beat(..., taste: TasteContext | None = None, visual_route: str | None = None) -> dict[str, Any]:
    ...
    minimum = taste.default_proposal_count if taste else 2
    proposals = select_proposals(ranked, minimum=minimum, taste=taste, visual_route=visual_route)
```

Return:

```python
"visual_route": visual_route,
"taste_profile_version": taste.profile_version if taste else None,
"taste_profile_hash": taste.profile_hash if taste else None,
```

Ensure `_empty()` accepts the same optional metadata and returns it consistently.

- [ ] **Step 4: Run GREEN + sourcing regressions**

Run:

```bash
pytest tests/unit/test_taste_online_sourcing.py tests/unit/test_online_sourcing.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/online_sourcing.py tests/unit/test_taste_online_sourcing.py
git commit -m "feat: thread TasteContext through online sourcing"
```

---

### Task 5: Persist visual route and taste snapshot in the Edit Plan and review output

**Files:**
- Modify: `backend/app/director_engine.py`
- Modify: `backend/app/director_preview.py`
- Create: `tests/unit/test_taste_edit_plan.py`
- Modify: `tests/unit/test_director_preview.py`

**Interfaces:**
- Changes: `build_edit_plan(..., taste_context: TasteContext | None = None, route_by_slot: dict[str, VisualRouteDecision | dict[str, Any]] | None = None)`.
- Produces top-level `taste_snapshot` and per-coverage-slot `visual_route`, `route_reason`, `taste_profile_version`, `taste_profile_hash`, `applicable_guardrails`.

- [ ] **Step 1: Write failing plan tests**

```python
plan = build_edit_plan(
    transcript, outline, [], client_id="client-a", source_frames=240,
    taste_context=taste,
    route_by_slot={"beat-1:coverage:1": {"route":"RECEIPT","reason":"quote","confidence":0.9}},
)
assert plan["taste_snapshot"] == {
    "client_id":"client-a",
    "profile_version": taste.profile_version,
    "profile_hash": taste.profile_hash,
}
slot = plan["coverage_slots"][0]
assert slot["visual_route"] == "RECEIPT"
assert slot["route_reason"] == "quote"
assert slot["taste_profile_hash"] == taste.profile_hash
```

Also test client isolation: passing a TasteContext for `client-b` into `build_edit_plan(... client_id="client-a")` raises `ValueError("taste context violates client isolation")`.

- [ ] **Step 2: Run RED**

Run: `pytest tests/unit/test_taste_edit_plan.py -q`
Expected: FAIL because `build_edit_plan` lacks Taste arguments.

- [ ] **Step 3: Implement plan persistence and validation**

Add imports from `taste_profile` and `visual_routing`; validate client identity; enrich coverage rows by slot ID; add top-level snapshot. Extend `validate_edit_plan()` so every slot with a taste hash must match the top-level snapshot hash/version, and reject mismatches.

- [ ] **Step 4: Update review HTML**

In `director_preview.py`, add compact metadata per slot:

```text
Route: RECEIPT · Taste v3 · reason: quote
A: semantic 0.88 · crop 0.91 · taste 0.95 · final 0.89
```

Do not hide existing Qwen/provider/provenance details.

- [ ] **Step 5: Run GREEN + regression suite**

Run:

```bash
pytest tests/unit/test_taste_edit_plan.py tests/unit/test_director_preview.py tests/unit/test_director_engine.py -q
python -m compileall backend
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/director_engine.py backend/app/director_preview.py tests/unit/test_taste_edit_plan.py tests/unit/test_director_preview.py
git commit -m "feat: persist Taste routing in Edit Plan review"
```

---

### Task 6: Full T1 verification and stacked draft PR

**Files:**
- No new production files expected.
- Update: Issue #3 handoff.

**Interfaces:**
- Verifies all Tasks 1–5 as one backend slice.

- [ ] **Step 1: Run full repository tests**

Run:

```bash
pytest -q
python -m compileall backend
```

Expected: both GREEN.

- [ ] **Step 2: Verify no Resolve coupling**

Inspect T1 diff and assert no new imports from `resolve_live`, `resolve_apply`, bridge/MCP modules, and no live network calls in `taste_profile.py` or `visual_routing.py`.

- [ ] **Step 3: Verify score invariants**

Run the dedicated relevance-gap test from Task 3 and confirm a clearly inferior semantic candidate cannot win solely because of taste.

- [ ] **Step 4: Open a draft PR**

Base the PR on the latest safe backend/panel branch this implementation was created from. Keep it draft and unmerged. State clearly that fingerprint extraction is T2 and trusted-source import/batching/verification is T3.

- [ ] **Step 5: Post HANDOFF to Issue #3**

Include branch, SHA, test run IDs, TasteProfile/hash, route planner coverage, score invariant, zero Resolve calls, and next planned tranche T2.
