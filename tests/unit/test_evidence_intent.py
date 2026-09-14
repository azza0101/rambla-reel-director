from __future__ import annotations

from backend.app.evidence_intent import plan_evidence_intent
from backend.app.taste_profile import TasteProfile, build_taste_context
from backend.app.visual_routing import VisualRouteDecision


def _taste():
    return build_taste_context(
        TasteProfile(
            client_id="client-a",
            version=1,
            approved=True,
        )
    )


def test_quote_requires_exact_receipt() -> None:
    intent = plan_evidence_intent(
        {"transcript": 'Ha scritto "non venderemo i dati"', "intent": "show the claim"},
        "Si parla del post ufficiale della società.",
        "RECEIPT",
        _taste(),
    )
    assert intent.evidence_intent_type == "EXACT_RECEIPT"
    assert intent.specificity_required >= 0.75
    assert "generic stock" in intent.unacceptable_substitutions
    assert intent.can_use_still is True


def test_named_product_prefers_exact_ui_not_generic_tutorial() -> None:
    intent = plan_evidence_intent(
        {"transcript": "In ComfyUI collego questi due nodi", "intent": "show actual workflow"},
        "software workflow",
        "PRODUCT_UI",
        _taste(),
    )
    assert intent.evidence_intent_type == "PRODUCT_UI_DEMO"
    assert "generic software tutorial" in intent.unacceptable_substitutions


def test_accepts_visual_route_decision() -> None:
    intent = plan_evidence_intent(
        {"transcript": "Nel 1990 accadde questo", "intent": "historical context"},
        "history",
        VisualRouteDecision("ARCHIVAL", "historical", 0.8, "find archive"),
        _taste(),
    )
    assert intent.evidence_intent_type == "ARCHIVAL_EVIDENCE"
