"""Deterministic checked-in JSON Schema export for frozen v1 models."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from .apply import ApplyOperation, ApplyReport
from .errors import TypedError
from .plans import EditDecision, EditPlan
from .runs import Run

TOP_LEVEL_MODELS: tuple[type[BaseModel], ...] = (
    TypedError,
    Run,
    EditDecision,
    EditPlan,
    ApplyOperation,
    ApplyReport,
)

_DISCRIMINATED_FIELDS = {
    "EditDecision": (
        "action",
        "parameters",
        {
            "BROLL": "BrollParameters",
            "EDITORIAL_INSERT": "EditorialInsertParameters",
            "PUNCH_IN": "PunchInParameters",
            "STICKER": "StickerParameters",
            "CAPTION_EMPHASIS": "CaptionEmphasisParameters",
        },
    ),
    "ApplyOperation": (
        "kind",
        "payload",
        {
            "DUPLICATE_TIMELINE": "DuplicateTimelinePayload",
            "IMPORT_ASSET": "ImportAssetPayload",
            "PLACE_MEDIA": "PlaceMediaPayload",
            "SET_TRANSFORM": "SetTransformPayload",
            "PLACE_OVERLAY": "PlaceOverlayPayload",
            "APPLY_CAPTION_EMPHASIS": "ApplyCaptionEmphasisPayload",
            "VERIFY": "VerifyPayload",
            "DISCARD_GENERATED_TIMELINE": "DiscardGeneratedTimelinePayload",
        },
    ),
}


def _close_discriminator_coupling(model_name: str, schema: dict[str, object]) -> None:
    coupling = _DISCRIMINATED_FIELDS.get(model_name)
    if coupling is None:
        return
    discriminator, value_field, variants = coupling
    schema["allOf"] = [
        {
            "if": {
                "properties": {discriminator: {"const": discriminator_value}},
                "required": [discriminator],
            },
            "then": {
                "properties": {
                    value_field: {"$ref": f"#/$defs/{definition_name}"}
                }
            },
        }
        for discriminator_value, definition_name in variants.items()
    ]


def export_schemas(destination: Path | None = None) -> list[Path]:
    """Write sorted UTF-8 schemas to the v1 schema directory and return paths."""
    output_dir = destination or Path(__file__).resolve().parents[2] / "schemas" / "v1"
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for model in TOP_LEVEL_MODELS:
        schema = model.model_json_schema()
        _close_discriminator_coupling(model.__name__, schema)
        payload = json.dumps(
            schema, ensure_ascii=False, indent=2, sort_keys=True
        ) + "\n"
        path = output_dir / f"{model.__name__}.schema.json"
        path.write_text(payload, encoding="utf-8", newline="\n")
        paths.append(path)
    return paths


if __name__ == "__main__":
    export_schemas()
