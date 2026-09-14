"""Client-scoped Taste profile primitives.

This module is intentionally runtime-light: profiles are immutable snapshots,
explicit guardrail changes create a new unapproved version, and the canonical
hash is suitable for freezing into an Edit Plan.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Mapping

ROUTES = frozenset(
    {
        "RECEIPT",
        "ENTITY",
        "PRODUCT_UI",
        "ARCHIVAL",
        "CONCEPT",
        "CULTURAL",
        "STOCK",
    }
)


def _freeze_map(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


def _bounded(value: float, name: str) -> float:
    numeric = float(value)
    if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise ValueError(f"{name} must lie between 0 and 1")
    return numeric


def _bounded_map(value: Mapping[str, float], name: str) -> Mapping[str, float]:
    return _freeze_map(
        {
            key: _bounded(item, name)
            for key, item in sorted(value.items())
        }
    )


@dataclass(frozen=True)
class ReferenceStyleProfile:
    """One immutable fingerprint for a single reference exemplar."""

    id: str
    speaker_persistence: float
    coverage_density: float
    median_insert_seconds: float
    route_mix: Mapping[str, float] = field(default_factory=dict)
    presentation_mix: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("reference style profile id is required")
        object.__setattr__(self, "speaker_persistence", _bounded(self.speaker_persistence, "speaker persistence"))
        object.__setattr__(self, "coverage_density", _bounded(self.coverage_density, "coverage density"))
        if float(self.median_insert_seconds) <= 0:
            raise ValueError("median insert seconds must be positive")
        object.__setattr__(self, "median_insert_seconds", float(self.median_insert_seconds))
        object.__setattr__(self, "route_mix", _bounded_map(self.route_mix, "route mix value"))
        object.__setattr__(self, "presentation_mix", _bounded_map(self.presentation_mix, "presentation mix value"))


@dataclass(frozen=True)
class StyleDNA:
    """Immutable active style snapshot, with independently retained exemplars."""

    reference_profiles: tuple[ReferenceStyleProfile, ...] = ()
    active_style_mix: Mapping[str, float] = field(default_factory=dict)
    generic_stock_penalty: float = 0.0
    exact_evidence_bonus: float = 0.0
    source_native_bonus: float = 0.0
    still_document_tolerance: float = 0.5
    cultural_reference_tolerance: float = 0.5
    split_layout_preference: float = 0.5
    full_screen_preference: float = 0.5
    visual_grit_tolerance: float = 0.5
    minimum_editorial_quality: float = 0.5
    minimum_evidence_specificity_by_route: Mapping[str, float] = field(default_factory=dict)
    maximum_repetition_by_source_or_motif: int = 1

    def __post_init__(self) -> None:
        profiles = tuple(self.reference_profiles)
        profile_ids = tuple(profile.id for profile in profiles)
        if len(set(profile_ids)) != len(profile_ids):
            raise ValueError("reference style profile ids must be unique")
        object.__setattr__(self, "reference_profiles", profiles)

        mix = {key: float(value) for key, value in self.active_style_mix.items()}
        unknown_ids = set(mix).difference(profile_ids)
        if unknown_ids:
            raise ValueError("style mix keys must reference a known reference profile")
        if any(not math.isfinite(value) or value <= 0.0 for value in mix.values()):
            raise ValueError("style mix weights must be positive")
        total = sum(mix.values())
        if mix and total <= 0.0:
            raise ValueError("style mix weights must have a positive total")
        object.__setattr__(
            self,
            "active_style_mix",
            _freeze_map({key: mix[key] / total for key in sorted(mix)}),
        )

        for name in (
            "generic_stock_penalty",
            "exact_evidence_bonus",
            "source_native_bonus",
            "still_document_tolerance",
            "cultural_reference_tolerance",
            "split_layout_preference",
            "full_screen_preference",
            "visual_grit_tolerance",
            "minimum_editorial_quality",
        ):
            object.__setattr__(self, name, _bounded(getattr(self, name), name.replace("_", " ")))

        specificity: dict[str, float] = {}
        for route, value in self.minimum_evidence_specificity_by_route.items():
            if route not in ROUTES:
                raise ValueError("evidence specificity must use a supported route")
            specificity[route] = _bounded(value, "minimum evidence specificity")
        object.__setattr__(
            self,
            "minimum_evidence_specificity_by_route",
            _freeze_map({key: specificity[key] for key in sorted(specificity)}),
        )
        if (
            isinstance(self.maximum_repetition_by_source_or_motif, bool)
            or not isinstance(self.maximum_repetition_by_source_or_motif, int)
            or self.maximum_repetition_by_source_or_motif < 1
        ):
            raise ValueError("maximum repetition must be positive")


@dataclass(frozen=True)
class TasteProfile:
    client_id: str
    version: int
    approved: bool
    route_weights: Mapping[str, float] = field(default_factory=dict)
    guardrails: Mapping[str, Any] = field(default_factory=dict)
    trusted_sources: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    default_proposal_count: int = 2
    pacing: Mapping[str, float] = field(default_factory=dict)
    provenance: tuple[str, ...] = ()
    style_dna: StyleDNA = field(default_factory=StyleDNA)

    def __post_init__(self) -> None:
        if not self.client_id or self.version < 1:
            raise ValueError("client identity and positive profile version are required")
        if self.default_proposal_count < 1:
            raise ValueError("default proposal count must be positive")

        normalized_weights: dict[str, float] = {}
        for name, value in self.route_weights.items():
            numeric = float(value)
            if name not in ROUTES or not 0.0 <= numeric <= 1.0:
                raise ValueError("route weight must use a supported route and lie between 0 and 1")
            normalized_weights[name] = numeric

        object.__setattr__(self, "route_weights", _freeze_map(normalized_weights))
        object.__setattr__(self, "guardrails", _freeze_map(self.guardrails))
        object.__setattr__(
            self,
            "trusted_sources",
            _freeze_map({key: tuple(values) for key, values in self.trusted_sources.items()}),
        )
        object.__setattr__(
            self,
            "pacing",
            _freeze_map({key: float(value) for key, value in self.pacing.items()}),
        )
        object.__setattr__(self, "provenance", tuple(self.provenance))


@dataclass(frozen=True)
class TasteContext:
    client_id: str
    profile_version: int
    profile_hash: str
    route_weights: Mapping[str, float]
    guardrails: Mapping[str, Any]
    trusted_sources: tuple[str, ...]
    default_proposal_count: int
    style_dna: StyleDNA
    topic: str | None = None
    genre: str | None = None


def _profile_payload(profile: TasteProfile) -> dict[str, Any]:
    return {
        "client_id": profile.client_id,
        "version": profile.version,
        "approved": profile.approved,
        "route_weights": dict(sorted(profile.route_weights.items())),
        "guardrails": dict(sorted(profile.guardrails.items())),
        "trusted_sources": {
            key: list(profile.trusted_sources[key]) for key in sorted(profile.trusted_sources)
        },
        "default_proposal_count": profile.default_proposal_count,
        "pacing": dict(sorted(profile.pacing.items())),
        "provenance": list(profile.provenance),
        "style_dna": _style_dna_payload(profile.style_dna),
    }


def _style_dna_payload(style_dna: StyleDNA) -> dict[str, Any]:
    return {
        "reference_profiles": [
            {
                "id": profile.id,
                "speaker_persistence": profile.speaker_persistence,
                "coverage_density": profile.coverage_density,
                "median_insert_seconds": profile.median_insert_seconds,
                "route_mix": dict(sorted(profile.route_mix.items())),
                "presentation_mix": dict(sorted(profile.presentation_mix.items())),
            }
            for profile in style_dna.reference_profiles
        ],
        "active_style_mix": dict(sorted(style_dna.active_style_mix.items())),
        "generic_stock_penalty": style_dna.generic_stock_penalty,
        "exact_evidence_bonus": style_dna.exact_evidence_bonus,
        "source_native_bonus": style_dna.source_native_bonus,
        "still_document_tolerance": style_dna.still_document_tolerance,
        "cultural_reference_tolerance": style_dna.cultural_reference_tolerance,
        "split_layout_preference": style_dna.split_layout_preference,
        "full_screen_preference": style_dna.full_screen_preference,
        "visual_grit_tolerance": style_dna.visual_grit_tolerance,
        "minimum_editorial_quality": style_dna.minimum_editorial_quality,
        "minimum_evidence_specificity_by_route": dict(
            sorted(style_dna.minimum_evidence_specificity_by_route.items())
        ),
        "maximum_repetition_by_source_or_motif": style_dna.maximum_repetition_by_source_or_motif,
    }


def canonical_taste_hash(profile: TasteProfile) -> str:
    raw = json.dumps(
        _profile_payload(profile),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_taste_context(
    profile: TasteProfile,
    *,
    topic: str | None = None,
    genre: str | None = None,
) -> TasteContext:
    return TasteContext(
        client_id=profile.client_id,
        profile_version=profile.version,
        profile_hash=canonical_taste_hash(profile),
        route_weights=profile.route_weights,
        guardrails=profile.guardrails,
        trusted_sources=tuple(profile.trusted_sources.get(topic or "", ())),
        default_proposal_count=profile.default_proposal_count,
        style_dna=profile.style_dna,
        topic=topic,
        genre=genre,
    )


def apply_guardrail_override(
    profile: TasteProfile,
    override: Mapping[str, Any],
) -> TasteProfile:
    merged = dict(profile.guardrails)
    merged.update(dict(override))
    return replace(
        profile,
        version=profile.version + 1,
        approved=False,
        guardrails=merged,
    )
