"""Deterministic, provider-free evidence planning for visual coverage slots."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from .taste_profile import TasteContext
from .visual_routing import VisualRouteDecision, route_name


@dataclass(frozen=True)
class EvidenceIntent:
    evidence_intent_type: str
    target_entities: tuple[str, ...]
    target_event_or_claim: str | None
    acceptable_visual_forms: tuple[str, ...]
    unacceptable_substitutions: tuple[str, ...]
    specificity_required: float
    can_use_still: bool
    can_use_composite_with_speaker: bool
    fallback_route_order: tuple[str, ...]


_SENTENCE_STARTERS = frozenset(
    {"Questo", "Questa", "Questi", "Queste", "Poi", "Qui", "Quando", "Come", "Perché", "Oggi", "Ieri", "Domani", "Nel", "Nella", "Un", "Una", "Il", "La", "Lo", "In"}
)


def _entities(slot: Mapping[str, Any]) -> tuple[str, ...]:
    text = " ".join((str(slot.get("transcript", "")), str(slot.get("intent", ""))))
    candidates = re.findall(r"\b[A-ZÀ-Ý][\wÀ-ÿ-]{2,}\b", text)
    return tuple(dict.fromkeys(candidate for candidate in candidates if candidate not in _SENTENCE_STARTERS))


def _claim(slot: Mapping[str, Any], context: str) -> str | None:
    transcript = str(slot.get("transcript", "")).strip()
    intent = str(slot.get("intent", "")).strip()
    if '"' in transcript or "'" in transcript:
        return transcript
    return intent or context.strip() or transcript or None


def _specificity(route: str, taste: TasteContext, default: float) -> float:
    return max(default, taste.style_dna.minimum_evidence_specificity_by_route.get(route, 0.0))


def plan_evidence_intent(
    slot: Mapping[str, Any],
    context: str,
    route: VisualRouteDecision | str,
    taste: TasteContext,
) -> EvidenceIntent:
    """Describe the visual proof required before any discovery provider is called."""
    selected_route = route_name(route)
    entities = _entities(slot)
    claim = _claim(slot, context)
    plans = {
        "RECEIPT": ("EXACT_RECEIPT", ("original post", "article", "document", "chart", "screenshot"), ("generic stock", "unrelated illustration"), 0.75, True, True, ("RECEIPT", "ENTITY", "CONCEPT", "STOCK")),
        "PRODUCT_UI": ("PRODUCT_UI_DEMO", ("exact product UI", "official demo", "workflow screenshot"), ("generic software tutorial", "unrelated app interface"), 0.75, True, True, ("PRODUCT_UI", "ENTITY", "CONCEPT", "STOCK")),
        "ENTITY": ("EXACT_ENTITY_EVENT", ("exact entity footage", "event image", "official profile"), ("generic portrait", "unrelated person"), 0.65, True, True, ("ENTITY", "RECEIPT", "ARCHIVAL", "CONCEPT", "STOCK")),
        "ARCHIVAL": ("ARCHIVAL_EVIDENCE", ("archival footage", "historical image", "primary record"), ("generic period stock", "unrelated history footage"), 0.70, True, True, ("ARCHIVAL", "RECEIPT", "ENTITY", "CONCEPT", "STOCK")),
        "CULTURAL": ("CULTURAL_REFERENCE", ("recognizable cultural reference", "source-native reaction"), ("generic reaction footage",), 0.60, False, False, ("CULTURAL", "ENTITY", "CONCEPT", "STOCK")),
        "CONCEPT": ("EXPLANATORY_CONCEPT", ("explanatory graphic", "relevant demonstration", "concept footage"), ("keyword-only filler",), 0.40, True, True, ("CONCEPT", "STOCK")),
        "STOCK": ("GENERIC_CONTEXT", ("contextual stock footage",), ("misleading literal claim",), 0.25, False, False, ("STOCK",)),
    }
    intent_type, forms, unacceptable, default, can_use_still, can_composite, fallbacks = plans.get(
        selected_route,
        plans["CONCEPT"],
    )
    return EvidenceIntent(
        evidence_intent_type=intent_type,
        target_entities=entities,
        target_event_or_claim=claim,
        acceptable_visual_forms=forms,
        unacceptable_substitutions=unacceptable,
        specificity_required=_specificity(selected_route, taste, default),
        can_use_still=can_use_still,
        can_use_composite_with_speaker=can_composite,
        fallback_route_order=fallbacks,
    )
