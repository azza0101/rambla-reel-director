"""Deterministic semantic-only versus evidence-first selection comparison."""

from __future__ import annotations

from statistics import mean
from typing import Any, Mapping, Sequence

from .proposals import select_proposals


def _selected(proposals: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [proposals[key] for key in ("proposal_A", "proposal_B")
            if isinstance(proposals.get(key), dict)]


def compare_editorial_to_semantic(slots: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rows = []
    all_selected = []
    two = 0
    floor = 0
    duplicate = 0
    for slot in slots:
        candidates = list(slot["candidates"])
        baseline = sorted(candidates, key=lambda row: (-float(row.get("score", 0)), str(row.get("id", ""))))[:2]
        editorial = select_proposals(candidates, minimum=2, taste=slot["taste"],
                                     evidence_intent=slot["intent"])
        selected = _selected(editorial)
        all_selected.extend(selected)
        two += int(len(selected) >= 2)
        floor += int(editorial["review_state"] == "NO_BROLL_QUALITY_FLOOR")
        duplicate += int(len(selected) > 1 and (
            selected[0].get("provider_id") == selected[1].get("provider_id")
            or (bool(selected[0].get("motif_id")) and selected[0].get("motif_id") == selected[1].get("motif_id"))
        ))
        rows.append({
            "slot_id": slot.get("id"),
            "baseline_ids": [row["id"] for row in baseline],
            "editorial_ids": [row["id"] for row in selected],
            "rejected_ids": [row["id"] for row in editorial.get("rejected_candidates", [])],
            "review_state": editorial["review_state"],
        })
    count = len(all_selected)
    exact = sum(str(row.get("source_class", "")).startswith("EXACT_")
                or row.get("source_class") == "SOURCE_NATIVE_SOCIAL" for row in all_selected)
    return {
        "slot_count": len(slots),
        "slots_with_two_eligible_proposals": two,
        "quality_floor_no_broll_rate": round(floor / len(slots), 4) if slots else 0.0,
        "mean_evidence_specificity_selected": round(mean(float(row["evidence_specificity"]) for row in all_selected), 4) if count else 0.0,
        "mean_editorial_quality_selected": round(mean(float(row["editorial_quality"]) for row in all_selected), 4) if count else 0.0,
        "generic_stock_selection_rate": round(sum(row.get("source_class") == "GENERIC_STOCK" for row in all_selected) / count, 4) if count else 0.0,
        "duplicate_source_or_motif_rate": round(duplicate / len(slots), 4) if slots else 0.0,
        "exact_or_source_native_selection_rate": round(exact / count, 4) if count else 0.0,
        "baseline_vs_editorial": rows,
        "resolve_calls": 0,
    }
