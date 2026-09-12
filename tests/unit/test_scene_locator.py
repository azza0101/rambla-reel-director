from __future__ import annotations

import pytest

from backend.app.scene_locator import SceneEvidence, locate_windows


def test_locator_builds_short_window_around_best_evidence() -> None:
    evidence = [
        SceneEvidence(10, "intro", None, 0.1),
        SceneEvidence(75, "robot factory", None, 0.9),
        SceneEvidence(80, "robot closeup", None, 0.8),
    ]

    windows = locate_windows(
        "industrial robot",
        evidence,
        target_seconds=3.5,
        source_duration=600,
    )

    assert windows
    assert 72 <= windows[0].start_seconds <= 79
    assert 2.5 <= windows[0].end_seconds - windows[0].start_seconds <= 4.5
    assert set(windows[0].evidence_timestamps) == {75.0, 80.0}


def test_locator_clamps_window_at_source_start_and_end() -> None:
    start = locate_windows(
        "hook",
        [SceneEvidence(0.2, "hook", None, 1.0)],
        target_seconds=3.5,
        source_duration=20,
    )[0]
    end = locate_windows(
        "ending",
        [SceneEvidence(19.8, "ending", None, 1.0)],
        target_seconds=3.5,
        source_duration=20,
    )[0]

    assert start.start_seconds == 0.0
    assert start.end_seconds == pytest.approx(3.5)
    assert end.start_seconds == pytest.approx(16.5)
    assert end.end_seconds == 20.0


def test_locator_returns_top_non_overlapping_windows() -> None:
    evidence = [
        SceneEvidence(30, "one", None, 0.9),
        SceneEvidence(32, "one close", None, 0.8),
        SceneEvidence(100, "two", None, 0.85),
        SceneEvidence(180, "three", None, 0.7),
        SceneEvidence(250, "four", None, 0.6),
    ]

    windows = locate_windows("evidence", evidence, target_seconds=3.5, source_duration=300)

    assert len(windows) == 3
    assert all(left.end_seconds <= right.start_seconds or right.end_seconds <= left.start_seconds
               for index, left in enumerate(windows) for right in windows[index + 1:])


def test_locator_can_use_injected_query_similarity() -> None:
    evidence = [
        SceneEvidence(10, "generic", None, 0.5),
        SceneEvidence(50, "named person", None, 0.5),
    ]

    windows = locate_windows(
        "named person",
        evidence,
        target_seconds=3.5,
        source_duration=100,
        score_fn=lambda query, row: 1.0 if query in row.text else 0.0,
    )

    assert 48 <= windows[0].start_seconds <= 51


def test_locator_handles_empty_evidence_and_rejects_bad_timing() -> None:
    assert locate_windows("anything", [], target_seconds=3.5, source_duration=100) == []

    with pytest.raises(ValueError, match="source duration"):
        locate_windows("x", [SceneEvidence(1, "x", None, 1.0)], target_seconds=3.5, source_duration=0)
