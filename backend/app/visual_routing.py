"""Deterministic visual routing before provider search.

The router decides what *kind* of evidence a coverage slot should seek. It is a
fallback/policy layer, not a replacement for the Director or Qwen ranking.
Explicit Taste guardrails always win over historical route preferences.
"""

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
    return " ".join(
        [str(slot.get("transcript", "")), str(slot.get("intent", "")), context]
    ).casefold()


def _named_entities(slot: Mapping[str, Any]) -> list[str]:
    original = " ".join(
        [str(slot.get("transcript", "")), str(slot.get("intent", ""))]
    )
    candidates = re.findall(r"\b[A-ZÀ-Ý][\wÀ-ÿ-]{2,}\b", original)
    sentence_starters = {
        "Questo",
        "Questa",
        "Questi",
        "Queste",
        "Poi",
        "Qui",
        "Quando",
        "Come",
        "Perché",
        "Oggi",
        "Ieri",
        "Domani",
        "Nel",
        "Nella",
        "Un",
        "Una",
        "Il",
        "La",
        "Lo",
    }
    return [candidate for candidate in candidates if candidate not in sentence_starters]


def plan_visual_route(
    slot: Mapping[str, Any],
    context: str,
    taste: TasteContext,
) -> VisualRouteDecision:
    text = _text(slot, context)
    memes_allowed = bool(taste.guardrails.get("memes", True))

    receipt_tokens = (
        "ha scritto",
        "tweet",
        "post",
        "articolo",
        "headline",
        "prezzo",
        "statistica",
        "studio",
        "ricerca mostra",
        "documento",
        "recensione",
    )
    if any(token in text for token in receipt_tokens) or '"' in text:
        return VisualRouteDecision(
            "RECEIPT",
            "Concrete claim/quote should use the original receipt.",
            0.9,
            "find authentic post/article/document",
        )

    product_tokens = (
        "app ",
        "software",
        "interfaccia",
        " ui ",
        "dashboard",
        "apro ",
        "clicco ",
        "schermata",
        "prodotto digitale",
    )
    if any(token in f" {text} " for token in product_tokens):
        return VisualRouteDecision(
            "PRODUCT_UI",
            "The beat describes a product/interface action.",
            0.85,
            "find current official UI/demo",
        )

    archival_tokens = ("nel 19", "nel 20", "storico", "archivio", "anni fa", "all'epoca")
    if any(token in text for token in archival_tokens):
        return VisualRouteDecision(
            "ARCHIVAL",
            "Historical context benefits from archival evidence.",
            0.8,
            "find authoritative archival footage/image",
        )

    if any(token in text for token in ("meme", "reaction", "reazione", "punchline")):
        if memes_allowed:
            return VisualRouteDecision(
                "CULTURAL",
                "Reaction beat and memes are allowed by the active profile.",
                0.75,
                "find culturally matching reaction",
            )
        return VisualRouteDecision(
            "CONCEPT",
            "Cultural route blocked by explicit guardrail; fall back to concept/talking head.",
            0.7,
            "use concept emphasis or no visual",
        )

    if _named_entities(slot):
        return VisualRouteDecision(
            "ENTITY",
            "Named entity detected; prefer exact subject/context footage.",
            0.7,
            "find named entity in the described context",
        )

    return VisualRouteDecision(
        "CONCEPT",
        "No concrete artifact/entity detected; prefer explanatory concept over generic stock.",
        0.55,
        "illustrate the underlying idea",
    )
