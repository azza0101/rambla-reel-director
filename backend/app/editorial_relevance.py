"""Context-aware retrieval intent for imported editorial plans.

The external editorial plan remains authoritative. This module does not invent a
new story; it protects retrieval from generic visual shortcuts (laptops, maps,
hotel rooms, tutorial slides) when those props are not supported by the spoken
beat, and adds conservative literal fallbacks from entities explicitly present
in the beat.
"""
from __future__ import annotations

import json
import re
from typing import Any

INTENT_PREFIX = "RAMBLA_INTENT::"

_GENERIC_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (r"\b(laptop|computer|typing|notebook|taking notes?|working remotely)\b", ("laptop", "computer", "notebook", "typing", "appunti", "computer")),
    (r"\b(map|route planning|travel planning|itinerary planning|comparing routes?)\b", ("map", "mappa", "route", "tratta", "itinerary", "itinerario", "planning", "pianific")),
    (r"\b(hotel room|accommodation options?|booking|hotel comparison)\b", ("hotel", "albergo", "camera", "accommodation", "struttura ricettiva", "booking", "guesthouse", "guest house", "lodging", "strutture locali", "local structures")),
)

_BASE_NEGATIVES = (
    "travel vlogger talking to camera",
    "tutorial text slide",
    "infographic or presentation slide",
)


def _norm(value: Any) -> str:
    return " ".join(str(value or "").split())


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    folded = text.casefold()
    return any(needle.casefold() in folded for needle in needles)


def _dedupe(values: list[str], *, limit: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = _norm(raw)
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
        if len(out) >= limit:
            break
    return out


def _context(beat: dict[str, Any]) -> str:
    return _norm(" ".join([
        str(beat.get("core_meaning") or ""),
        str(beat.get("subtext") or ""),
        str(beat.get("original_text") or ""),
    ]))


def _unsupported_generic(beat: dict[str, Any], shot: dict[str, Any]) -> tuple[bool, list[str]]:
    context = _context(beat)
    target = _norm(" ".join([
        str(shot.get("description") or ""),
        *[str(v) for v in shot.get("image_queries") or []],
        *[str(v) for v in shot.get("video_queries") or []],
    ]))
    unsupported: list[str] = []
    for pattern, support_terms in _GENERIC_PATTERNS:
        if re.search(pattern, target, flags=re.I) and not _contains_any(context, support_terms):
            unsupported.append(pattern)
    return bool(unsupported), unsupported


def _literal_context_fallbacks(context: str) -> list[str]:
    """Return conservative English search phrases supported by explicit beat text.

    These cues are intentionally literal and multilingual. They never turn a
    question into an allegation: for example, elephant-treatment questions yield
    neutral sanctuary/care footage, not abuse footage.
    """
    folded = context.casefold()
    out: list[str] = []

    if any(token in folded for token in ("silenzio", "silence", "nessuna risposta", "no answer", "non risponde", "won't answer")):
        out += ["awkward silence people", "people avoiding answer", "uncomfortable silence conversation"]

    if any(token in folded for token in ("elefant", "elephant")):
        out += ["elephant sanctuary thailand", "elephant care sanctuary", "elephants sanctuary staff"]

    if any(token in folded for token in ("lavorator", "worker", "wage", "pagat", "stipend", "salary")):
        out += ["hospitality workers behind scenes", "local tourism workers", "hotel staff behind scenes"]

    if any(token in folded for token in ("compromess", "compromise", "greenwashing", "etichetta verde", "eco sull", "eco label", "sostenibil", "sustainable")):
        out += ["greenwashing tourism", "eco label travel", "sustainable tourism reality"]

    if any(token in folded for token in ("basilic", "basil")):
        out += ["wilted basil balcony", "dying basil plant pot", "dead basil balcony", "drooping basil plant"]

    if any(token in folded for token in ("gallin", "chicken")):
        out += ["free range chickens garden", "chickens vegetable garden"]

    return _dedupe(out, limit=8)


def build_retrieval_spec(beat: dict[str, Any], shot: dict[str, Any], kind: str) -> dict[str, Any]:
    if kind not in {"image", "video"}:
        raise ValueError("retrieval kind must be image or video")
    description = _norm(shot.get("description"))
    context = _context(beat)
    original_queries = [_norm(v) for v in shot.get(f"{kind}_queries") or [] if _norm(v)]
    generic_demoted, unsupported = _unsupported_generic(beat, shot)
    contextual = _literal_context_fallbacks(context)

    if generic_demoted:
        # The speech/context wins over an unsupported generic prop proposed by an
        # older plan. Search literal contextual evidence instead of reinforcing
        # the wrong laptop/map/hotel shortcut.
        queries = contextual or original_queries
        positive_parts = [beat.get("core_meaning"), *contextual[:3], beat.get("original_text")]
    else:
        # API-first/imported queries are deliberate shot-level search phrases.
        # Do not append broad topic/context fallbacks when explicit queries exist:
        # that turns a concrete scene into searches such as "greenwashing tourism".
        queries = original_queries or contextual
        positive_parts = [description, beat.get("core_meaning"), beat.get("subtext"), beat.get("original_text")]

    negatives = [str(v) for v in beat.get("avoid") or []]
    target_and_context = (description + " " + context).casefold()
    if not any(term in target_and_context for term in ("laptop", "computer", "notebook", "typing")):
        negatives += ["person using laptop", "typing on computer"]
    if not any(term in target_and_context for term in ("map", "mappa", "route planning", "itinerary planning")):
        negatives += ["generic travel planning map"]
    if not any(term in target_and_context for term in ("hotel room", "camera hotel", "albergo", "accommodation", "guesthouse", "guest house", "lodging")):
        negatives += ["generic hotel room"]
    negatives += list(_BASE_NEGATIVES)
    if generic_demoted and description:
        negatives.insert(0, description)

    positive = _norm(". ".join(str(v) for v in positive_parts if _norm(v)))
    if not positive:
        positive = description or (original_queries[0] if original_queries else context)

    visual_target = description or (original_queries[0] if original_queries else positive)

    return {
        "positive": positive,
        "visual_target": visual_target,
        "context": context,
        "negatives": _dedupe(negatives, limit=8),
        "queries": _dedupe(queries, limit=8),
        "generic_shot_demoted": generic_demoted,
        "unsupported_generic_patterns": unsupported,
        "shot_id": shot.get("shot_id"),
    }


def encode_retrieval_intent(beat: dict[str, Any], shot: dict[str, Any]) -> str:
    # Kind-independent intent; provider queries remain medium-specific.
    spec = build_retrieval_spec(beat, shot, "video")
    payload = {key: spec[key] for key in ("positive", "visual_target", "context", "negatives", "generic_shot_demoted", "shot_id")}
    return INTENT_PREFIX + json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def decode_retrieval_intent(intent: str) -> dict[str, Any]:
    text = str(intent or "")
    if not text.startswith(INTENT_PREFIX):
        return {"positive": text, "visual_target": text, "context": "", "negatives": [], "generic_shot_demoted": False, "shot_id": None}
    try:
        value = json.loads(text[len(INTENT_PREFIX):])
    except (TypeError, ValueError, json.JSONDecodeError):
        return {"positive": text, "visual_target": text, "context": "", "negatives": [], "generic_shot_demoted": False, "shot_id": None}
    if not isinstance(value, dict):
        return {"positive": text, "visual_target": text, "context": "", "negatives": [], "generic_shot_demoted": False, "shot_id": None}
    positive = _norm(value.get("positive")) or text
    return {
        "positive": positive,
        "visual_target": _norm(value.get("visual_target")) or positive,
        "context": _norm(value.get("context")),
        "negatives": _dedupe([str(v) for v in value.get("negatives") or []], limit=8),
        "generic_shot_demoted": bool(value.get("generic_shot_demoted")),
        "shot_id": value.get("shot_id"),
    }
