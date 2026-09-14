from __future__ import annotations

from backend.app.editorial_quality import score_editorial_candidate
from backend.app.evidence_intent import plan_evidence_intent
from backend.app.taste_profile import StyleDNA, TasteProfile, build_taste_context


def _taste():
    return build_taste_context(TasteProfile(client_id="c", version=1, approved=True, style_dna=StyleDNA(minimum_editorial_quality=0.55, minimum_evidence_specificity_by_route={"RECEIPT": 0.75, "ENTITY": 0.65})))


def _intent(route):
    return plan_evidence_intent({"transcript": 'Ha scritto "non venderemo i dati"', "intent": "show evidence"}, "post ufficiale", route, _taste())


def test_exact_evidence_beats_pristine_generic_stock() -> None:
    exact = score_editorial_candidate({"id": "exact", "semantic_score": 0.84, "source_class": "EXACT_RECEIPT", "evidence_specificity": 1.0, "source_authenticity": 0.95, "editorial_quality": 0.72, "composition_usability": 0.80, "technical_quality": 0.65, "source": "web", "motif_id": "article-receipt"}, intent=_intent("RECEIPT"), taste=_taste())
    stock = score_editorial_candidate({"id": "stock", "semantic_score": 0.91, "source_class": "GENERIC_STOCK", "evidence_specificity": 0.25, "source_authenticity": 0.55, "editorial_quality": 0.90, "composition_usability": 0.95, "technical_quality": 0.95, "source": "pexels", "motif_id": "person-laptop"}, intent=_intent("RECEIPT"), taste=_taste())
    assert exact.eligible is True
    assert exact.final_score > stock.final_score
    assert "evidence_specificity_below_floor" in stock.rejection_reasons
    assert exact.recommended_presentation_mode in {"DOCUMENT_CARD", "SPEAKER_PLUS_EVIDENCE_TOP"}


def test_low_editorial_quality_is_ineligible() -> None:
    score = score_editorial_candidate({"id": "dead", "semantic_score": 0.86, "source_class": "EXACT_ENTITY_EVENT", "evidence_specificity": 0.8, "editorial_quality": 0.25, "source_authenticity": 0.8, "composition_usability": 0.8, "technical_quality": 0.8}, intent=_intent("ENTITY"), taste=_taste())
    assert score.eligible is False
    assert "editorial_quality_below_floor" in score.rejection_reasons


def test_style_cannot_rescue_semantically_wrong_candidate() -> None:
    score = score_editorial_candidate({"id": "pretty-wrong", "semantic_score": 0.18, "source_class": "SOURCE_NATIVE_SOCIAL", "evidence_specificity": 0.9, "editorial_quality": 0.95, "style_fit": 1.0, "source_authenticity": 1.0, "composition_usability": 1.0, "technical_quality": 1.0}, intent=_intent("ENTITY"), taste=_taste())
    assert score.eligible is False
    assert "semantic_relevance_below_floor" in score.rejection_reasons
    assert score.semantic_relevance == 0.18


def test_final_segment_score_overrides_coarse_score() -> None:
    score = score_editorial_candidate({"id": "coarse-illusion", "semantic_score": 0.88, "final_segment_semantic_score": 0.2, "source_class": "EXACT_RECEIPT", "evidence_specificity": 1.0, "editorial_quality": 0.9}, intent=_intent("RECEIPT"), taste=_taste())
    assert score.semantic_relevance == 0.2
    assert score.eligible is False
