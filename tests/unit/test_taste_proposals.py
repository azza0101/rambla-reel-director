from __future__ import annotations

from backend.app.proposals import select_proposals
from backend.app.taste_profile import TasteProfile, build_taste_context


def _taste():
    return build_taste_context(
        TasteProfile(
            client_id="client-a",
            version=1,
            approved=True,
            route_weights={"RECEIPT": 0.9, "STOCK": 0.1},
            guardrails={},
            trusted_sources={"tech": ("youtube:OpenAI",)},
        ),
        topic="tech",
    )


def _row(
    asset_id: str,
    score: float,
    *,
    source: str,
    provider_id: str,
    route: str,
    source_registry_key: str | None = None,
) -> dict:
    row = {
        "id": asset_id,
        "client_id": "client-a",
        "score": score,
        "embedding_score": score,
        "width": 1920,
        "height": 1080,
        "source": source,
        "provider_id": provider_id,
        "route": route,
    }
    if source_registry_key is not None:
        row["source_registry_key"] = source_registry_key
    return row


def test_taste_breaks_close_semantic_tie_but_cannot_overturn_large_relevance_gap() -> None:
    rows = [
        _row("stock", 0.90, source="pexels", provider_id="1", route="STOCK"),
        _row(
            "receipt",
            0.88,
            source="youtube",
            provider_id="2",
            route="RECEIPT",
            source_registry_key="youtube:OpenAI",
        ),
    ]
    close = select_proposals(rows, taste=_taste(), visual_route="RECEIPT")
    assert close["proposal_A"]["id"] == "receipt"

    rows[0]["score"] = rows[0]["embedding_score"] = 0.99
    rows[1]["score"] = rows[1]["embedding_score"] = 0.55
    far = select_proposals(rows, taste=_taste(), visual_route="RECEIPT")
    assert far["proposal_A"]["id"] == "stock"


def test_taste_components_are_exposed_not_opaque() -> None:
    result = select_proposals(
        [
            _row(
                "a",
                0.8,
                source="youtube",
                provider_id="1",
                route="RECEIPT",
                source_registry_key="youtube:OpenAI",
            )
        ],
        taste=_taste(),
        visual_route="RECEIPT",
    )
    proposal = result["proposal_A"]
    assert 0 <= proposal["taste_score"] <= 1
    assert set(proposal["taste_components"]) >= {"route_match", "trusted_source"}


def test_without_taste_context_existing_score_shape_remains_available() -> None:
    result = select_proposals(
        [_row("a", 0.8, source="pexels", provider_id="1", route="STOCK")]
    )
    proposal = result["proposal_A"]
    assert proposal["semantic_score"] == 0.8
    assert "crop_score" in proposal
    assert "final_score" in proposal


def test_editorial_mode_keeps_legacy_taste_path_separate() -> None:
    from backend.app.evidence_intent import plan_evidence_intent

    taste = _taste()
    intent = plan_evidence_intent({"transcript": 'Ha scritto "test"', "intent": "show claim"}, "post", "RECEIPT", taste)
    rows = [
        {**_row("exact", .82, source="youtube", provider_id="1", route="RECEIPT"), "source_class": "EXACT_RECEIPT", "evidence_specificity": 1.0, "editorial_quality": .8},
        {**_row("stock", .92, source="pexels", provider_id="2", route="STOCK"), "source_class": "GENERIC_STOCK", "evidence_specificity": .2, "editorial_quality": .9},
    ]
    editorial = select_proposals(rows, taste=taste, visual_route="RECEIPT", evidence_intent=intent)
    assert editorial["proposal_A"]["id"] == "exact"
    assert editorial["proposal_B"] is None
    assert editorial["review_state"] == "SINGLE_PROPOSAL_QUALITY_FLOOR"
    assert "rejected_candidates" in editorial
