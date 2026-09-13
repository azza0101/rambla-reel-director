from __future__ import annotations

from backend.app.taste_profile import TasteProfile, build_taste_context
from backend.app.visual_routing import plan_visual_route


def _taste(**guardrails):
    return build_taste_context(
        TasteProfile(
            client_id="client-a",
            version=1,
            approved=True,
            route_weights={"RECEIPT": 0.8, "ENTITY": 0.7, "STOCK": 0.1},
            guardrails=guardrails,
        )
    )


def test_direct_quote_routes_to_receipt_before_generic_stock() -> None:
    decision = plan_visual_route(
        {"transcript": 'Ha scritto: "questa funzione cambia tutto"', "intent": "quote from a post"},
        "Contesto: si parla di un post pubblico di una startup.",
        _taste(),
    )
    assert decision.route == "RECEIPT"
    assert decision.confidence >= 0.8


def test_named_product_ui_routes_to_product_ui() -> None:
    decision = plan_visual_route(
        {"transcript": "Poi apro Notion e creo il database", "intent": "show workflow"},
        "Tutorial software",
        _taste(),
    )
    assert decision.route == "PRODUCT_UI"


def test_explicit_meme_ban_prevents_cultural_route() -> None:
    decision = plan_visual_route(
        {"transcript": "qui ci starebbe una reaction meme", "intent": "reaction punchline"},
        "Comedic beat",
        _taste(memes=False),
    )
    assert decision.route != "CULTURAL"
    assert "guardrail" in decision.reason.lower()
