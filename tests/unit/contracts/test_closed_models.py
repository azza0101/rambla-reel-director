import pytest
from pydantic import TypeAdapter, ValidationError

from backend.app.contracts.apply import ApplyOperation
from backend.app.contracts.common import FrameRange, Timebase, UtcTimestamp
from backend.app.contracts.errors import TypedError
from backend.app.contracts.plans import EditDecision


def test_typed_error_rejects_unknown_fields() -> None:
    """Removing closed-model validation would silently accept unsafe payload data."""
    with pytest.raises(ValidationError, match="unexpected"):
        TypedError(
            schema_version="1.0",
            code="X",
            category="INTERNAL",
            retryable=False,
            message="x",
            diagnostic_id="00000000-0000-0000-0000-000000000001",
            details=None,
            unexpected=True,
        )


def test_frame_range_requires_a_positive_half_open_interval() -> None:
    """Changing the interval guard would allow zero-length timeline edits."""
    with pytest.raises(ValidationError):
        FrameRange(start_frame=12, end_frame=12)


def test_timebase_requires_a_reduced_positive_rational() -> None:
    """Removing rational normalization would make equivalent timebases unstable."""
    with pytest.raises(ValidationError):
        Timebase(num=48, den=2, drop_frame=False, start_timecode="01:00:00:00")


def test_punch_in_requires_range_and_rejects_frame() -> None:
    """Changing action placement rules would permit an invalid PUNCH_IN placement."""
    with pytest.raises(ValidationError):
        EditDecision(
            id="00000000-0000-0000-0000-000000000002",
            action="PUNCH_IN",
            range={"start_frame": 5, "end_frame": 20},
            frame=5,
            intent="Add emphasis",
            reason="The delivery peaks here",
            confidence=0.9,
            queries=[],
            candidate_refs=[],
            selected_asset_ref=None,
            parameters={
                "scale": 1.1,
                "anchor_x": 0.5,
                "anchor_y": 0.5,
                "easing": "CUT",
            },
            review_state="PROPOSED",
            provenance={"source_kind": "MANUAL", "source_id": "fixture"},
        )


def test_caption_emphasis_requires_canonical_alignment_word_ids() -> None:
    """Weakening word IDs to arbitrary strings would break alignment provenance."""
    with pytest.raises(ValidationError):
        EditDecision(
            id="00000000-0000-0000-0000-000000000003",
            action="CAPTION_EMPHASIS",
            range={"start_frame": 5, "end_frame": 20},
            frame=None,
            intent="Emphasize the keyword",
            reason="It is the editorial point",
            confidence=0.9,
            queries=[],
            candidate_refs=[],
            selected_asset_ref=None,
            parameters={
                "style_token": "keyword",
                "emphasis": "COLOR",
                "keyword_text": "point",
                "alignment_word_ids": ["NOT-A-UUID"],
            },
            review_state="PROPOSED",
            provenance={"source_kind": "MANUAL", "source_id": "fixture"},
        )


def _apply_operation(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": "1.0",
        "id": "00000000-0000-0000-0000-000000000010",
        "apply_attempt_id": "00000000-0000-0000-0000-000000000011",
        "plan_id": "00000000-0000-0000-0000-000000000012",
        "decision_id": None,
        "kind": "DUPLICATE_TIMELINE",
        "target_identity": None,
        "precondition": {"kind": "SOURCE_UNCHANGED", "expected_hash": "sha256:" + "a" * 64},
        "payload": {"source_timeline_name": "REEL_MASTER", "target_timeline_name": "REEL_AI_v01"},
        "expected_postcondition": {"kind": "TARGET_EXISTS", "expected_hash": None},
    }
    value.update(overrides)
    return value


def test_apply_operation_payload_is_closed() -> None:
    payload = _apply_operation()["payload"]
    assert isinstance(payload, dict)
    payload["unexpected"] = True

    with pytest.raises(ValidationError, match="unexpected"):
        ApplyOperation.model_validate(_apply_operation(payload=payload))


def test_apply_operation_payload_must_match_kind() -> None:
    with pytest.raises(ValidationError, match="payload must match kind"):
        ApplyOperation.model_validate(
            _apply_operation(
                payload={
                    "range": {"start_frame": 10, "end_frame": 20},
                    "scale": 1.1,
                    "anchor_x": 0.5,
                    "anchor_y": 0.5,
                    "easing": "CUT",
                }
            )
        )


def test_timestamp_rejects_impossible_calendar_values() -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(UtcTimestamp).validate_python("2026-99-99T99:99:99Z")


def test_json_details_reject_non_json_and_non_finite_values() -> None:
    for details in ({"opaque": object()}, {"infinite": float("inf")}, {"nan": float("nan")}):
        with pytest.raises(ValidationError):
            TypedError(
                schema_version="1.0",
                code="X",
                category="INTERNAL",
                retryable=False,
                message="x",
                diagnostic_id="00000000-0000-0000-0000-000000000001",
                details=details,
            )
