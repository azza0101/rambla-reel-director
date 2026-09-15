"""Inspectible, evidence-first editorial scoring on final candidate windows."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .evidence_intent import EvidenceIntent
from .taste_profile import TasteContext

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

_CLASS_SPECIFICITY = {
    "EXACT_RECEIPT": 1.0,
    "EXACT_ENTITY_EVENT": 0.9,
    "SOURCE_NATIVE_SOCIAL": 0.8,
    "ARCHIVAL_REPERTORY": 0.8,
    "PRODUCT_UI_DEMO": 0.9,
    "CULTURAL_REFERENCE": 0.7,
    "CLOSE_SEMANTIC_EDITORIAL": 0.5,
    "GENERIC_STOCK": 0.25,
}
_CLASS_AUTHENTICITY = {
    "EXACT_RECEIPT": 0.9,
    "EXACT_ENTITY_EVENT": 0.85,
    "SOURCE_NATIVE_SOCIAL": 0.85,
    "ARCHIVAL_REPERTORY": 0.75,
    "PRODUCT_UI_DEMO": 0.8,
    "CULTURAL_REFERENCE": 0.7,
    "CLOSE_SEMANTIC_EDITORIAL": 0.55,
    "GENERIC_STOCK": 0.45,
}
_EXACT_INTENTS = {"EXACT_RECEIPT", "EXACT_ENTITY_EVENT", "PRODUCT_UI_DEMO", "ARCHIVAL_EVIDENCE", "CULTURAL_REFERENCE"}


def _bounded(value: Any, name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError(f"{name} must be finite and between 0 and 1")
    return number


def _component(row: Mapping[str, Any], key: str, default: float) -> float:
    value = row.get(key)
    return _bounded(default if value is None else value, key)


def _presentation(row: Mapping[str, Any], intent: EvidenceIntent, taste: TasteContext) -> str:
    source_class = str(row.get("source_class") or "")
    width = int(row.get("width") or 0)
    height = int(row.get("height") or 0)
    if source_class == "EXACT_RECEIPT":
        return "DOCUMENT_CARD" if intent.can_use_still else "SPEAKER_PLUS_EVIDENCE_TOP"
    if source_class == "ARCHIVAL_REPERTORY":
        return "ARCHIVE_FRAME"
    if source_class == "SOURCE_NATIVE_SOCIAL":
        return "FULL_FRAME_CUTAWAY"
    if source_class == "PRODUCT_UI_DEMO":
        return "PIP_EVIDENCE" if taste.style_dna.split_layout_preference >= 0.5 else "FULL_FRAME_CUTAWAY"
    if width > height > 0 and intent.can_use_composite_with_speaker:
        return "SPEAKER_PLUS_EVIDENCE_TOP"
    if row.get("media_type") in {"image", "document"}:
        return "STILL_WITH_MOTION"
    return "FULL_FRAME_CUTAWAY"


@dataclass(frozen=True)
class EditorialScore:
    semantic_relevance: float
    evidence_specificity: float
    editorial_quality: float
    source_authority_authenticity: float
    style_fit: float
    composition_usability: float
    technical_quality: float
    diversity_novelty: float
    eligible: bool
    rejection_reasons: tuple[str, ...]
    recommended_presentation_mode: str
    final_score: float
    semantic_floor: float
    evidence_specificity_floor: float
    editorial_quality_floor: float

    @property
    def editorial_final_score(self) -> float:
        return self.final_score


def score_editorial_candidate(
    candidate: Mapping[str, Any],
    *,
    intent: EvidenceIntent,
    taste: TasteContext,
    recent_context: Sequence[Mapping[str, Any]] = (),
) -> EditorialScore:
    """Apply hard gates before weighted editorial ranking."""
    semantic = _component(candidate, "final_segment_semantic_score",
                          _component(candidate, "semantic_score", candidate.get("score", 0.0)))
    source_class = str(candidate.get("source_class") or "CLOSE_SEMANTIC_EDITORIAL")
    specificity = _component(candidate, "evidence_specificity", _CLASS_SPECIFICITY.get(source_class, 0.4))
    quality = _component(candidate, "editorial_quality",
                         max(0.0, min(1.0, float(candidate.get("visual_interest", 0.65)))))
    authority = _component(candidate, "source_authenticity", _CLASS_AUTHENTICITY.get(source_class, 0.5))
    style_default = 0.5
    if source_class == "GENERIC_STOCK":
        style_default -= taste.style_dna.generic_stock_penalty
    elif source_class.startswith("EXACT_"):
        style_default += taste.style_dna.exact_evidence_bonus
    elif source_class == "SOURCE_NATIVE_SOCIAL":
        style_default += taste.style_dna.source_native_bonus
    style = _component(candidate, "style_fit", max(0.0, min(1.0, style_default)))
    composition = _component(candidate, "composition_usability", 0.75)
    technical = _component(candidate, "technical_quality", 0.75)
    identity = str(candidate.get("provider_id") or candidate.get("id") or "")
    motif = str(candidate.get("motif_id") or "")
    repeated = any(
        (identity and identity == str(previous.get("provider_id") or previous.get("id") or ""))
        or (motif and motif == str(previous.get("motif_id") or ""))
        for previous in recent_context
    )
    diversity = _component(candidate, "diversity_novelty", 0.2 if repeated else 1.0)
    semantic_floor = 0.40
    evidence_floor = intent.specificity_required if intent.evidence_intent_type in _EXACT_INTENTS else 0.0
    editorial_floor = taste.style_dna.minimum_editorial_quality
    reasons = []
    if semantic < semantic_floor:
        reasons.append("semantic_relevance_below_floor")
    if specificity < evidence_floor:
        reasons.append("evidence_specificity_below_floor")
    if quality < editorial_floor:
        reasons.append("editorial_quality_below_floor")
    if candidate.get("broken") or candidate.get("blank"):
        reasons.append("broken_or_blank_final_segment")
    if candidate.get("rights_state") in {"blocked", "forbidden", "unlicensed"}:
        reasons.append("rights_or_provenance_blocked")
    if composition <= 0.0:
        reasons.append("composition_unusable")
    axes = {
        "semantic_relevance": semantic,
        "evidence_specificity": specificity,
        "editorial_quality": quality,
        "source_authority_authenticity": authority,
        "style_fit": style,
        "composition_usability": composition,
        "technical_quality": technical,
        "diversity_novelty": diversity,
    }
    final = round(sum(WEIGHTS[name] * value for name, value in axes.items()), 4)
    return EditorialScore(
        **axes,
        eligible=not reasons,
        rejection_reasons=tuple(reasons),
        recommended_presentation_mode=_presentation(candidate, intent, taste),
        final_score=final,
        semantic_floor=semantic_floor,
        evidence_specificity_floor=evidence_floor,
        editorial_quality_floor=editorial_floor,
    )
