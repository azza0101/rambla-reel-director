from __future__ import annotations

from backend.app.evidence_intent import plan_evidence_intent
from backend.app.source_strategy import plan_source_strategy
from backend.app.taste_profile import TasteProfile, build_taste_context


def _taste():
    return build_taste_context(TasteProfile(client_id="c", version=1, approved=True))


def test_receipt_strategy_starts_exact_and_stock_is_last() -> None:
    taste = _taste()
    intent = plan_evidence_intent(
        {"transcript": 'Ha scritto "non venderemo i dati"', "intent": "show claim"},
        "post ufficiale della società", "RECEIPT", taste,
    )
    strategy = plan_source_strategy(intent, "RECEIPT", taste)
    assert strategy.classes[0] == "EXACT_RECEIPT"
    assert strategy.classes[-1] == "GENERIC_STOCK"
    assert strategy.query_families["EXACT_RECEIPT"]
    assert strategy.query_families["GENERIC_STOCK"]


def test_product_ui_prefers_exact_demo_before_related_editorial() -> None:
    taste = _taste()
    intent = plan_evidence_intent(
        {"transcript": "In ComfyUI collego questi nodi", "intent": "show actual workflow"},
        "software workflow", "PRODUCT_UI", taste,
    )
    strategy = plan_source_strategy(intent, "PRODUCT_UI", taste)
    assert strategy.classes.index("PRODUCT_UI_DEMO") < strategy.classes.index("CLOSE_SEMANTIC_EDITORIAL")
    assert strategy.classes[-1] == "GENERIC_STOCK"


def test_source_strategy_keeps_query_families_inspectable_and_deterministic() -> None:
    taste = _taste()
    intent = plan_evidence_intent({"transcript": "Rambla Studio gira dal vivo", "intent": "show entity"}, "film production", "ENTITY", taste)
    first = plan_source_strategy(intent, "ENTITY", taste)
    second = plan_source_strategy(intent, "ENTITY", taste)
    assert first == second
    assert set(first.query_families) == set(first.classes)
    assert "GENERIC_STOCK" in first.classes
