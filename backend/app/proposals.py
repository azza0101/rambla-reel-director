"""Editorial proposal selection after semantic ranking.

Qwen remains responsible for semantic similarity.  This module adds cheap
presentation constraints (crop feasibility) and diversity so review surfaces
receive meaningful A/B alternatives rather than one opaque winner.
"""

from __future__ import annotations

from typing import Any

from .crop_safety import evaluate_static_crop


def _proposal_row(row: dict[str, Any], target_aspect: float) -> dict[str, Any]:
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
    result["final_score"] = round(0.8 * semantic_score + 0.2 * assessment.score, 4)
    return result


def _distinct(candidate: dict[str, Any], selected: list[dict[str, Any]]) -> bool:
    identity = (str(candidate.get("source", "")), str(candidate.get("provider_id", candidate.get("id", ""))))
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


def select_proposals(
    candidates: list[dict[str, Any]],
    *,
    minimum: int = 2,
    target_aspect: float = 9 / 16,
) -> dict[str, Any]:
    """Return A/B/(C) review proposals with crop-aware final scores.

    Unusable extreme crops are dropped.  Proposal B/C must be meaningfully
    distinct by source identity and preview content hash when that evidence is
    available.
    """

    if minimum < 1:
        raise ValueError("minimum proposals must be positive")
    if target_aspect <= 0:
        raise ValueError("target aspect must be positive")

    prepared = [
        proposal
        for proposal in (_proposal_row(row, target_aspect) for row in candidates)
        if proposal["crop_usable"]
    ]
    prepared.sort(key=lambda row: (-float(row["final_score"]), str(row.get("id", ""))))

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
