from __future__ import annotations

from dataclasses import replace

import pytest

from backend.app.taste_profile import (
    TasteProfile,
    apply_guardrail_override,
    build_taste_context,
    canonical_taste_hash,
)


def _profile() -> TasteProfile:
    return TasteProfile(
        client_id="client-a",
        version=3,
        approved=True,
        route_weights={"RECEIPT": 0.7, "ENTITY": 0.6, "STOCK": 0.2},
        guardrails={"memes": False, "audio_policy": "strip"},
        trusted_sources={"tech": ("youtube:OpenAI",)},
        default_proposal_count=2,
    )


def test_taste_hash_is_stable_and_client_scoped() -> None:
    profile = _profile()
    assert canonical_taste_hash(profile) == canonical_taste_hash(replace(profile))
    other = replace(profile, client_id="client-b")
    assert canonical_taste_hash(profile) != canonical_taste_hash(other)


def test_guardrail_override_creates_new_unapproved_version_without_mutating_input() -> None:
    profile = _profile()
    updated = apply_guardrail_override(profile, {"memes": True})
    assert profile.guardrails["memes"] is False
    assert updated.version == 4
    assert updated.approved is False
    assert updated.guardrails["memes"] is True


def test_context_exposes_only_client_profile_and_topic_sources() -> None:
    ctx = build_taste_context(_profile(), topic="tech", genre="explainer")
    assert ctx.client_id == "client-a"
    assert ctx.profile_version == 3
    assert ctx.trusted_sources == ("youtube:OpenAI",)
    assert ctx.guardrails["memes"] is False


def test_invalid_profile_rejects_bad_route_weight() -> None:
    with pytest.raises(ValueError, match="route weight"):
        TasteProfile(client_id="client-a", version=1, approved=True, route_weights={"STOCK": 1.5})
