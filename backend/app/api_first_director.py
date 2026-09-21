"""APP REEL V5 text-first editorial director."""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Protocol

from .editorial_import import VERSION, validate_import
from .gemini_interactions import GeminiJSONReply


DIRECTOR_SCHEMA_VERSION = "rambla-api-first-director-1"

DIRECTOR_INSTRUCTIONS = """You are the editorial B-roll director for a fast-paced short-form reel.

Understand the ENTIRE spoken reel first: topic, tone, jokes, references, setup/payoff
and what each sentence means in context. Only then group adjacent transcript chunks
into visual beats. The source video is deliberately unavailable. Base editorial meaning
only on the spoken transcript.

Cover every transcript chunk exactly once and in order. Prefer dense short-form visual
coverage when concrete retrievable visuals exist. KEEP_TALKING_HEAD is deliberate for
intro, CTA, delivery-critical punchline, or moments where B-roll would weaken the idea.
CONTINUE_PREVIOUS_VISUAL means the previous visual stays useful and needs no new shots.

Current spoken meaning is authoritative. Neighboring chunks may resolve references but
must not add unrelated objects or claims. Prefer literal physical subjects and actions
that can actually be found online. Avoid generic laptop, map, hotel-room, office-stock,
presenter, infographic, or symbolic filler unless the speech is really about it. Prefer
candid phone-native real-world actions suitable for Shorts/Reels/TikTok. Avoid repeating
the same visual idea across the reel.

Prefer one strong retrievable shot. Use 2-3 only for a real sequence or juxtaposition.
Queries must be simple concrete English search phrases of 2-10 words. Produce 1-3 image
queries and 1-3 video queries per shot. Put likely false positives and unwanted shortcuts
in avoid. Output only the structured object requested by the schema.
"""


def director_schema() -> dict[str, Any]:
    string = {"type": "string", "minLength": 1}
    query_list = {"type": "array", "items": string, "minItems": 1, "maxItems": 3}
    shot = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "description": string,
            "image_queries": query_list,
            "video_queries": query_list,
        },
        "required": ["description", "image_queries", "video_queries"],
    }
    beat = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "first_chunk_id": string,
            "last_chunk_id": string,
            "action": {"type": "string", "enum": ["BROLL", "KEEP_TALKING_HEAD", "CONTINUE_PREVIOUS_VISUAL"]},
            "editorial_function": string,
            "core_meaning": string,
            "subtext": {"type": "string"},
            "visual_mode": {"type": "string", "enum": ["single", "sequence", "juxtaposition"]},
            "shots": {"type": "array", "items": shot, "maxItems": 3},
            "avoid": {"type": "array", "items": string, "maxItems": 8},
        },
        "required": [
            "first_chunk_id", "last_chunk_id", "action", "editorial_function",
            "core_meaning", "subtext", "visual_mode", "shots", "avoid",
        ],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "global_topic": string,
            "beats": {"type": "array", "items": beat, "minItems": 1},
        },
        "required": ["global_topic", "beats"],
    }


def _compact_chunk_ledger(package: dict[str, Any]) -> str:
    rows = [
        {
            "id": str(chunk["id"]),
            "start": round(float(chunk["start"]), 3),
            "end": round(float(chunk["end"]), 3),
            "text": str(chunk["text"]),
        }
        for chunk in package["chunks"]
    ]
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))


def build_director_prompt(package: dict[str, Any]) -> str:
    return (
        DIRECTOR_INSTRUCTIONS
        + "\nRead all chronological chunks before deciding beats. "
        + "Use first_chunk_id and last_chunk_id for each contiguous beat. "
        + "The first beat starts at the first chunk, the last beat ends at the last chunk, "
        + "and adjacent beats meet with no gaps or overlap. "
        + "For BROLL: single means exactly 1 shot; sequence/juxtaposition means 2-3 shots. "
        + "For KEEP_TALKING_HEAD and CONTINUE_PREVIOUS_VISUAL: shots must be empty.\n"
        + "TRANSCRIPT_CHUNKS="
        + _compact_chunk_ledger(package)
    )


def _clean_text(value: Any, *, allow_empty: bool = False) -> str:
    clean = " ".join(str(value or "").split())
    if not clean and not allow_empty:
        raise ValueError("empty text field")
    return clean


def _queries(values: Any, path: str) -> list[str]:
    if not isinstance(values, list) or not 1 <= len(values) <= 3:
        raise ValueError(f"{path}: expected 1-3 queries")
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        query = _clean_text(value)
        if not 2 <= len(query.split()) <= 10:
            raise ValueError(f"{path}: queries must contain 2-10 words")
        key = query.casefold()
        if key in seen:
            raise ValueError(f"{path}: duplicate query")
        seen.add(key)
        out.append(query)
    return out
