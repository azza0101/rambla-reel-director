"""Validated, global visual preferences stored beside RMBL project data."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .atomic_io import write_json


class ThemePaint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["solid", "gradient"] = "solid"
    color_a: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    color_b: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")


class ThemePreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    canvas: ThemePaint
    sections: dict[str, ThemePaint] = Field(min_length=7, max_length=7)


def default_theme_preferences() -> dict:
    panel = {"mode": "solid", "color_a": "#242743", "color_b": "#20233d"}
    return {
        "canvas": {"mode": "solid", "color_a": "#0b2427", "color_b": "#081b1e"},
        "sections": {str(step): dict(panel) for step in range(1, 8)},
    }


def validate_theme_preferences(payload) -> ThemePreferences:
    validated = ThemePreferences.model_validate(payload)
    if set(validated.sections) != {str(step) for step in range(1, 8)}:
        raise ValueError("theme sections must contain exactly 1 through 7")
    return validated


def load_theme_preferences(path: Path) -> dict:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return validate_theme_preferences(payload).model_dump()
    except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
        return default_theme_preferences()


def save_theme_preferences(path: Path, preferences: ThemePreferences) -> dict:
    payload = preferences.model_dump()
    write_json(Path(path), payload)
    return payload
