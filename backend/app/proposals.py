"""Editorial proposal selection after semantic ranking.

Qwen remains responsible for semantic similarity. This module adds explicit
evidence-route correctness, crop feasibility, bounded Taste compatibility, and
diversity so review surfaces receive meaningful A/B alternatives rather than
one opaque winner.
"""

from __future__ import annotations

from typing import Any

from .crop_safety import evaluate_static_crop
from .taste_profile import TasteContext


_RELEVANCE_GAP_GUARD = 0.20


def _evidence_route_score(row: dict[str, Any], visual_route: str | None) -> float:
    """Score whether the candidate belongs to the requested evidence lane.

    Route correctness is editorial evidence, not Taste. Unknown routes stay
    neutral; generic stock is deliberately weak when an exact evidence route was
    requested, but it remains eligible as fallback.
    """

    if not visual_route:
        return 0.5
    row_route = str(row.get("route") or "")
    if not row_route:
        return 0.5
    if row_route == visual_route:
        return 1.0
    if row_route == "STOCK" and visual_route != "STOCK":
        return 0.10
    return 0.35


def _taste_score(
    row: dict[str, Any],
    taste: TasteContext | None,
) -> tuple[float, dict[str, float]]:
    if taste is None:
        return 0.5, {"route_match": 0.5, "trusted_source": 0.5}

    row_route = str(row.get("route") or "")
    # This component reflects the client's historical/declared route preference,
    # while _evidence_route_score() separately represents the route requested by
    # the current narration.
    route_match = float(taste.route_weights.get(row_route, 0.5))
    trusted_source = (
        1.0
        if str(row.get("source_registry_key") or "") in taste.trusted_sources
        else 0.5
    )
    score = max(0.0, min(1.0, 0.7 * route_match + 0.3 * trusted_source))
    return round(score, 4), {
        "route_match": round(route_match, 4),
        "trusted_source": round(trusted_source, 4),
    }


def _proposal_row(
    row: dict[str, Any],
    target_aspect: float,
    *,
    taste: TasteContext | None,
    visual_route: str | None,
) -> dict[str, Any]:
    width = int(row.get("width") or 0)
    height = int(row.get("height") or 0)
    assessment = evaluate_static_crop(width, height, target_aspect)
    semantic_score = float(row.get("score", 0.0))
    if not 0.0 <= semantic_score <= 1.0:
        raise ValueError("candidate score must be between 0 and 1")

    result = dict(row)
    result["qwen_score"] = round(float(row.get("embedding_score", semantic_score)), 4)
    result["semantic_score"] = round(semantic_score, 4)
    result["crop_score"] = assessment.score
    result["crop_box"] = list(assessment.crop_box)
    result["needs_tracking"] = assessment.needs_tracking
    result["crop_usable"] = assessment.usable
    result["crop_reason"] = assessment.reason
    result["evidence_route_score"] = round(_evidence_route_score(result, visual_route), 4)
    taste_score, taste_components = _taste_score(result, taste)
    result["taste_score"] = taste_score
    result["taste_components"] = taste_components

    if taste is None and visual_route is None:
        # Preserve legacy ranking exactly when the Taste Engine is not active.
        result["final_score"] = round(
            0.8 * semantic_score + 0.2 * assessment.score,
            4,
        )
    else:
        # Evidence correctness precedes geometric convenience and Taste. Qwen
        # remains the largest score component; the hard semantic-gap guard below
        # prevents this policy layer from rescuing a clearly irrelevant asset.
        result["final_score"] = round(
            0.65 * semantic_score
            + 0.15 * result["evidence_route_score"]
            + 0.10 * assessment.score
            + 0.10 * taste_score,
            4,
        )
    return result


def _distinct(candidate: dict[str, Any], selected: list[dict[str, Any]]) -> bool:
    identity = (
        str(candidate.get("source", "")),
        str(candidate.get("provider_id", candidate.get("id", ""))),
    )
    preview_hash = str(candidate.get("preview_sha256") or "")
    for existing in selected:
        existing_identity = (
            str(existing.get("source", "")),
            str(existing.get("provider_id", existing.get("id", ""))),
        )
        if identity == existing_identity:
            return False
        existing_hash = str(existing.get("preview_sha256") or "")
        if preview_hash and existing_hash and preview_hash == existing_hash:
            return False
    return True


def _apply_relevance_gap_guard(prepared: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep policy/crop/Taste as close-call factors, not relevance overrides."""

    if len(prepared) < 2:
        return prepared
    best_semantic = max(
        prepared,
        key=lambda row: (float(row["semantic_score"]), str(row.get("id", ""))),
    )
    first = prepared[0]
    gap = float(best_semantic["semantic_score"]) - float(first["semantic_score"])
    if gap <= _RELEVANCE_GAP_GUARD or best_semantic is first:
        return prepared
    return [best_semantic, *(row for row in prepared if row is not best_semantic)]


def select_proposals(
    candidates: list[dict[str, Any]],
    *,
    minimum: int = 2,
    target_aspect: float = 9 / 16,
    taste: TasteContext | None = None,
    visual_route: str | None = None,
) -> dict[str, Any]:
    """Return A/B/(C) proposals with explicit score components.

    Semantic relevance stays dominant. The requested evidence route can decide
    close calls ahead of crop convenience, Taste can refine close calls, and a
    >20-point semantic gap always restores the strongest relevant candidate to A.
    """

    if minimum < 1:
        raise ValueError("minimum proposals must be positive")
    if target_aspect <= 0:
        raise ValueError("target aspect must be positive")

    prepared = [
        proposal
        for proposal in (
            _proposal_row(
                row,
                target_aspect,
                taste=taste,
                visual_route=visual_route,
            )
            for row in candidates
        )
        if proposal["crop_usable"]
    ]
    prepared.sort(key=lambda row: (-float(row["final_score"]), str(row.get("id", ""))))
    prepared = _apply_relevance_gap_guard(prepared)

    chosen: list[dict[str, Any]] = []
    for row in prepared:
        if not chosen or _distinct(row, chosen):
            chosen.append(row)
        if len(chosen) >= 3:
            break

    proposal_a = chosen[0] if chosen else None
    proposal_b = chosen[1] if len(chosen) > 1 else None
    proposal_c = chosen[2] if len(chosen) > 2 else None

    if proposal_a is None:
        review_state = "NO_VISUAL_FOUND"
    elif len(chosen) < minimum:
        review_state = "SINGLE_PROPOSAL" if len(chosen) == 1 else "INSUFFICIENT_PROPOSALS"
    else:
        review_state = "READY"

    return {
        "proposal_A": proposal_a,
        "proposal_B": proposal_b,
        "proposal_C": proposal_c,
        "review_state": review_state,
        "usable_candidate_count": len(prepared),
        "minimum_proposals": minimum,
    }
