from __future__ import annotations

from backend.app.coverage import plan_coverage_slots


def test_long_beat_gets_short_slot_not_full_beat() -> None:
    beats = [
        {
            "id": "b1",
            "start_seconds": 10.0,
            "end_seconds": 18.0,
            "intent": "show named event",
            "broll_queries": ["named event"],
        }
    ]

    slots = plan_coverage_slots(beats)

    assert len(slots) == 1
    assert 2.5 <= slots[0].end_seconds - slots[0].start_seconds <= 4.5
    assert slots[0].start_seconds >= 10.0
    assert slots[0].end_seconds <= 18.0
    assert slots[0].minimum_proposals == 2


def test_short_beat_is_not_extended_outside_beat() -> None:
    beats = [
        {
            "id": "b1",
            "start_seconds": 2.0,
            "end_seconds": 4.0,
            "intent": "show source",
            "broll_queries": ["source"],
        }
    ]

    slots = plan_coverage_slots(beats)

    assert slots[0].start_seconds == 2.0
    assert slots[0].end_seconds == 4.0


def test_beat_without_visual_query_stays_talking_head() -> None:
    beats = [
        {
            "id": "b1",
            "start_seconds": 0.0,
            "end_seconds": 5.0,
            "intent": "speaker setup",
            "broll_queries": [],
        }
    ]

    assert plan_coverage_slots(beats) == []


def test_very_long_beat_can_receive_two_separated_slots() -> None:
    beats = [
        {
            "id": "b1",
            "start_seconds": 0.0,
            "end_seconds": 12.0,
            "intent": "two evidence moments",
            "broll_queries": ["first evidence", "second evidence"],
        }
    ]

    slots = plan_coverage_slots(beats)

    assert len(slots) == 2
    assert slots[0].end_seconds <= slots[1].start_seconds
    assert all(2.5 <= slot.end_seconds - slot.start_seconds <= 4.5 for slot in slots)
