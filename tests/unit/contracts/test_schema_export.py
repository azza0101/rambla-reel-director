import json
from pathlib import Path

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
