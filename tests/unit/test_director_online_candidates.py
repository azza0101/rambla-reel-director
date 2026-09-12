from __future__ import annotations

import copy

import pytest

from backend.app.director_engine import build_edit_plan, validate_edit_plan


def _transcript():
    return {
        "timeline_fps": 25,
        "timeline_start_frame": 0,
        "source": "reel.mp4",
        "language": "it",
        "segments": [{"start": 0.0, "end": 4.0, "text": "Passavo ore a fare tutto manualmente."}],
    }


def _outline():
    return {
        "beats": [
            {
                "id": "beat-1",
                "start_seconds": 0.0,
                "end_seconds": 4.0,
                "intent": "manual repetitive work",
                "broll_queries": ["frustrated creative repetitive computer work"],
            }
        ]
    }


def _remote(score=0.43, *, provider_id="42", source="pexels"):
    return {
        "id": f"{source}:{provider_id}",
        "client_id": "rambla",
        "path": f"Z:/cache/{provider_id}.jpg",
        "preview_path": f"Z:/cache/{provider_id}.jpg",
        "preview_sha256": provider_id * 8,
        "description": "person working on computer",
        "kind": "image",
        "source": source,
        "source_page": f"https://example.com/{source}/{provider_id}",
        "provider_id": provider_id,
        "creator": {"name": "Alice", "profile_page": "https://example.com/alice"},
        "rights_state": "review_required" if source == "youtube" else "provider_stock_terms",
        "query": "frustrated creative repetitive computer work",
        "selected_full_download": False,
        "embedding_score": score,
        "reranker_score": None,
        "score": score,
        "reason": "multimodal semantic embedding",
        "providers": {"embedding": "Qwen3-VL-Embedding-2B", "reranker": None, "retrieval": source},
        "width": 1920 if source == "youtube" else 1080,
        "height": 1080 if source == "youtube" else 1920,
    }


def _proposal(candidate: dict, *, final_score: float, crop_score: float, start=None, end=None):
    row = dict(candidate)
    row.update(
        {
            "qwen_score": candidate["embedding_score"],
            "semantic_score": candidate["score"],
            "crop_score": crop_score,
            "crop_box": [0.34, 0.0, 0.66, 1.0] if candidate["width"] > candidate["height"] else [0.0, 0.0, 1.0, 1.0],
            "needs_tracking": candidate["width"] > candidate["height"],
            "crop_usable": True,
            "final_score": final_score,
        }
    )
    if start is not None:
        row["source_start_seconds"] = start
    if end is not None:
        row["source_end_seconds"] = end
    return row


def _coverage_slot():
    a = _proposal(_remote(0.91, provider_id="abc", source="youtube"), final_score=0.79, crop_score=0.32, start=75.0, end=78.5)
    b = _proposal(_remote(0.84, provider_id="43", source="pexels"), final_score=0.872, crop_score=1.0)
    return {
        "id": "beat-1:coverage:1",
        "beat_id": "beat-1",
        "start_seconds": 0.25,
        "end_seconds": 3.75,
        "visual_intent": "show evidence of repetitive computer work",
        "queries": ["frustrated creative repetitive computer work"],
        "evidence_class": "exact_or_related_evidence",
        "minimum_proposals": 2,
        "proposal_A": a,
        "proposal_B": b,
        "proposal_C": None,
        "selected_proposal_id": a["id"],
        "review_state": "READY",
    }


def test_online_ranked_candidate_is_selected_and_persisted_without_resolve():
    plan = build_edit_plan(
        _transcript(),
        _outline(),
        [],
        client_id="rambla",
        source_frames=100,
        candidate_assets_by_beat={"beat-1": [_remote(0.43)]},
    )

    beat = plan["beats"][0]
    assert beat["action"] == "BROLL"
    assert beat["selected_asset"]["source"] == "pexels"
    assert beat["selected_asset"]["source_page"] == "https://example.com/pexels/42"
    assert beat["selected_asset"]["embedding_score"] == 0.43
    assert beat["review_state"] == "REVIEW_REQUIRED_LOW_CONFIDENCE"
    assert beat["providers"]["retrieval"] == "pexels"
    assert plan["retrieval"]["external"] == "online-sourcing-v1"


def test_slot_level_a_b_proposals_are_persisted_and_selected():
    slot = _coverage_slot()
    plan = build_edit_plan(
        _transcript(),
        _outline(),
        [],
        client_id="rambla",
        source_frames=100,
        candidate_assets_by_beat={"beat-1": [slot["proposal_A"], slot["proposal_B"]]},
        coverage_slots_by_beat={"beat-1": [slot]},
    )

    saved = plan["coverage_slots"][0]
    assert saved["proposal_A"]["source"] == "youtube"
    assert saved["proposal_B"]["source"] == "pexels"
    assert saved["selected_proposal_id"] == saved["proposal_A"]["id"]
    assert saved["proposal_A"]["source_start_seconds"] == 75.0
    assert saved["proposal_A"]["qwen_score"] == 0.91
    assert saved["proposal_A"]["crop_score"] == 0.32
    assert saved["review_state"] == "READY"
    validate_edit_plan(plan)


def test_validator_rejects_selected_slot_proposal_not_in_a_b_c():
    slot = _coverage_slot()
    plan = build_edit_plan(
        _transcript(),
        _outline(),
        [],
        client_id="rambla",
        source_frames=100,
        candidate_assets_by_beat={"beat-1": [slot["proposal_A"], slot["proposal_B"]]},
        coverage_slots_by_beat={"beat-1": [slot]},
    )
    broken = copy.deepcopy(plan)
    broken["coverage_slots"][0]["selected_proposal_id"] = "not-a-proposal"

    with pytest.raises(ValueError, match="selected proposal"):
        validate_edit_plan(broken)


def test_online_high_confidence_candidate_is_auto_selected_for_review_plan():
    plan = build_edit_plan(
        _transcript(),
        _outline(),
        [],
        client_id="rambla",
        source_frames=100,
        candidate_assets_by_beat={"beat-1": [_remote(0.86)]},
    )

    assert plan["beats"][0]["review_state"] == "AUTO_SELECTED"


def test_online_candidates_still_enforce_client_isolation():
    foreign = _remote(0.9)
    foreign["client_id"] = "other"

    with pytest.raises(ValueError, match="client"):
        build_edit_plan(
            _transcript(),
            _outline(),
            [],
            client_id="rambla",
            source_frames=100,
            candidate_assets_by_beat={"beat-1": [foreign]},
        )
