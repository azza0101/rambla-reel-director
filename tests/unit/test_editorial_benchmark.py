from backend.app.editorial_benchmark import compare_editorial_to_semantic
from backend.app.evidence_intent import plan_evidence_intent
from backend.app.taste_profile import TasteProfile, build_taste_context


def test_benchmark_exposes_baseline_and_exact_evidence_improvement():
    taste = build_taste_context(TasteProfile(client_id="test", version=1, approved=True))
    intent = plan_evidence_intent({"transcript": 'OpenAI ha scritto "test"'}, "original post", "RECEIPT", taste)
    candidates = [
        {"id": "stock", "provider_id": "stock", "source": "pexels", "source_class": "GENERIC_STOCK", "score": .96, "editorial_quality": .95, "width": 1080, "height": 1920},
        {"id": "dead", "provider_id": "dead", "source": "web", "source_class": "EXACT_RECEIPT", "score": .94, "editorial_quality": .1, "width": 1080, "height": 1920},
        {"id": "receipt-a", "provider_id": "receipt-a", "source": "web", "source_class": "EXACT_RECEIPT", "score": .91, "editorial_quality": .85, "width": 1080, "height": 1920},
        {"id": "receipt-b", "provider_id": "receipt-b", "source": "web", "source_class": "EXACT_RECEIPT", "score": .88, "editorial_quality": .8, "width": 1080, "height": 1920},
    ]
    report = compare_editorial_to_semantic([{"id": "slot", "candidates": candidates, "intent": intent, "taste": taste}])
    assert report["baseline_vs_editorial"][0]["baseline_ids"][0] == "stock"
    assert report["baseline_vs_editorial"][0]["editorial_ids"] == ["receipt-a", "receipt-b"]
    assert "dead" in report["baseline_vs_editorial"][0]["rejected_ids"]
    assert report["slots_with_two_eligible_proposals"] == 1
    assert report["mean_evidence_specificity_selected"] > .75
    assert report["resolve_calls"] == 0
