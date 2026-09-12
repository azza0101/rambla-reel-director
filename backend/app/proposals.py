"""Editorial proposal selection after semantic ranking.

Qwen remains responsible for semantic similarity. This module adds cheap
presentation constraints (crop feasibility), bounded Taste compatibility, and
diversity so review surfaces receive meaningful A/B alternatives rather than
one opaque winner.
"""

from __future__ import annotations

from typing import Any

from .crop_safety import evaluate_static_crop
from .taste_profile import TasteContext


_RELEVANCE_GAP_GUARD = 0.20


def _taste_score(
    row: dict[str, Any],
    taste: TasteContext | None,
    visual_route: str | None,
) -> tuple[float, dict[str, float]]:
    if taste is None:
        return 0.5, {"route_match": 0.5, "trusted_source": 0.5}

    row_route = str(row.get("route") or "")
    route_match = (
        1.0
        if visual_route and row_route == visual_route
        else float(taste.route_weights.get(row_route, 0.5))
    )
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
    taste_score, taste_components = _taste_score(result, taste, visual_route)
    result["taste_score"] = taste_score
    result["taste_components"] = taste_components
    result["final_score"] = round(
        0.72 * semantic_score + 0.18 * assessment.score + 0.10 * taste_score,
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
    """Keep Taste/crop as tie-breakers, never as a large relevance override."""

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
    """Return A/B/(C) review proposals with crop- and Taste-aware scores.

    Semantic relevance remains dominant. Taste can reorder close candidates,
    but a >20-point semantic gap restores the strongest relevant candidate to A.
    Proposal B/C must be meaningfully distinct by source identity and preview
    content hash when that evidence is available.
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
