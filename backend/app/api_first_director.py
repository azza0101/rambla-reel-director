"""APP REEL V5 text-first editorial director."""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Protocol

from .editorial_import import VERSION, validate_import
from .gemini_interactions import GeminiJSONReply


DIRECTOR_SCHEMA_VERSION = "rambla-api-first-director-2"

DIRECTOR_INSTRUCTIONS = """You are the editorial B-roll director for a fast-paced short-form reel.

Understand the ENTIRE spoken reel first: topic, tone, jokes, references, setup/payoff
and what each sentence means in context. Then make exactly ONE editorial decision for
EACH transcript chunk, in the same order. Do not merge chunks. The source video is
deliberately unavailable. Base editorial meaning only on the spoken transcript.

Cover every transcript chunk exactly once and in order. This is a fast-cut reel: one
transcript chunk equals one visual beat. Never merge chunks. Prefer dense short-form visual
coverage when concrete retrievable visuals exist. KEEP_TALKING_HEAD is deliberate for intro,
CTA, delivery-critical punchline, or moments where B-roll would weaken the idea.
CONTINUE_PREVIOUS_VISUAL means the previous visual stays useful across this chunk and needs
no new shots.

Current spoken meaning is authoritative. Neighboring chunks may resolve references but
must not add unrelated objects or claims. Prefer literal physical subjects and actions
that can actually be found online. Avoid generic laptop, map, hotel-room, office-stock,
presenter, infographic, or symbolic filler unless the speech is really about it. Prefer
candid phone-native real-world actions suitable for Shorts/Reels/TikTok. Avoid repeating
the same visual idea across the reel.

BROLL is NOT a topical explainer search. Never answer an abstract sentence with a video
that merely discusses the same topic. Do not search for essays, explainers, certifications,
criteria, educational slides, talking-head experts, "how to", or generic concept videos.
If the current chunk is abstract and has no truthful camera-visible physical scene, use
CONTINUE_PREVIOUS_VISUAL when the previous visual still works; otherwise KEEP_TALKING_HEAD.
A good B-roll description should sound like something a person could film on a phone:
a visible subject doing a visible action in a real place.

Prefer one strong retrievable shot. Use 2-3 only for a real sequence or juxtaposition.
Queries must be simple concrete English search phrases of 2-10 words describing visible
subjects/actions, not themes or arguments. Prefer "airport shuttle bus departing" over
"sustainable travel choices"; prefer "passengers boarding ferry with luggage" over
"ethical tourism"; prefer "wilted basil plant balcony" over "urban regeneration joke".
Do not use abstract search phrases such as "greenwashing tourism", "sustainable tourism",
"ethical tourism", "responsible tourism", "sustainability explained", "criteria", "how to",
or "tips" unless those exact words/signs are themselves the physical subject being shown.
Produce 1-3 image queries and 1-3 video queries per shot. When using multiple queries,
make them a retrieval ladder for the SAME visible evidence: (1) precise subject, place,
period and event, (2) shorter subject+place, (3) a simple broad query people really use.
For example: "Minya Egypt 1990s jihadist attacks archive", then
"jihadist violence Egypt", then "jihad Egypt". The broad query must remain faithful to
the spoken claim; it is not permission to replace it with generic street or town footage.
When speech makes a factual historical, political, violent or archival claim, search for
literal documentary evidence, contemporary news/archive material, named people, places,
events or institutions. Do not neutralize that claim into calm ambience. Avoid may exclude
graphic injury, reenactments, unrelated wars and wrong geography, but must never ban the
central spoken subject or all news/archive evidence needed to show it.
For location-dependent scenes, retain the place established by the transcript, not
only the current sentence: tourist police in Egypt means "tourist police Egypt",
never American police. A newly spoken location overrides the previous location.
Use short catalog queries with a concrete subject/action and geographic name,
preferably 2-5 words. Never use a country match as a substitute for the subject.
Do not introduce a new concept in query 2 or 3. Put likely false positives and unwanted
shortcuts in avoid. Output only the structured object requested by the schema.
"""


def director_schema(expected_chunk_count: int | None = None) -> dict[str, Any]:
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
            "chunk_id": string,
            "action": {"type": "string", "enum": ["BROLL", "KEEP_TALKING_HEAD", "CONTINUE_PREVIOUS_VISUAL"]},
            "editorial_function": string,
            "core_meaning": string,
            "subtext": {"type": "string"},
            "visual_mode": {"type": "string", "enum": ["single", "sequence", "juxtaposition"]},
            "shots": {"type": "array", "items": shot, "maxItems": 3},
            "avoid": {"type": "array", "items": string, "maxItems": 8},
        },
        "required": [
            "chunk_id", "action", "editorial_function",
            "core_meaning", "subtext", "visual_mode", "shots", "avoid",
        ],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "global_topic": string,
            "beats": {
                "type": "array",
                "items": beat,
                "minItems": expected_chunk_count if expected_chunk_count is not None else 1,
                **({"maxItems": expected_chunk_count} if expected_chunk_count is not None else {}),
            },
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
    coverage = package.get("coverage_selected_chunk_ids")
    coverage_rule = ""
    if coverage is not None:
        coverage_rule = (
            "Only selected chunk IDs may use BROLL or CONTINUE_PREVIOUS_VISUAL. "
            "Every selected chunk must use BROLL so it remains independently searchable in the UI. "
            "Every unselected chunk must use KEEP_TALKING_HEAD with no shots.\n"
            "COVERAGE_SELECTED_CHUNK_IDS="
            + json.dumps([str(value) for value in coverage], ensure_ascii=False, separators=(",", ":"))
            + "\n"
        )
    return (
        DIRECTOR_INSTRUCTIONS
        + "\nRead all chronological chunks before deciding. "
        + "Return exactly one decision per transcript chunk, in identical order. "
        + "Use chunk_id to identify that chunk. Never merge chunks. "
        + "For BROLL: single means exactly 1 shot; sequence/juxtaposition means 2-3 shots. "
        + "For KEEP_TALKING_HEAD and CONTINUE_PREVIOUS_VISUAL: shots must be empty.\n"
        + coverage_rule
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


_HISTORICAL_CLAIM_MARKERS = {
    "anni 90", "1990", "90s", "archiv", "attacc", "conflict", "guerra", "history",
    "jihad", "militant", "storia", "terror", "violence", "violent", "violenza",
}
_HISTORICAL_EVIDENCE_MARKERS = {
    "1990", "90s", "archiv", "attack", "conflict", "document", "history", "jihad",
    "militant", "news", "terror", "violence", "violent", "war",
}
_SAFE_AVOID_QUALIFIERS = {"graphic", "unrelated", "wrong", "fictional", "reenact"}


def _contains_marker(text: str, markers: set[str]) -> bool:
    value = text.casefold()
    return any(marker in value for marker in markers)


def _ensure_findable_historical_queries(
    *,
    spoken_text: str,
    core_meaning: str,
    shot: dict[str, Any],
) -> None:
    """Add a short catalog query without asking the Director for a repair turn."""
    claim = f"{spoken_text} {core_meaning}"
    if not _contains_marker(claim, _HISTORICAL_CLAIM_MARKERS):
        return
    all_queries = [
        query
        for field in ("image_queries", "video_queries")
        for query in shot[field]
    ]
    query_text = " ".join(all_queries)
    folded = f"{query_text} {claim}".casefold()
    event = next((
        label
        for marker, label in (
            ("jihad", "jihad"), ("terror", "terrorism"), ("violen", "violence"),
            ("attack", "attacks"), ("conflict", "conflict"), ("war", "war"),
            ("history", "history"), ("archiv", "archive"),
        )
        if marker in folded
    ), "archive")
    ignored = {
        "archival", "archive", "documentary", "news", "historical", "history",
        "jihad", "jihadist", "terror", "terrorism", "violence", "violent",
        "attacks", "attack", "conflict", "war",
    }
    locations: list[str] = []
    for query in all_queries:
        for token in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ'-]+", query):
            if token[:1].isupper() and token.casefold() not in ignored:
                locations.append(token)
    aliases = {
        "egypt": "Egypt", "egyptian": "Egypt", "thailand": "Thailand", "thai": "Thailand",
        "italy": "Italy", "italian": "Italy", "france": "France", "french": "France",
        "spain": "Spain", "spanish": "Spain", "japan": "Japan", "japanese": "Japan",
        "china": "China", "chinese": "China", "india": "India", "indian": "India",
    }
    country = next((aliases[token.casefold()] for token in locations if token.casefold() in aliases), "")
    specific = next((token for token in locations if token.casefold() not in aliases), "")
    place = " ".join(dict.fromkeys(value for value in (specific, country) if value)) or "archive"
    broad_place = country or specific or "archive"
    broad = f"{event} {broad_place}"
    period = "1990s" if any(marker in claim.casefold() for marker in ("anni 90", "1990", "90s")) else ""
    precise = " ".join(value for value in (place, period, event, "archive") if value)
    middle = f"{event} {broad_place} archive"
    has_literal_evidence = _contains_marker(query_text, _HISTORICAL_EVIDENCE_MARKERS)
    for field in ("image_queries", "video_queries"):
        queries = shot[field]
        if not has_literal_evidence:
            shot[field] = [precise, middle, broad]
            continue
        if any(len(query.split()) <= 2 for query in queries):
            continue
        if len(queries) < 3:
            queries.append(broad)
        else:
            queries[-1] = broad


def _validate_historical_evidence(
    *,
    spoken_text: str,
    core_meaning: str,
    shots: list[dict[str, Any]],
    avoid: list[str],
    path: str,
) -> None:
    claim = f"{spoken_text} {core_meaning}"
    if not shots or not _contains_marker(claim, _HISTORICAL_CLAIM_MARKERS):
        return
    query_text = " ".join(
        query
        for shot in shots
        for field in ("image_queries", "video_queries")
        for query in shot[field]
    )
    if not _contains_marker(query_text, _HISTORICAL_EVIDENCE_MARKERS):
        raise ValueError(
            f"{path}: historical evidence query required; generic ambience is not faithful to the spoken claim"
        )
    for shot_index, shot in enumerate(shots):
        for field in ("image_queries", "video_queries"):
            if not any(len(query.split()) <= 2 for query in shot[field]):
                raise ValueError(
                    f"{path}.shots[{shot_index}].{field}: add a findable broad query of 2 words "
                    "after the precise historical query (example: 'jihad Egypt')"
                )
    claim_folded = claim.casefold()
    central_markers = {"archive", "news"}
    if any(marker in claim_folded for marker in ("jihad", "terror", "violen", "conflict", "guerra")):
        central_markers |= {
            "jihad", "terror", "militant", "violence", "violent", "violenza",
            "conflict", "gunfire", "war", "wars", "rebel",
        }
    retained_avoid: list[str] = []
    for item in avoid:
        folded = item.casefold()
        erases_subject = any(marker in folded for marker in central_markers)
        safe_narrowing = any(qualifier in folded for qualifier in _SAFE_AVOID_QUALIFIERS)
        if not erases_subject or safe_narrowing:
            retained_avoid.append(item)
    avoid[:] = retained_avoid


def compile_director_decisions(
    package: dict[str, Any],
    decisions: dict[str, Any],
) -> dict[str, Any]:
    """Compile compact AI decisions into the canonical deterministic visual plan."""
    if not isinstance(decisions, dict):
        raise ValueError("director output must be an object")
    chunks = list(package.get("chunks") or [])
    if not chunks:
        raise ValueError("transcript chunks are empty")
    chunk_ids = [str(row["id"]) for row in chunks]
    positions = {chunk_id: index for index, chunk_id in enumerate(chunk_ids)}
    if len(positions) != len(chunk_ids):
        raise ValueError("transcript contains duplicate chunk ids")

    raw_beats = decisions.get("beats")
    if not isinstance(raw_beats, list) or not raw_beats:
        raise ValueError("$.beats: expected at least one beat")

    if len(raw_beats) != len(chunks):
        raise ValueError(
            f"$.beats: expected exactly {len(chunks)} chunk decisions, got {len(raw_beats)}"
        )

    canonical: list[dict[str, Any]] = []
    used_queries: dict[str, dict[str, str]] = {"image_queries": {}, "video_queries": {}}
    selected_raw = package.get("coverage_selected_chunk_ids")
    selected = None if selected_raw is None else {str(value) for value in selected_raw}
    if selected is not None and not selected.issubset(positions):
        raise ValueError("coverage selection contains unknown chunk ids")
    for index, (raw, chunk) in enumerate(zip(raw_beats, chunks), start=1):
        path = f"$.beats[{index - 1}]"
        if not isinstance(raw, dict):
            raise ValueError(f"{path}: expected object")
        chunk_id = _clean_text(raw.get("chunk_id"))
        expected_id = str(chunk["id"])
        if chunk_id != expected_id:
            raise ValueError(f"{path}: chunk_id must be {expected_id}")
        covered = [chunk]

        action = _clean_text(raw.get("action"))
        if action not in {"BROLL", "KEEP_TALKING_HEAD", "CONTINUE_PREVIOUS_VISUAL"}:
            raise ValueError(f"{path}: unsupported action")
        if selected is not None and expected_id not in selected and action != "KEEP_TALKING_HEAD":
            raise ValueError(f"{path}: chunk {expected_id} is not selected for Coverage")
        visual_mode = _clean_text(raw.get("visual_mode"))
        if visual_mode not in {"single", "sequence", "juxtaposition"}:
            raise ValueError(f"{path}: unsupported visual_mode")

        raw_shots = raw.get("shots")
        if not isinstance(raw_shots, list):
            raise ValueError(f"{path}.shots: expected array")
        # A provider can incorrectly continue across an unselected talking-head
        # chunk. The selected phrase still needs coverage, so turn that orphaned
        # continuation into a searchable single shot instead of invalidating the
        # complete plan after both provider attempts.
        orphaned_continuation = (
            action == "CONTINUE_PREVIOUS_VISUAL"
            and (not canonical or canonical[-1]["action"] == "KEEP_TALKING_HEAD")
        )
        selected_needs_visual = selected is not None and expected_id in selected and action != "BROLL"
        if (orphaned_continuation or selected_needs_visual) and selected is not None and expected_id in selected:
            action = "BROLL"
            visual_mode = "single"
            meaning = _clean_text(raw.get("core_meaning"), allow_empty=True) or str(chunk["text"])
            query_words = meaning.split()[:10]
            if len(query_words) < 2:
                query_words.append("video")
            query = " ".join(query_words)
            raw_shots = [{
                "description": meaning,
                "image_queries": [query],
                "video_queries": [query],
            }]
        beat_id = f"beat_{index:03d}"
        shots: list[dict[str, Any]] = []
        if action == "BROLL":
            if visual_mode == "single" and len(raw_shots) != 1:
                raise ValueError(f"{path}: single BROLL requires exactly one shot")
            if visual_mode != "single" and not 2 <= len(raw_shots) <= 3:
                raise ValueError(f"{path}: sequence/juxtaposition requires 2-3 shots")
            for shot_index, shot in enumerate(raw_shots, start=1):
                if not isinstance(shot, dict):
                    raise ValueError(f"{path}.shots[{shot_index - 1}]: expected object")
                compiled_shot = {
                        "shot_id": f"{beat_id}_shot_{shot_index:02d}",
                        "description": _clean_text(shot.get("description")),
                        "image_queries": _queries(
                            shot.get("image_queries"),
                            f"{path}.shots[{shot_index - 1}].image_queries",
                        ),
                        "video_queries": _queries(
                            shot.get("video_queries"),
                            f"{path}.shots[{shot_index - 1}].video_queries",
                        ),
                    }
                _ensure_findable_historical_queries(
                    spoken_text=str(chunk["text"]),
                    core_meaning=_clean_text(raw.get("core_meaning")),
                    shot=compiled_shot,
                )
                for field in ("image_queries", "video_queries"):
                    for query in compiled_shot[field]:
                        key = query.casefold()
                        previous_beat = used_queries[field].get(key)
                        if previous_beat and previous_beat != beat_id:
                            raise ValueError(
                                f"{path}.{field}: query {query!r} reused by another visual beat {previous_beat}"
                            )
                        used_queries[field][key] = beat_id
                shots.append(compiled_shot)
        elif raw_shots:
            raise ValueError(f"{path}: only BROLL may contain shots")

        raw_avoid = raw.get("avoid")
        if not isinstance(raw_avoid, list):
            raise ValueError(f"{path}.avoid: expected array")
        avoid: list[str] = []
        seen_avoid: set[str] = set()
        for value in raw_avoid:
            clean = _clean_text(value)
            key = clean.casefold()
            if key not in seen_avoid:
                seen_avoid.add(key)
                avoid.append(clean)

        _validate_historical_evidence(
            spoken_text=str(chunk["text"]),
            core_meaning=_clean_text(raw.get("core_meaning")),
            shots=shots,
            avoid=avoid,
            path=path,
        )

        beat: dict[str, Any] = {
            "id": beat_id,
            "start": float(covered[0]["start"]),
            "end": float(covered[-1]["end"]),
            "covered_chunk_ids": [str(row["id"]) for row in covered],
            "original_text": " ".join(str(row["text"]) for row in covered),
            "action": action,
            "editorial_function": _clean_text(raw.get("editorial_function")),
            "core_meaning": _clean_text(raw.get("core_meaning")),
            "subtext": _clean_text(raw.get("subtext"), allow_empty=True),
            "visual_mode": visual_mode,
            "shots": shots,
            "avoid": avoid,
        }
        if action == "CONTINUE_PREVIOUS_VISUAL":
            if not canonical or canonical[-1]["action"] == "KEEP_TALKING_HEAD":
                raise ValueError(f"{path}: continuation requires an immediately preceding visual beat")
            beat["continuation_from"] = canonical[-1]["id"]

        canonical.append(beat)

    plan = {
        "schema_version": VERSION,
        "project_id": package["project_id"],
        "transcript_signature": package["transcript_signature"],
        "global_topic": _clean_text(decisions.get("global_topic")),
        "visual_beats": canonical,
    }
    validate_import(plan, package)
    return plan


def build_repair_prompt(error: Exception) -> str:
    message = " ".join(str(error).split())[:1000]
    return (
        "Your previous structured editorial decision failed deterministic validation. "
        "Keep the same whole-reel editorial reasoning, but return a corrected complete object. "
        "Return exactly one decision per transcript chunk, in the original order, and never merge chunks. "
        "Validation error: " + message
    )


class DirectorProvider(Protocol):
    provider_name: str
    model: str

    def generate_json(
        self,
        prompt: str,
        schema: dict[str, Any],
        *,
        previous_interaction_id: str | None = None,
    ) -> GeminiJSONReply:
        ...


@dataclass(frozen=True, slots=True)
class DirectorRunResult:
    plan: dict[str, Any]
    decisions: dict[str, Any]
    provider: str
    model: str
    attempts: int
    interaction_id: str | None
    validation_errors: tuple[str, ...]
    usage: tuple[dict[str, int], ...]
    requested_model: str
    fallback_used: bool
    transport_attempts: int


def generate_director_plan(
    package: dict[str, Any],
    provider: DirectorProvider,
    *,
    max_attempts: int = 2,
) -> DirectorRunResult:
    """Generate once; make one stateful repair call only if deterministic validation fails."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    prompt = build_director_prompt(package)
    previous_id: str | None = None
    errors: list[str] = []
    usage: list[dict[str, int]] = []
    requested_model = str(getattr(provider, "model", "unknown"))
    fallback_used = False
    transport_attempts = 0
    # Exact array cardinality on a large nested schema exhausts provider decoder
    # complexity (Gemini HTTP 400 / Groq json_validate_failed). Keep the count in
    # instructions and enforce it deterministically in compile_director_decisions.
    wire_schema = director_schema(len(package.get("chunks") or []))
    beats_schema = wire_schema["properties"]["beats"]
    beats_schema.pop("minItems", None)
    beats_schema.pop("maxItems", None)
    beats_schema["description"] = (
        f"Exactly {len(package.get('chunks') or [])} decisions, one per supplied chunk, in order."
    )
    for attempt in range(1, max_attempts + 1):
        request = prompt if attempt == 1 else build_repair_prompt(ValueError(errors[-1]))
        reply = provider.generate_json(
            request,
            wire_schema,
            previous_interaction_id=previous_id,
        )
        previous_id = reply.interaction_id or previous_id
        if reply.usage:
            usage.append(dict(reply.usage))
        requested_model = str(reply.requested_model or requested_model)
        fallback_used = fallback_used or bool(reply.fallback_used)
        transport_attempts += int(reply.transport_attempts or 1)
        try:
            plan = compile_director_decisions(package, reply.data)
        except (ValueError, KeyError, TypeError) as exc:
            errors.append(" ".join(str(exc).split())[:1000])
            if attempt >= max_attempts:
                raise ValueError(
                    f"API-first director remained invalid after {attempt} attempt(s): {errors[-1]}"
                ) from exc
            continue
        return DirectorRunResult(
            plan=plan,
            decisions=reply.data,
            provider=str(getattr(provider, "provider_name", "unknown")),
            model=reply.model,
            attempts=attempt,
            interaction_id=reply.interaction_id,
            validation_errors=tuple(errors),
            usage=tuple(usage),
            requested_model=requested_model,
            fallback_used=fallback_used,
            transport_attempts=transport_attempts,
        )
    raise RuntimeError("unreachable director state")
