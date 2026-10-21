"""Fast geometry-only crop feasibility for mixed-aspect evidence media.

This intentionally does not pretend to know where the visual subject is.  It
provides a cheap first-pass score and a normalized center-crop box; a later
vision/tracking pass can replace or refine the assessment without changing the
consumer contract.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CropAssessment:
    score: float
    crop_box: tuple[float, float, float, float]
    needs_tracking: bool
    usable: bool
    reason: str


def evaluate_static_crop(
    width: int,
    height: int,
    target_aspect: float = 9 / 16,
) -> CropAssessment:
    """Estimate how much of a frame survives a centered target-aspect crop.

    ``crop_box`` is normalized as ``(left, top, right, bottom)`` in source
    coordinates.  The score is the retained fraction along the cropped axis.
    It is intentionally conservative for landscape material but does not
    reject it outright: landscape footage remains eligible for later subject
    tracking/reframing.
    """

    if width <= 0 or height <= 0 or target_aspect <= 0:
        raise ValueError("positive source geometry and target aspect required")

    source_aspect = width / height
    if source_aspect >= target_aspect:
        normalized_width = target_aspect / source_aspect
        left = (1.0 - normalized_width) / 2.0
        crop = (left, 0.0, left + normalized_width, 1.0)
        retained = normalized_width
    else:
        normalized_height = source_aspect / target_aspect
        top = (1.0 - normalized_height) / 2.0
        crop = (0.0, top, 1.0, top + normalized_height)
        retained = normalized_height

    score = max(0.05, min(1.0, retained))
    return CropAssessment(
        score=round(score, 4),
        crop_box=tuple(round(value, 6) for value in crop),
        needs_tracking=score < 0.75,
        usable=score >= 0.18,
        reason="static center-crop geometry",
    )
