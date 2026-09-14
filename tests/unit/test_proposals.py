from __future__ import annotations

from backend.app.proposals import select_proposals


def _row(
    asset_id: str,
    *,
    score: float,
    source: str,
    provider_id: str,
    width: int,
    height: int,
    preview_sha256: str,
) -> dict:
    return {
        "id": asset_id,
        "score": score,
        "embedding_score": score,
        "source": source,
        "provider_id": provider_id,
        "width": width,
        "height": height,
        "preview_sha256": preview_sha256,
    }


def test_two_distinct_proposals_are_retained() -> None:
    rows = [
        _row("youtube:1", score=.91, source="youtube", provider_id="1", width=1920, height=1080, preview_sha256="a"),
        _row("pexels:2", score=.84, source="pexels", provider_id="2", width=1080, height=1920, preview_sha256="b"),
    ]

    result = select_proposals(rows)

    assert result["proposal_A"]["id"] in {"youtube:1", "pexels:2"}
    assert result["proposal_B"] is not None
    assert result["proposal_B"]["id"] != result["proposal_A"]["id"]
    assert result["review_state"] == "READY"
    assert 0 <= result["proposal_A"]["crop_score"] <= 1
    assert len(result["proposal_A"]["crop_box"]) == 4


def test_crop_score_can_demote_semantically_close_landscape_candidate() -> None:
    rows = [
        _row("landscape", score=.90, source="youtube", provider_id="1", width=1920, height=1080, preview_sha256="a"),
        _row("portrait", score=.86, source="pexels", provider_id="2", width=1080, height=1920, preview_sha256="b"),
    ]

    result = select_proposals(rows)

    assert result["proposal_A"]["id"] == "portrait"
    assert result["proposal_A"]["final_score"] > result["proposal_B"]["final_score"]


def test_duplicate_preview_is_not_used_as_second_proposal() -> None:
    rows = [
        _row("one", score=.95, source="youtube", provider_id="1", width=1080, height=1920, preview_sha256="same"),
        _row("duplicate", score=.94, source="youtube", provider_id="2", width=1080, height=1920, preview_sha256="same"),
        _row("different", score=.80, source="pexels", provider_id="3", width=1080, height=1920, preview_sha256="different"),
    ]

    result = select_proposals(rows)

    assert result["proposal_A"]["id"] == "one"
    assert result["proposal_B"]["id"] == "different"


def test_single_candidate_is_explicitly_marked() -> None:
    result = select_proposals([
        _row("one", score=.8, source="pexels", provider_id="1", width=1080, height=1920, preview_sha256="a")
    ])

    assert result["proposal_B"] is None
    assert result["review_state"] == "SINGLE_PROPOSAL"


def test_empty_candidates_report_no_visual_found() -> None:
    result = select_proposals([])

    assert result["proposal_A"] is None
    assert result["proposal_B"] is None
    assert result["review_state"] == "NO_VISUAL_FOUND"


def test_editorial_mode_rejects_weak_filler_and_selects_distinct_ab() -> None:
    from backend.app.evidence_intent import plan_evidence_intent
    from backend.app.taste_profile import TasteProfile, build_taste_context

    taste = build_taste_context(TasteProfile(client_id="c", version=1, approved=True))
    intent = plan_evidence_intent({"transcript": 'Ha scritto "non venderemo i dati"', "intent": "show claim"}, "official post", "RECEIPT", taste)
    rows = [
        {**_row("stock", score=.92, source="pexels", provider_id="stock", width=1080, height=1920, preview_sha256="stock"), "source_class": "GENERIC_STOCK", "evidence_specificity": .25, "editorial_quality": .95},
        {**_row("exact", score=.83, source="web", provider_id="exact", width=1920, height=1080, preview_sha256="exact"), "source_class": "EXACT_RECEIPT", "evidence_specificity": 1.0, "editorial_quality": .82, "motif_id": "receipt"},
        {**_row("native", score=.79, source="youtube", provider_id="native", width=1080, height=1920, preview_sha256="native"), "source_class": "SOURCE_NATIVE_SOCIAL", "evidence_specificity": .8, "editorial_quality": .76, "motif_id": "interview"},
    ]
    result = select_proposals(rows, taste=taste, evidence_intent=intent)
    assert result["proposal_A"]["id"] == "exact"
    assert result["proposal_B"]["id"] == "native"
    assert result["review_state"] == "READY"
    assert any(row["id"] == "stock" for row in result["rejected_candidates"])
    assert result["proposal_A"]["editorial_quality"] == .82


def test_editorial_mode_reports_quality_floor_without_fabricating_proposals() -> None:
    from backend.app.evidence_intent import plan_evidence_intent
    from backend.app.taste_profile import TasteProfile, build_taste_context

    taste = build_taste_context(TasteProfile(client_id="c", version=1, approved=True))
    intent = plan_evidence_intent({"transcript": "Un evento preciso", "intent": "show event"}, "event", "ENTITY", taste)
    dead = {**_row("dead", score=.85, source="youtube", provider_id="dead", width=1080, height=1920, preview_sha256="dead"), "source_class": "EXACT_ENTITY_EVENT", "evidence_specificity": .9, "editorial_quality": .2}
    result = select_proposals([dead], taste=taste, evidence_intent=intent)
    assert result["proposal_A"] is None
    assert result["proposal_B"] is None
    assert result["review_state"] == "NO_BROLL_QUALITY_FLOOR"
    assert result["rejected_candidates"][0]["rejection_reasons"] == ["editorial_quality_below_floor"]



def test_editorial_b_prefers_different_visual_motif_when_available() -> None:
    from backend.app.evidence_intent import plan_evidence_intent
    from backend.app.taste_profile import TasteProfile, build_taste_context

    taste = build_taste_context(TasteProfile(client_id="c", version=1, approved=True))
    intent = plan_evidence_intent({"transcript": "Un concetto visivo", "intent": "show concept"}, "concept", "CONCEPT", taste)
    rows = [
        {**_row("a", score=.90, source="youtube", provider_id="a", width=1080, height=1920, preview_sha256="a"), "source_class": "CLOSE_SEMANTIC_EDITORIAL", "editorial_quality": .9, "motif_id": "node-graph"},
        {**_row("lookalike", score=.88, source="youtube", provider_id="b", width=1080, height=1920, preview_sha256="b"), "source_class": "CLOSE_SEMANTIC_EDITORIAL", "editorial_quality": .9, "motif_id": "node-graph"},
        {**_row("different", score=.80, source="youtube", provider_id="c", width=1080, height=1920, preview_sha256="c"), "source_class": "CLOSE_SEMANTIC_EDITORIAL", "editorial_quality": .9, "motif_id": "live-camera"},
    ]
    result = select_proposals(rows, taste=taste, evidence_intent=intent)
    assert result["proposal_A"]["id"] == "a"
    assert result["proposal_B"]["id"] == "different"
