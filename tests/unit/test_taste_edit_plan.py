from __future__ import annotations

import pytest

from backend.app.director_engine import build_edit_plan, validate_edit_plan
from backend.app.taste_profile import TasteProfile, build_taste_context


def _transcript() -> dict:
    return {
        "source": "reel.mp4",
        "language": "it",
        "timeline_fps": 25,
        "segments": [
            {"start": 0.0, "end": 4.0, "text": "OpenAI ha scritto che il prodotto cambia tutto.", "words": []}
        ],
    }


def _outline() -> dict:
    return {
        "beats": [
            {
                "id": "beat-1",
                "start_seconds": 0.0,
                "end_seconds": 4.0,
                "intent": "show the original launch claim",
                "broll_queries": ["OpenAI original launch post"],
            }
        ]
    }


def _taste(client_id: str = "client-a"):
    return build_taste_context(
        TasteProfile(
            client_id=client_id,
            version=3,
            approved=True,
            route_weights={"RECEIPT": 0.9, "STOCK": 0.1},
            guardrails={"memes": False, "audio_policy": "strip"},
            default_proposal_count=2,
        ),
        topic="tech",
        genre="explainer",
    )


def test_edit_plan_persists_taste_snapshot_and_slot_route() -> None:
    taste = _taste()
    plan = build_edit_plan(
        _transcript(),
        _outline(),
        [],
        client_id="client-a",
        source_frames=100,
        taste_context=taste,
        route_by_slot={
            "beat-1:coverage:1": {
                "route": "RECEIPT",
                "reason": "direct claim should use the original post",
                "confidence": 0.92,
                "search_hint": "find authentic post",
            }
        },
    )

    assert plan["taste_snapshot"] == {
        "client_id": "client-a",
        "profile_version": 3,
        "profile_hash": taste.profile_hash,
    }
    slot = plan["coverage_slots"][0]
    assert slot["visual_route"] == "RECEIPT"
    assert slot["route_reason"] == "direct claim should use the original post"
    assert slot["route_confidence"] == 0.92
    assert slot["taste_profile_version"] == 3
    assert slot["taste_profile_hash"] == taste.profile_hash
    assert slot["applicable_guardrails"]["memes"] is False


def test_edit_plan_rejects_taste_context_from_other_client() -> None:
    with pytest.raises(ValueError, match="taste context violates client isolation"):
        build_edit_plan(
            _transcript(),
            _outline(),
            [],
            client_id="client-a",
            source_frames=100,
            taste_context=_taste("client-b"),
        )


def test_validate_edit_plan_rejects_tampered_slot_taste_hash() -> None:
    taste = _taste()
    plan = build_edit_plan(
        _transcript(),
        _outline(),
        [],
        client_id="client-a",
        source_frames=100,
        taste_context=taste,
        route_by_slot={"beat-1:coverage:1": {"route": "RECEIPT", "reason": "receipt", "confidence": 0.9}},
    )
    plan["coverage_slots"][0]["taste_profile_hash"] = "tampered"

    with pytest.raises(ValueError, match="taste snapshot"):
        validate_edit_plan(plan)
