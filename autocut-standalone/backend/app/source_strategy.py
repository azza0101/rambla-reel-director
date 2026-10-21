"""Deterministic evidence-first source-class search plan."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .evidence_intent import EvidenceIntent
from .taste_profile import TasteContext
from .visual_routing import VisualRouteDecision, route_name

SOURCE_CLASSES = (
    "EXACT_RECEIPT",
    "EXACT_ENTITY_EVENT",
    "SOURCE_NATIVE_SOCIAL",
    "ARCHIVAL_REPERTORY",
    "PRODUCT_UI_DEMO",
    "CULTURAL_REFERENCE",
    "CLOSE_SEMANTIC_EDITORIAL",
    "GENERIC_STOCK",
)

_ORDER = {
    "RECEIPT": ("EXACT_RECEIPT", "EXACT_ENTITY_EVENT", "SOURCE_NATIVE_SOCIAL", "ARCHIVAL_REPERTORY", "CLOSE_SEMANTIC_EDITORIAL", "GENERIC_STOCK"),
    "ENTITY": ("EXACT_ENTITY_EVENT", "SOURCE_NATIVE_SOCIAL", "EXACT_RECEIPT", "ARCHIVAL_REPERTORY", "CLOSE_SEMANTIC_EDITORIAL", "GENERIC_STOCK"),
    "PRODUCT_UI": ("PRODUCT_UI_DEMO", "EXACT_RECEIPT", "SOURCE_NATIVE_SOCIAL", "CLOSE_SEMANTIC_EDITORIAL", "GENERIC_STOCK"),
    "ARCHIVAL": ("ARCHIVAL_REPERTORY", "EXACT_RECEIPT", "EXACT_ENTITY_EVENT", "CLOSE_SEMANTIC_EDITORIAL", "GENERIC_STOCK"),
    "CULTURAL": ("CULTURAL_REFERENCE", "SOURCE_NATIVE_SOCIAL", "EXACT_ENTITY_EVENT", "CLOSE_SEMANTIC_EDITORIAL", "GENERIC_STOCK"),
    "CONCEPT": ("CLOSE_SEMANTIC_EDITORIAL", "SOURCE_NATIVE_SOCIAL", "GENERIC_STOCK"),
    "STOCK": ("GENERIC_STOCK",),
}


@dataclass(frozen=True)
class SourceStrategy:
    classes: tuple[str, ...]
    query_families: Mapping[str, tuple[str, ...]]

    def __post_init__(self) -> None:
        if not self.classes or len(set(self.classes)) != len(self.classes):
            raise ValueError("source strategy requires unique classes")
        if any(item not in SOURCE_CLASSES for item in self.classes):
            raise ValueError("unsupported source class")
        if set(self.query_families) != set(self.classes):
            raise ValueError("query families must cover source classes")
        families = {
            key: tuple(dict.fromkeys(query.strip() for query in self.query_families[key] if query.strip()))
            for key in self.classes
        }
        if any(not values for values in families.values()):
            raise ValueError("each source class requires a query")
        object.__setattr__(self, "query_families", MappingProxyType(families))


def plan_source_strategy(
    intent: EvidenceIntent,
    route: VisualRouteDecision | str,
    taste: TasteContext,
) -> SourceStrategy:
    """Order exact/source-native classes ahead of generic fallback."""
    selected = route_name(route)
    classes = _ORDER.get(selected, _ORDER["CONCEPT"])
    entity = " ".join(intent.target_entities).strip()
    claim = (intent.target_event_or_claim or "").strip()
    subject = entity or claim or selected.lower().replace("_", " ")
    exact = " ".join(part for part in (entity, claim) if part).strip() or subject
    families = {
        "EXACT_RECEIPT": (f"{exact} original post document article",),
        "EXACT_ENTITY_EVENT": (f"{exact} official original event",),
        "SOURCE_NATIVE_SOCIAL": (f"{subject} original creator social clip",),
        "ARCHIVAL_REPERTORY": (f"{subject} archival original footage",),
        "PRODUCT_UI_DEMO": (f"{subject} official product UI demo",),
        "CULTURAL_REFERENCE": (f"{subject} original cultural reference",),
        "CLOSE_SEMANTIC_EDITORIAL": (f"{subject} relevant editorial footage",),
        "GENERIC_STOCK": (f"{subject} stock footage",),
    }
    return SourceStrategy(classes=classes, query_families={key: families[key] for key in classes})
