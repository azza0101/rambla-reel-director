"""Client-scoped Taste profile primitives.

This module is intentionally runtime-light: profiles are immutable snapshots,
explicit guardrail changes create a new unapproved version, and the canonical
hash is suitable for freezing into an Edit Plan.
"""

from __future__ import annotations

import hashlib
import json
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
