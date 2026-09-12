from __future__ import annotations

from backend.app.director_engine import build_edit_plan


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


def _remote(score=0.43):
    return {
        "id": "pexels:42",
        "client_id": "rambla",
        "path": "Z:/cache/42.jpg",
        "preview_path": "Z:/cache/42.jpg",
        "description": "person working on computer",
        "kind": "image",
        "source": "pexels",
        "source_page": "https://www.pexels.com/video/42/",
        "provider_id": "42",
        "creator": {"name": "Alice", "profile_page": "https://www.pexels.com/@alice"},
        "rights_state": "provider_stock_terms",
        "query": "frustrated creative repetitive computer work",
        "selected_full_download": False,
        "embedding_score": score,
        "reranker_score": None,
        "score": score,
        "reason": "multimodal semantic embedding",
        "providers": {"embedding": "Qwen3-VL-Embedding-2B", "reranker": None, "retrieval": "pexels"},
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
    assert beat["selected_asset"]["source_page"] == "https://www.pexels.com/video/42/"
    assert beat["selected_asset"]["embedding_score"] == 0.43
    assert beat["review_state"] == "REVIEW_REQUIRED_LOW_CONFIDENCE"
    assert beat["providers"]["retrieval"] == "pexels"
    assert plan["retrieval"]["external"] == "online-sourcing-v1"


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

    try:
        build_edit_plan(
            _transcript(),
            _outline(),
            [],
            client_id="rambla",
            source_frames=100,
            candidate_assets_by_beat={"beat-1": [foreign]},
        )
    except ValueError as exc:
        assert "client" in str(exc)
    else:
        raise AssertionError("cross-client remote candidate was accepted")
