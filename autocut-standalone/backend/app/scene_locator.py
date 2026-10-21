"""Coarse-to-fine scene-window selection from lightweight evidence.

This module deliberately contains no downloader.  Callers can feed transcript
snippets, storyboard frames, preview-frame scores, or other cheap evidence and
receive a small set of short source windows to acquire later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class SceneEvidence:
    timestamp_seconds: float
    text: str
    image_path: str | None
    metadata_score: float


@dataclass(frozen=True, slots=True)
class SceneWindow:
    start_seconds: float
    end_seconds: float
    score: float
    evidence_timestamps: tuple[float, ...]


ScoreFn = Callable[[str, SceneEvidence], float]


def _effective_score(query: str, row: SceneEvidence, score_fn: ScoreFn | None) -> float:
    metadata = float(row.metadata_score)
    if not 0.0 <= metadata <= 1.0:
        raise ValueError("scene evidence score must be between 0 and 1")
    if score_fn is None:
        return metadata
    similarity = float(score_fn(query, row))
    similarity = max(0.0, min(1.0, similarity))
    return max(0.0, min(1.0, 0.7 * metadata + 0.3 * similarity))


def _window(center: float, duration: float, source_duration: float) -> tuple[float, float]:
    duration = min(duration, source_duration)
    start = center - duration / 2.0
    end = start + duration
    if start < 0:
        start = 0.0
        end = duration
    if end > source_duration:
        end = source_duration
        start = source_duration - duration
    return round(start, 4), round(end, 4)


def _overlaps(left: SceneWindow, right: SceneWindow) -> bool:
    return left.start_seconds < right.end_seconds and right.start_seconds < left.end_seconds


def locate_windows(
    query: str,
    evidence: list[SceneEvidence],
    *,
    target_seconds: float = 3.5,
    source_duration: float,
    score_fn: ScoreFn | None = None,
    cluster_gap_seconds: float = 8.0,
    limit: int = 3,
) -> list[SceneWindow]:
    """Rank short source windows around promising lightweight evidence.

    Evidence samples that sit within ``cluster_gap_seconds`` of each other are
    treated as support for the same coarse scene region.  A small support bonus
    rewards corroborated regions without allowing sample count to swamp
    relevance.  Returned windows stay score-ranked and non-overlapping.
    """

    if source_duration <= 0:
        raise ValueError("source duration must be positive")
    if target_seconds <= 0:
        raise ValueError("target seconds must be positive")
    if cluster_gap_seconds <= 0:
        raise ValueError("cluster gap must be positive")
    if limit <= 0:
        raise ValueError("limit must be positive")
    if not evidence:
        return []

    scored: list[tuple[SceneEvidence, float]] = []
    for row in evidence:
        timestamp = float(row.timestamp_seconds)
        if not 0.0 <= timestamp <= source_duration:
            raise ValueError("scene evidence timestamp is outside source")
        scored.append((row, _effective_score(query, row, score_fn)))
    scored.sort(key=lambda item: (item[0].timestamp_seconds, -item[1]))

    clusters: list[list[tuple[SceneEvidence, float]]] = []
    current: list[tuple[SceneEvidence, float]] = []
    for item in scored:
        if not current:
            current = [item]
            continue
        previous_timestamp = float(current[-1][0].timestamp_seconds)
        if float(item[0].timestamp_seconds) - previous_timestamp <= cluster_gap_seconds:
            current.append(item)
        else:
            clusters.append(current)
            current = [item]
    if current:
        clusters.append(current)

    candidates: list[SceneWindow] = []
    for cluster in clusters:
        weights = [max(score, 0.001) for _, score in cluster]
        weight_sum = sum(weights)
        center = sum(float(row.timestamp_seconds) * weight for (row, _), weight in zip(cluster, weights)) / weight_sum
        best = max(score for _, score in cluster)
        support_bonus = 0.1 * max(0, len(cluster) - 1)
        score = round(min(1.0, best + support_bonus), 4)
        start, end = _window(center, target_seconds, source_duration)
        candidates.append(
            SceneWindow(
                start_seconds=start,
                end_seconds=end,
                score=score,
                evidence_timestamps=tuple(float(row.timestamp_seconds) for row, _ in cluster),
            )
        )

    candidates.sort(key=lambda row: (-row.score, row.start_seconds, row.end_seconds))
    selected: list[SceneWindow] = []
    for candidate in candidates:
        if any(_overlaps(candidate, existing) for existing in selected):
            continue
        selected.append(candidate)
        if len(selected) >= limit:
            break
    return selected
