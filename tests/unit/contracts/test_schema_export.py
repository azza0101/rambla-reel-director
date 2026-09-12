import json
from pathlib import Path

import jsonschema
import pytest

from backend.app.contracts.schema_export import TOP_LEVEL_MODELS, export_schemas


def test_schema_export_is_byte_stable_and_closes_top_level_models(tmp_path) -> None:
    """A non-deterministic or open export would make persisted API contracts unsafe."""
    first = export_schemas(tmp_path)
    before = {path.name: path.read_bytes() for path in first}
    second = export_schemas(tmp_path)
    after = {path.name: path.read_bytes() for path in second}

    assert before == after
    assert set(before) == {f"{model.__name__}.schema.json" for model in TOP_LEVEL_MODELS}
    for content in before.values():
        assert json.loads(content)["additionalProperties"] is False


def test_default_schema_export_targets_checked_in_backend_directory() -> None:
    """Changing the default export root would leave required schemas untracked."""
    paths = export_schemas()

    assert {path.parent.resolve() for path in paths} == {Path("backend/schemas/v1").resolve()}


def _read_export(tmp_path: Path, name: str) -> dict[str, object]:
    export_schemas(tmp_path)
    return json.loads((tmp_path / f"{name}.schema.json").read_text(encoding="utf-8"))


def test_exported_apply_schema_rejects_kind_payload_mismatch(tmp_path: Path) -> None:
    schema = _read_export(tmp_path, "ApplyOperation")
    instance = {
        "schema_version": "1.0",
        "id": "00000000-0000-0000-0000-000000000010",
        "apply_attempt_id": "00000000-0000-0000-0000-000000000011",
        "plan_id": "00000000-0000-0000-0000-000000000012",
        "decision_id": None,
        "kind": "DUPLICATE_TIMELINE",
        "target_identity": None,
        "precondition": {"kind": "SOURCE_UNCHANGED", "expected_hash": "sha256:" + "a" * 64},
        "payload": {
            "range": {"start_frame": 10, "end_frame": 20},
            "scale": 1.1,
            "anchor_x": 0.5,
            "anchor_y": 0.5,
            "easing": "CUT",
        },
        "expected_postcondition": {"kind": "TARGET_EXISTS", "expected_hash": None},
    }

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(instance)


def test_exported_decision_schema_rejects_action_parameter_mismatch(tmp_path: Path) -> None:
    schema = _read_export(tmp_path, "EditDecision")
    instance = {
        "id": "00000000-0000-0000-0000-000000000020",
        "action": "PUNCH_IN",
        "range": {"start_frame": 10, "end_frame": 20},
        "frame": None,
        "intent": "emphasis",
        "reason": "beat",
        "confidence": 0.9,
        "queries": [],
        "candidate_refs": [],
        "selected_asset_ref": None,
        "parameters": {
            "fit": "COVER",
            "crop_anchor": "CENTER",
            "custom_anchor": None,
            "source_offset_frame": 0,
            "opacity": 1,
        },
        "review_state": "PROPOSED",
        "provenance": {"source_kind": "MANUAL", "source_id": "fixture"},
    }

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(instance)


def test_named_nested_contract_records_are_closed(tmp_path: Path) -> None:
    expected_defs = {
        "StepLease",
        "EditControls",
        "ProviderTrace",
        "PlanValidation",
        "ProvenanceRecord",
        "SourceTimelineIdentity",
        "TargetTimelineIdentity",
        "PreflightResult",
        "OperationJournalEntry",
        "VerificationResult",
        "OperationCondition",
    }
    schemas = {
        name: _read_export(tmp_path, name)
        for name in ("Run", "EditPlan", "ApplyOperation", "ApplyReport")
    }
    definitions = {
        key: value
        for schema in schemas.values()
        for key, value in schema.get("$defs", {}).items()
    }

    assert expected_defs <= definitions.keys()
    for name in expected_defs:
        assert definitions[name]["additionalProperties"] is False, name
