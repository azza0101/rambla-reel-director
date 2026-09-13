from __future__ import annotations

from backend.app.director_preview import render_report


def test_coverage_review_exposes_route_and_separate_taste_score_components() -> None:
    proposal_a = {
        "id": "youtube:receipt",
        "client_id": "client-a",
        "source": "youtube",
        "provider_id": "receipt",
        "source_page": "https://www.youtube.com/watch?v=receipt",
        "preview_path": "Z:/cache/receipt.jpg",
        "path": "Z:/cache/receipt.jpg",
        "qwen_score": 0.88,
        "semantic_score": 0.88,
        "evidence_route_score": 1.0,
        "crop_score": 0.3164,
        "taste_score": 0.93,
        "taste_components": {"route_match": 0.9, "trusted_source": 1.0},
        "final_score": 0.847,
        "needs_tracking": True,
        "rights_state": "review_required",
    }
    proposal_b = {
        "id": "pexels:stock",
        "client_id": "client-a",
        "source": "pexels",
        "provider_id": "stock",
        "source_page": "https://www.pexels.com/video/stock/",
        "preview_path": "Z:/cache/stock.jpg",
        "path": "Z:/cache/stock.jpg",
        "qwen_score": 0.90,
        "semantic_score": 0.90,
        "evidence_route_score": 0.1,
        "crop_score": 1.0,
        "taste_score": 0.22,
        "taste_components": {"route_match": 0.1, "trusted_source": 0.5},
        "final_score": 0.722,
        "needs_tracking": False,
        "rights_state": "provider_stock_terms",
    }
    plan = {
        "client_id": "client-a",
        "content_hash": "hash",
        "taste_snapshot": {"client_id": "client-a", "profile_version": 3, "profile_hash": "taste-hash"},
        "source": {"fps": 25, "duration_frames": 100, "media": "reel.mp4"},
        "beats": [{
            "id": "beat-1", "start_frame": 0, "end_frame": 100,
            "transcript": "OpenAI ha scritto che cambia tutto.", "action": "BROLL",
            "rationale": "evidence", "broll_query": "original post", "selected_asset": None,
            "candidates": [], "caption_text": "OpenAI ha scritto", "review_state": "AUTO_SELECTED", "providers": {},
        }],
        "coverage_slots": [{
            "id": "beat-1:coverage:1", "beat_id": "beat-1",
            "start_frame": 6, "end_frame": 94, "start_seconds": 0.25, "end_seconds": 3.75,
            "visual_intent": "show original claim", "queries": ["original post"],
            "evidence_class": "exact_or_related_evidence", "minimum_proposals": 2,
            "visual_route": "RECEIPT", "route_reason": "direct claim should use authentic receipt",
            "route_confidence": 0.92, "taste_profile_version": 3, "taste_profile_hash": "taste-hash",
            "applicable_guardrails": {"memes": False},
            "proposal_A": proposal_a, "proposal_B": proposal_b, "proposal_C": None,
            "selected_proposal_id": "youtube:receipt", "review_state": "READY",
        }],
        "captions": [{"start_frame": 0, "end_frame": 100, "text": "OpenAI ha scritto", "review_state": "ASR_UNREVIEWED"}],
    }

    html = render_report(plan)

    assert "Route: RECEIPT" in html
    assert "Taste v3" in html
    assert "direct claim should use authentic receipt" in html
    assert "semantic 0.88" in html
    assert "route 1.0" in html
    assert "crop 0.3164" in html
    assert "taste 0.93" in html
    assert "final" in html
