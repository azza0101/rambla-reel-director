"""Deterministic short coverage-slot planning for evidence-first reels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CoverageSlot:
    id: str
    beat_id: str
    start_seconds: float
    end_seconds: float
    visual_intent: str
    queries: tuple[str, ...]
    evidence_class: str
    minimum_proposals: int = 2

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds


def _centered_window(start: float, end: float, target: float) -> tuple[float, float]:
    duration = end - start
    if duration <= target:
        return start, end
    center = (start + end) / 2.0
    half = target / 2.0
    return center - half, center + half


def plan_coverage_slots(
    beats: list[dict[str, Any]],
    *,
    target_seconds: float = 3.5,
    min_seconds: float = 2.5,
    max_seconds: float = 4.5,
    min_gap_seconds: float = 1.0,
) -> list[CoverageSlot]:
    """Create short visual coverage windows without covering full long beats.

    Beats without visual queries remain talking-head.  A normal eligible beat
    gets one centered window.  A beat longer than two target windows plus the
    configured gap may receive two separated windows so a long explanation can
    return to the speaker between inserts.
    """

    if not (0 < min_seconds <= target_seconds <= max_seconds):
        raise ValueError("coverage duration bounds are invalid")
    if min_gap_seconds < 0:
        raise ValueError("minimum gap must be non-negative")

    slots: list[CoverageSlot] = []
    for beat in beats:
        beat_id = str(beat.get("id") or "").strip()
        if not beat_id:
            raise ValueError("coverage beat id is required")
        start = float(beat["start_seconds"])
        end = float(beat["end_seconds"])
        if start < 0 or end <= start:
            raise ValueError("coverage beat timing is invalid")

        queries = tuple(
            value.strip()
            for value in beat.get("broll_queries", [])
            if isinstance(value, str) and value.strip()
        )
        if not queries:
            continue

        intent = str(beat.get("intent") or queries[0]).strip()
        duration = end - start
        windows: list[tuple[float, float]]

        if duration > 2 * target_seconds + min_gap_seconds:
            edge_padding = min_gap_seconds / 2.0
            first_start = start + edge_padding
            first_end = min(first_start + target_seconds, end)
            second_end = end - edge_padding
            second_start = max(start, second_end - target_seconds)
            if first_end + min_gap_seconds <= second_start:
                windows = [(first_start, first_end), (second_start, second_end)]
            else:
                windows = [_centered_window(start, end, target_seconds)]
        else:
            windows = [_centered_window(start, end, target_seconds)]

        for index, (slot_start, slot_end) in enumerate(windows, start=1):
            slots.append(
                CoverageSlot(
                    id=f"{beat_id}:coverage:{index}",
                    beat_id=beat_id,
                    start_seconds=round(slot_start, 4),
                    end_seconds=round(slot_end, 4),
                    visual_intent=intent,
                    queries=queries,
                    evidence_class="exact_or_related_evidence",
                    minimum_proposals=2,
                )
            )

    return slots
