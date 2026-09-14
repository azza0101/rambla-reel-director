from __future__ import annotations

from dataclasses import replace

import pytest

from backend.app.taste_profile import (
    ReferenceStyleProfile,
    StyleDNA,
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


def _style() -> StyleDNA:
    return StyleDNA(
        reference_profiles=(
            ReferenceStyleProfile(
                id="factanza_evidence_editorial",
                speaker_persistence=0.82,
                coverage_density=0.58,
                median_insert_seconds=3.9,
                route_mix={"RECEIPT": 0.42, "ARCHIVAL": 0.22, "STOCK": 0.02},
                presentation_mix={
                    "SPEAKER_PLUS_EVIDENCE_TOP": 0.45,
                    "FULL_FRAME_CUTAWAY": 0.25,
                },
            ),
            ReferenceStyleProfile(
                id="olimpia_social_kinetic",
                speaker_persistence=0.62,
                coverage_density=0.82,
                median_insert_seconds=1.2,
                route_mix={"ENTITY": 0.30, "CULTURAL": 0.20, "STOCK": 0.01},
                presentation_mix={"FULL_FRAME_CUTAWAY": 0.72},
            ),
        ),
        active_style_mix={
            "factanza_evidence_editorial": 0.7,
            "olimpia_social_kinetic": 0.3,
        },
        generic_stock_penalty=0.35,
        exact_evidence_bonus=0.20,
        source_native_bonus=0.10,
        minimum_editorial_quality=0.55,
        minimum_evidence_specificity_by_route={"RECEIPT": 0.75, "ENTITY": 0.65},
        maximum_repetition_by_source_or_motif=1,
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


def test_style_dna_preserves_independent_reference_profiles() -> None:
    style = _style()
    assert tuple(profile.id for profile in style.reference_profiles) == (
        "factanza_evidence_editorial",
        "olimpia_social_kinetic",
    )
    assert style.reference_profiles[0].route_mix["RECEIPT"] == 0.42
    assert style.reference_profiles[1].route_mix["ENTITY"] == 0.30


def test_style_mix_is_validated_and_canonicalized() -> None:
    style = StyleDNA(
        reference_profiles=_style().reference_profiles,
        active_style_mix={"olimpia_social_kinetic": 3, "factanza_evidence_editorial": 7},
    )
    assert dict(style.active_style_mix) == {
        "factanza_evidence_editorial": 0.7,
        "olimpia_social_kinetic": 0.3,
    }
    with pytest.raises(ValueError, match="known reference profile"):
        StyleDNA(active_style_mix={"unknown": 1})


def test_style_dna_participates_in_canonical_hash() -> None:
    base = TasteProfile(client_id="c", version=1, approved=True, style_dna=_style())
    assert canonical_taste_hash(base) == canonical_taste_hash(replace(base))
    changed = replace(base, style_dna=replace(_style(), generic_stock_penalty=0.5))
    assert canonical_taste_hash(base) != canonical_taste_hash(changed)


def test_style_mix_hash_is_independent_of_mapping_insertion_order() -> None:
    refs = tuple(
        ReferenceStyleProfile(
            id=name,
            speaker_persistence=0.5,
            coverage_density=0.5,
            median_insert_seconds=2.0,
        )
        for name in ("a", "b", "c")
    )
    forward = StyleDNA(reference_profiles=refs, active_style_mix={"a": 1e16, "b": 1, "c": 1})
    reverse = StyleDNA(reference_profiles=refs, active_style_mix={"c": 1, "b": 1, "a": 1e16})
    assert canonical_taste_hash(TasteProfile(client_id="c", version=1, approved=True, style_dna=forward)) == canonical_taste_hash(TasteProfile(client_id="c", version=1, approved=True, style_dna=reverse))


def test_taste_context_keeps_legacy_constructor_compatible() -> None:
    from backend.app.taste_profile import TasteContext

    context = TasteContext(
        client_id="c",
        profile_version=1,
        profile_hash="hash",
        route_weights={},
        guardrails={},
        trusted_sources=(),
        default_proposal_count=2,
    )
    assert context.style_dna == StyleDNA()


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_reference_style_rejects_non_finite_insert_duration(invalid: float) -> None:
    with pytest.raises(ValueError, match="median insert seconds"):
        ReferenceStyleProfile(
            id="reference",
            speaker_persistence=0.5,
            coverage_density=0.5,
            median_insert_seconds=invalid,
        )



def test_style_mix_normalizes_large_positive_weights_without_overflow() -> None:
    refs = tuple(
        ReferenceStyleProfile(
            id=name,
            speaker_persistence=0.5,
            coverage_density=0.5,
            median_insert_seconds=2.0,
        )
        for name in ("a", "b", "c")
    )
    style = StyleDNA(reference_profiles=refs, active_style_mix={"c": 1e308, "a": 1e308, "b": 1e308})
    assert list(style.active_style_mix) == ["a", "b", "c"]
    assert sum(style.active_style_mix.values()) == pytest.approx(1.0)
