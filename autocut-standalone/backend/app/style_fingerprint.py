"""Pure timing and visual-state aggregation for one reference reel."""

from __future__ import annotations

import math
import statistics
from dataclasses import asdict, dataclass, field
from typing import Mapping, Sequence

from .taste_profile import ReferenceStyleProfile


@dataclass(frozen=True)
class VisualInterval:
    start_seconds: float
    end_seconds: float
    route: str
    presentation: str
    media_kind: str = "video"
    classification_confidence: float = 1.0

    def __post_init__(self) -> None:
        if (not math.isfinite(self.start_seconds) or not math.isfinite(self.end_seconds)
                or self.start_seconds < 0 or self.end_seconds <= self.start_seconds):
            raise ValueError("invalid visual interval timing")
        if not self.route or not self.presentation:
            raise ValueError("visual interval requires route and presentation")
        if not 0 <= self.classification_confidence <= 1:
            raise ValueError("classification confidence must be between 0 and 1")


@dataclass(frozen=True)
class StyleFingerprint:
    id: str
    duration_seconds: float
    visual_change_count: int
    cuts_per_minute: float
    insert_count: int
    mean_insert_seconds: float
    median_insert_seconds: float
    speaker_persistence: float
    coverage_density: float
    speaker_return_count: int
    speaker_return_intervals: tuple[float, ...]
    route_mix: Mapping[str, float]
    presentation_mix: Mapping[str, float]
    still_video_ratio: float
    hook_density: float
    body_density: float
    end_density: float
    source_native_overlay_tolerance: float
    classification_confidence_mean: float
    intervals: tuple[VisualInterval, ...] = field(repr=False)

    def to_reference_style_profile(self) -> ReferenceStyleProfile:
        if any(row.route == "UNCLASSIFIED" for row in self.intervals):
            raise ValueError("unclassified intervals cannot become an active reference style")
        return ReferenceStyleProfile(
            id=self.id, speaker_persistence=self.speaker_persistence,
            coverage_density=self.coverage_density,
            median_insert_seconds=self.median_insert_seconds,
            route_mix=self.route_mix, presentation_mix=self.presentation_mix,
        )

    def to_dict(self) -> dict:
        return asdict(self)


def _density(intervals: Sequence[VisualInterval], start: float, end: float) -> float:
    if end <= start:
        return 0.0
    covered = sum(
        max(0.0, min(end, row.end_seconds) - max(start, row.start_seconds))
        for row in intervals if row.route != "TALKING_HEAD"
    )
    return round(covered / (end - start), 4)


def build_style_fingerprint(
    *, exemplar_id: str, duration_seconds: float,
    intervals: Sequence[VisualInterval],
) -> StyleFingerprint:
    if not exemplar_id or not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise ValueError("fingerprint requires id and positive duration")
    rows = tuple(intervals)
    if not rows or abs(rows[0].start_seconds) > 1e-3 or abs(rows[-1].end_seconds - duration_seconds) > 1e-3:
        raise ValueError("visual intervals must be contiguous and span source")
    if any(abs(left.end_seconds - right.start_seconds) > 1e-3 for left, right in zip(rows, rows[1:])):
        raise ValueError("visual intervals must be contiguous and non-overlapping")
    inserts = tuple(row for row in rows if row.route != "TALKING_HEAD")
    lengths = [row.end_seconds - row.start_seconds for row in inserts]
    insert_duration = sum(lengths)
    route_mix: dict[str, float] = {}
    presentation_mix: dict[str, float] = {}
    for row in inserts:
        length = row.end_seconds - row.start_seconds
        route_mix[row.route] = route_mix.get(row.route, 0.0) + length
        presentation_mix[row.presentation] = presentation_mix.get(row.presentation, 0.0) + length
    route_mix = {key: round(value / insert_duration, 4) for key, value in route_mix.items()} if insert_duration else {}
    presentation_mix = {key: round(value / insert_duration, 4) for key, value in presentation_mix.items()} if insert_duration else {}
    returns = tuple(
        row.end_seconds - row.start_seconds for previous, row in zip(rows, rows[1:])
        if previous.route != "TALKING_HEAD" and row.route == "TALKING_HEAD"
    )
    still = sum(row.end_seconds - row.start_seconds for row in inserts if row.media_kind in {"still", "document", "image"})
    video = insert_duration - still
    third = duration_seconds / 3
    return StyleFingerprint(
        id=exemplar_id, duration_seconds=duration_seconds,
        visual_change_count=len(rows) - 1,
        cuts_per_minute=round((len(rows) - 1) * 60 / duration_seconds, 4),
        insert_count=len(inserts),
        mean_insert_seconds=round(statistics.mean(lengths), 4) if lengths else 0.0,
        median_insert_seconds=round(statistics.median(lengths), 4) if lengths else duration_seconds,
        speaker_persistence=round(1 - insert_duration / duration_seconds, 4),
        coverage_density=round(insert_duration / duration_seconds, 4),
        speaker_return_count=len(returns), speaker_return_intervals=returns,
        route_mix=route_mix, presentation_mix=presentation_mix,
        still_video_ratio=round(still / video, 4) if video else (1.0 if still else 0.0),
        hook_density=_density(rows, 0.0, third),
        body_density=_density(rows, third, 2 * third),
        end_density=_density(rows, 2 * third, duration_seconds),
        source_native_overlay_tolerance=round(
            sum(row.classification_confidence for row in inserts if row.route == "SOURCE_NATIVE_SOCIAL")
            / max(1, len(inserts)), 4,
        ),
        classification_confidence_mean=round(statistics.mean(row.classification_confidence for row in rows), 4),
        intervals=rows,
    )
