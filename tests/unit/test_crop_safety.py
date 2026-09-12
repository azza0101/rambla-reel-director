from __future__ import annotations

import pytest

from backend.app.crop_safety import evaluate_static_crop


def test_landscape_can_survive_center_9x16_crop() -> None:
    result = evaluate_static_crop(1920, 1080)

    assert result.usable is True
    assert 0.0 < result.score < 1.0
    assert result.crop_box[2] - result.crop_box[0] < 1.0
    assert result.crop_box[1] == 0.0
    assert result.crop_box[3] == 1.0
    assert result.needs_tracking is True


def test_native_9x16_is_high_confidence() -> None:
    result = evaluate_static_crop(1080, 1920)

    assert result.usable is True
    assert result.score >= 0.95
    assert result.crop_box == pytest.approx((0.0, 0.0, 1.0, 1.0))
    assert result.needs_tracking is False


def test_square_is_usable_but_needs_reframing() -> None:
    result = evaluate_static_crop(1080, 1080)

    assert result.usable is True
    assert 0.5 < result.score < 0.7
    assert result.needs_tracking is True


def test_invalid_geometry_is_rejected() -> None:
    with pytest.raises(ValueError, match="positive source geometry"):
        evaluate_static_crop(0, 1080)
