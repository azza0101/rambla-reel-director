"""Persistent transcript review, phrase intents and timestamp-safe correction."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any

from .atomic_io import write_json
from .editorial_import import digest, normalized_chunks, read


SCHEMA_VERSION = "rambla-phrase-intents-3"
FLAGS = ("coverage", "animation", "highlight")
WORD_FIELDS = {
    "coverage": "coverage_word_indices",
    "animation": "animation_word_indices",
    "highlight": "highlighted_word_indices",
}
WORD_SELECTION_FIELD = WORD_FIELDS["highlight"]


def _signature(chunks: list[dict[str, Any]]) -> str:
    return digest([
        {"id": str(row["id"]), "start": float(row["start"]), "end": float(row["end"]), "text": str(row["text"])}
        for row in chunks
    ])


def _empty() -> dict[str, Any]:
    return {
        "coverage": False,
        "animation": False,
        "highlight": False,
        "coverage_word_indices": [],
        "animation_word_indices": [],
        "highlighted_word_indices": [],
    }


def _row_words(row: dict[str, Any]) -> list[dict[str, Any]]:
    words = row.get("words")
    if isinstance(words, list) and words:
        return words
    return _words(str(row.get("text", "")), float(row.get("start", 0.0)), float(row.get("end", 0.001)))


def load_phrase_intents(run: Path) -> dict[str, Any]:
    chunks = normalized_chunks(run)
    signature = _signature(chunks)
    path = run / "phrase-intents.json"
    explicit = path.is_file()
    stored: dict[str, Any] = {}
    if explicit:
        try:
            value = read(path)
            stored = value.get("phrases", {}) if isinstance(value, dict) and value.get("transcript_signature") == signature else {}
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            stored = {}
    phrases: dict[str, dict[str, Any]] = {}
    for row in chunks:
        chunk_id = str(row["id"])
        raw = stored.get(chunk_id, {}) if isinstance(stored, dict) else {}
        word_count = len(_row_words(row))
        value = _empty()
        for intent, field in WORD_FIELDS.items():
            if isinstance(raw, dict) and field in raw:
                source_indices = raw.get(field)
                indices = sorted({item for item in source_indices if isinstance(item, int) and not isinstance(item, bool) and 0 <= item < word_count}) if isinstance(source_indices, list) else []
            elif isinstance(raw, dict) and raw.get(intent) is True:
                indices = list(range(word_count))
            else:
                indices = []
            value[field] = indices
            value[intent] = bool(indices)
        phrases[chunk_id] = value
    return {
        "schema_version": SCHEMA_VERSION,
        "transcript_signature": signature,
        "explicit": explicit,
        "phrases": phrases,
    }


def save_phrase_intents(
    run: Path,
    changes: dict[str, dict[str, Any]],
    expected_signature: str,
) -> dict[str, Any]:
    current = load_phrase_intents(run)
    if expected_signature != current["transcript_signature"]:
        raise ValueError("Transcript changed; reload phrase selections before saving")
    unknown = set(changes) - set(current["phrases"])
    if unknown:
        raise ValueError("Unknown transcript phrase: " + ", ".join(sorted(unknown)))
    phrases = deepcopy(current["phrases"])
    coverage_changed = False
    chunks = {str(row["id"]): row for row in normalized_chunks(run)}
    allowed_fields = set(FLAGS) | set(WORD_FIELDS.values())
    for chunk_id, update in changes.items():
        if not isinstance(update, dict) or set(update) - allowed_fields:
            raise ValueError("Phrase intents contain unsupported fields")
        word_count = len(_row_words(chunks[chunk_id]))
        for intent, field in WORD_FIELDS.items():
            if field in update:
                values = update[field]
                if not isinstance(values, list) or any(not isinstance(item, int) or isinstance(item, bool) or item < 0 or item >= word_count for item in values):
                    raise ValueError(f"{intent.title()} word index is outside the transcript phrase")
                indices = sorted(set(values))
            elif intent in update:
                selected = update[intent]
                if not isinstance(selected, bool):
                    raise ValueError(f"{intent} must be boolean")
                indices = list(range(word_count)) if selected else []
            else:
                continue
            if intent == "coverage" and phrases[chunk_id][field] != indices:
                coverage_changed = True
            phrases[chunk_id][field] = indices
            phrases[chunk_id][intent] = bool(indices)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "transcript_signature": current["transcript_signature"],
        "phrases": phrases,
    }
    intent_path = run / "phrase-intents.json"
    marker_path = run / "transcript-corrections.json"
    snapshot = {path: path.read_bytes() if path.exists() else None for path in (intent_path, marker_path)}
    try:
        write_json(intent_path, payload)
        plan_path = run / "visual-plan.json"
        if coverage_changed and plan_path.is_file():
            try:
                marker = read(marker_path) if marker_path.is_file() else {"original_chunks": normalized_chunks(run), "history": []}
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                marker = {"original_chunks": normalized_chunks(run), "history": []}
            marker.setdefault("history", []).append({"type": "coverage_selection"})
            marker["stale_plan_digest"] = digest(read(plan_path))
            write_json(marker_path, marker)
    except Exception:
        for path, content in snapshot.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(content)
        raise
    return {**payload, "explicit": True}


def transcript_document(run: Path) -> dict[str, Any]:
    chunks = normalized_chunks(run)
    if not chunks:
        raise ValueError("Analyze the source before editing its transcript")
    revision = _signature(chunks)
    return {
        "schema_version": "rambla-transcript-document-1",
        "revision": revision,
        "transcript_signature": revision,
        "text": "\n".join(str(row["text"]).strip() for row in chunks),
        "line_count": len(chunks),
        "start_seconds": float(chunks[0]["start"]),
        "end_seconds": float(chunks[-1]["end"]),
        "chunks": chunks,
    }


def _words(text: str, start: float, end: float) -> list[dict[str, Any]]:
    tokens = re.findall(r"\S+", text)
    if not tokens:
        raise ValueError("Transcript phrases cannot be empty")
    duration = max(0.001, end - start)
    step = duration / len(tokens)
    return [
        {
            "start": round(start + index * step, 6),
            "end": round(end if index == len(tokens) - 1 else start + (index + 1) * step, 6),
            "text": token,
        }
        for index, token in enumerate(tokens)
    ]


def _new_chunks(lines: list[str], old: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_start, source_end = float(old[0]["start"]), float(old[-1]["end"])
    if len(lines) == len(old):
        intervals = [(float(row["start"]), float(row["end"])) for row in old]
        ids = [str(row["id"]) for row in old]
    else:
        step = (source_end - source_start) / len(lines)
        intervals = [
            (source_start + index * step, source_end if index == len(lines) - 1 else source_start + (index + 1) * step)
            for index in range(len(lines))
        ]
        ids = [f"chunk_{index + 1:03d}" for index in range(len(lines))]
    result = []
    for chunk_id, text, (start, end) in zip(ids, lines, intervals):
        words = _words(text, start, end)
        result.append({"id": chunk_id, "start": round(start, 6), "end": round(end, 6), "text": text, "words": words})
    return result


def _overlap(a: dict[str, Any], b: dict[str, Any]) -> float:
    return max(0.0, min(float(a["end"]), float(b["end"])) - max(float(a["start"]), float(b["start"])))


def _remap_intents(old_chunks: list[dict[str, Any]], new_chunks: list[dict[str, Any]], old_intents: dict[str, Any]) -> dict[str, Any]:
    phrases: dict[str, dict[str, Any]] = {}
    source = old_intents.get("phrases", {})
    for row in new_chunks:
        candidates = sorted(old_chunks, key=lambda old: (_overlap(row, old), str(old["id"]) == str(row["id"])), reverse=True)
        match = candidates[0] if candidates and _overlap(row, candidates[0]) > 0 else None
        raw = source.get(str(match["id"]), {}) if match else {}
        value = _empty()
        new_word_count = len(_row_words(row))
        old_word_count = len(_row_words(match)) if match else 0
        for intent, field in WORD_FIELDS.items():
            if isinstance(raw, dict) and field in raw:
                old_indices = raw.get(field, [])
            elif isinstance(raw, dict) and raw.get(intent) and match:
                old_indices = list(range(old_word_count))
            else:
                old_indices = []
            indices = sorted({item for item in old_indices if isinstance(item, int) and not isinstance(item, bool) and 0 <= item < new_word_count})
            value[field] = indices
            value[intent] = bool(indices)
        phrases[str(row["id"])] = value
    return {
        "schema_version": SCHEMA_VERSION,
        "transcript_signature": _signature(new_chunks),
        "phrases": phrases,
    }


def save_transcript_document(run: Path, text: str, expected_revision: str) -> dict[str, Any]:
    old = normalized_chunks(run)
    if not old or expected_revision != _signature(old):
        raise ValueError("Transcript changed; reload it before saving")
    lines = [" ".join(line.split()) for line in str(text).splitlines() if line.strip()]
    if not lines:
        raise ValueError("Transcript cannot be empty")
    if any(len(line) > 10000 for line in lines):
        raise ValueError("A transcript phrase exceeds 10000 characters")
    new = _new_chunks(lines, old)
    raw_path = run / "transcript-raw.json"
    old_raw = read(raw_path)
    raw = deepcopy(old_raw)
    raw["segments"] = [
        {"start": row["start"], "end": row["end"], "text": row["text"], "words": row["words"]}
        for row in new
    ]
    raw["text"] = " ".join(row["text"] for row in new)
    raw["source_duration_seconds"] = float(new[-1]["end"])
    outline = {
        "schema_version": "content-sprint-0.1",
        "beats": [
            {"id": row["id"], "start_seconds": row["start"], "end_seconds": row["end"], "intent": row["text"], "broll_queries": []}
            for row in new
        ],
    }
    previous_intents = load_phrase_intents(run)
    intents = _remap_intents(old, new, previous_intents)
    marker_path = run / "transcript-corrections.json"
    try:
        marker = read(marker_path) if marker_path.is_file() else {"original_chunks": old, "history": []}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        marker = {"original_chunks": old, "history": []}
    marker.setdefault("history", []).append({"type": "full_transcript", "before_revision": expected_revision, "line_count": len(lines)})
    plan_path = run / "visual-plan.json"
    refresh = plan_path.is_file()
    if refresh:
        marker["stale_plan_digest"] = digest(read(plan_path))

    paths = [raw_path, run / "semantic-chunks.json", run / "semantic-beats.json", run / "phrase-intents.json", marker_path]
    snapshot = {path: path.read_bytes() if path.exists() else None for path in paths}
    try:
        write_json(raw_path, raw)
        write_json(run / "semantic-chunks.json", new)
        write_json(run / "semantic-beats.json", outline)
        write_json(run / "phrase-intents.json", intents)
        write_json(marker_path, marker)
    except Exception:
        for path, content in snapshot.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(content)
        raise
    return {
        "changed": True,
        "revision": intents["transcript_signature"],
        "transcript_signature": intents["transcript_signature"],
        "line_count": len(new),
        "editorial_refresh_required": refresh,
    }


def _selected_chunks(run: Path, intent: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    chunks = normalized_chunks(run)
    state = load_phrase_intents(run)
    selected = [row for row in chunks if state["phrases"].get(str(row["id"]), {}).get(intent)]
    if not selected:
        raise ValueError(f"Select at least one {intent.title()} phrase before exporting")
    return chunks, selected


def selected_word_ranges(run: Path, intent: str, *, max_words: int | None = None) -> list[dict[str, Any]]:
    if intent not in WORD_FIELDS:
        raise ValueError(f"Unsupported transcript intent: {intent}")
    chunks = normalized_chunks(run)
    state = load_phrase_intents(run)
    field = WORD_FIELDS[intent]
    ranges: list[dict[str, Any]] = []
    for row in chunks:
        chunk_id = str(row["id"])
        words = _row_words(row)
        indices = state["phrases"].get(chunk_id, {}).get(field, [])
        groups: list[list[int]] = []
        for index in indices:
            if not groups or index != groups[-1][-1] + 1 or (max_words is not None and len(groups[-1]) >= max_words):
                groups.append([index])
            else:
                groups[-1].append(index)
        for group in groups:
            selected_words = [words[index] for index in group]
            ranges.append({
                "source_chunk_ids": [chunk_id],
                "text": " ".join(str(word.get("text", "")).strip() for word in selected_words).strip(),
                "start_seconds": float(selected_words[0]["start"]),
                "end_seconds": float(selected_words[-1]["end"]),
                "word_start_index": group[0],
                "word_end_index": group[-1],
            })
    return ranges


def planning_chunks_for_coverage(run: Path) -> list[dict[str, Any]]:
    """Split Coverage into short, chronological units suited to media search."""
    chunks = normalized_chunks(run)
    state = load_phrase_intents(run)
    # A timing-only repair keeps already reviewed visual beats and media choices
    # stable. Any later transcript or selection edit invalidates this snapshot.
    snapshot_path = run / 'coverage-timing-snapshot.json'
    if snapshot_path.is_file():
        snapshot = read(snapshot_path)
        if (snapshot.get('transcript_signature') == state['transcript_signature']
                and snapshot.get('selection_digest') == digest(state['phrases'])):
            return snapshot['chunks']
    # The semantic transcript can contain several spoken sentences in one
    # display chunk. Preserve the ASR sentence/segment ends before applying the
    # length cap, otherwise a mechanical 10-word cut can separate a noun from
    # its adjective (for example ``violenza importante``) and attach that word
    # to the following sentence.
    raw_boundaries: set[tuple[str, float, float]] = set()
    raw_path = run / "transcript-raw.json"
    if raw_path.is_file():
        try:
            for segment in read(raw_path).get("segments", []):
                segment_words = segment.get("words") or []
                if segment_words:
                    last = segment_words[-1]
                    raw_boundaries.add((
                        str(last.get("text", "")).strip(),
                        round(float(last["start"]), 4),
                        round(float(last["end"]), 4),
                    ))
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            raw_boundaries = set()
    result: list[dict[str, Any]] = []
    for row in chunks:
        chunk_id = str(row["id"])
        words = _row_words(row)
        selected = set(state["phrases"].get(chunk_id, {}).get(WORD_FIELDS["coverage"], []))
        runs: list[tuple[bool, list[tuple[int, dict[str, Any]]]]] = []
        for index, word in enumerate(words):
            active = index in selected
            if not runs or runs[-1][0] != active:
                runs.append((active, []))
            runs[-1][1].append((index, word))
        segments: list[tuple[bool, list[tuple[int, dict[str, Any]]]]] = []
        semantic_restarts = {
            "allora", "comunque", "dopo", "eppure", "infatti", "inoltre",
            "negli", "oggi", "ora", "però", "poi", "quindi",
        }
        for active, entries in runs:
            if not active:
                segments.append((False, entries))
                continue
            current: list[tuple[int, dict[str, Any]]] = []
            for entry_position, entry in enumerate(entries):
                word = entry[1]
                raw_word = str(word.get("text", "")).strip(".,;:!?()\"'")
                restart = raw_word.casefold()
                previous_word = (
                    str(current[-1][1].get("text", "")).strip(".,;:!?()\"'").casefold()
                    if current else ""
                )
                next_word = (
                    str(entries[entry_position + 1][1].get("text", "")).strip(".,;:!?()\"'").casefold()
                    if entry_position + 1 < len(entries) else ""
                )
                capitalized_restart = (
                    raw_word[:1].isupper()
                    and len(entries) - entry_position >= 3
                    and previous_word not in {
                        "a", "al", "alla", "con", "da", "dal", "dalla", "di", "del", "della",
                        "e", "in", "nel", "nella", "o", "per", "su", "tra", "un", "una",
                    }
                )
                phrase_restart = restart == "delle" and next_word.startswith("attivit")
                if current and len(current) >= 3 and (
                    restart in semantic_restarts or capitalized_restart or phrase_restart
                ):
                    segments.append((True, current))
                    current = []
                gap = float(word["start"]) - float(current[-1][1]["end"]) if current else 0.0
                duration = float(word["end"]) - float(current[0][1]["start"]) if current else 0.0
                if current and (duration > 4.0 or gap > 0.65):
                    remaining = len(entries) - entry_position
                    if duration > 4.0 and remaining == 1 and len(current) >= 4:
                        combined = [*current, entry]
                        candidates: list[tuple[float, float, int]] = []
                        for cut in range(2, len(combined) - 1):
                            left_duration = float(combined[cut - 1][1]["end"]) - float(combined[0][1]["start"])
                            right_duration = float(combined[-1][1]["end"]) - float(combined[cut][1]["start"])
                            if left_duration <= 4.0 and right_duration <= 4.0:
                                pause = float(combined[cut][1]["start"]) - float(combined[cut - 1][1]["end"])
                                balance = abs((len(combined) / 2) - cut)
                                candidates.append((-pause, balance, cut))
                        if candidates:
                            cut = min(candidates)[2]
                            segments.append((True, combined[:cut]))
                            current = combined[cut:]
                            continue
                    segments.append((True, current))
                    current = []
                current.append(entry)
                raw_boundary = (
                    str(word.get("text", "")).strip(),
                    round(float(word["start"]), 4),
                    round(float(word["end"]), 4),
                ) in raw_boundaries
                if raw_boundary or (len(current) >= 4 and re.search(r"[.!?;:]$", str(word.get("text", "")))):
                    segments.append((True, current))
                    current = []
            if current:
                segments.append((True, current))
        for run_index, (active, entries) in enumerate(segments, 1):
            first_index, first_word = entries[0]
            last_index, last_word = entries[-1]
            derived_id = chunk_id if len(segments) == 1 else f"{chunk_id}__coverage_{run_index:02d}"
            result.append({
                "id": derived_id,
                "start": float(first_word["start"]),
                "end": float(last_word["end"]),
                "text": " ".join(str(word.get("text", "")).strip() for _, word in entries).strip(),
                "words": [word for _, word in entries],
                "source_chunk_id": chunk_id,
                "source_word_start_index": first_index,
                "source_word_end_index": last_index,
                "coverage_selected": active,
            })
    return result


def build_animation_export(run: Path, project_id: str, video_context: dict[str, Any] | None = None) -> dict[str, Any]:
    selected = selected_word_ranges(run, "animation")
    if not selected:
        raise ValueError("Select at least one Animation range before exporting")
    items: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    group = 0
    total = 0.0
    for order, row in enumerate(selected, 1):
        consecutive = previous is not None and abs(float(row["start_seconds"]) - float(previous["end_seconds"])) <= 0.001
        gap = round(float(row["start_seconds"]) - float(previous["end_seconds"]), 6) if previous else None
        if not consecutive:
            group += 1
        if previous:
            items.append({"type": "separator", "label": "────────────────", "relationship": "consecutive" if consecutive else "separate", "gap_seconds": gap})
        duration = round(float(row["end_seconds"]) - float(row["start_seconds"]), 6)
        total += duration
        source_id = row["source_chunk_ids"][0]
        full_chunk = row["word_start_index"] == 0 and row["word_end_index"] == len(_row_words(next(chunk for chunk in normalized_chunks(run) if str(chunk["id"]) == source_id))) - 1
        item_id = source_id if full_chunk else f"{source_id}_words_{row['word_start_index']}_{row['word_end_index']}"
        items.append({
            "type": "phrase", "order": order, "id": item_id, "text": row["text"], "source_chunk_ids": row["source_chunk_ids"],
            "word_start_index": row["word_start_index"], "word_end_index": row["word_end_index"],
            "duration_seconds": duration, "start_seconds": float(row["start_seconds"]), "end_seconds": float(row["end_seconds"]),
            "concatenation_group": group, "concatenated_with_previous": consecutive,
            "previous_phrase_id": items[-2]["id"] if previous and len(items) >= 2 else None, "gap_from_previous_seconds": gap,
        })
        previous = row
    return {
        "schema_version": "rambla-animation-selection-2", "project_id": project_id,
        "video_context": video_context, "timing_basis": "source transcript word timestamps",
        "phrase_count": len(selected), "total_phrase_duration_seconds": round(total, 6), "items": items,
    }


def build_textplus_export(run: Path, project_id: str, *, fps: int = 25, track_hint: int = 3) -> dict[str, Any]:
    if fps <= 0:
        raise ValueError("Timeline fps must be positive")
    items = []
    for row in selected_word_ranges(run, "highlight", max_words=3):
        start, end = float(row["start_seconds"]), float(row["end_seconds"])
        items.append({
            "kind": "TEXT_PLUS", "phrase_id": row["source_chunk_ids"][0], "text": row["text"],
            "word_start_index": row["word_start_index"], "word_end_index": row["word_end_index"],
            "start_seconds": start, "end_seconds": end, "duration_seconds": round(end - start, 6),
            "start_frame": round(start * fps), "end_frame": round(end * fps), "track_hint": int(track_hint),
        })
    if not items:
        raise ValueError("Select at least one Highlight word before exporting")
    return {
        "schema_version": "rambla-resolve-textplus-1", "project_id": project_id,
        "fps": int(fps), "timeline_basis": "source transcript timestamps",
        "effect_preset": None, "item_count": len(items), "items": items,
    }


def build_combined_resolve_export(run: Path, project_id: str, *, fps: int = 25) -> dict[str, Any]:
    """Build title rows plus native-subtitle rows without duplicating highlights."""
    if fps <= 0:
        raise ValueError("Timeline fps must be positive")
    title_export = build_textplus_export(run, project_id, fps=fps)
    intents = load_phrase_intents(run).get("phrases", {})
    subtitles: list[dict[str, Any]] = []
    for chunk in normalized_chunks(run):
        chunk_id = str(chunk["id"])
        words = _row_words(chunk)
        highlighted = set(intents.get(chunk_id, {}).get("highlighted_word_indices", []))
        groups: list[list[int]] = []
        for index in range(len(words)):
            if index in highlighted:
                continue
            if not groups or index != groups[-1][-1] + 1 or len(groups[-1]) >= 3:
                groups.append([])
            groups[-1].append(index)
        for group in groups:
            selected = [words[index] for index in group]
            start = float(selected[0]["start"])
            end = float(selected[-1]["end"])
            text = " ".join(str(word.get("text", "")).strip() for word in selected).strip()
            if not text:
                continue
            subtitles.append({
                "kind": "SUBTITLE",
                "phrase_id": chunk_id,
                "text": text,
                "word_start_index": group[0],
                "word_end_index": group[-1],
                "start_seconds": start,
                "end_seconds": end,
                "duration_seconds": round(end - start, 6),
                "start_frame": round(start * fps),
                "end_frame": round(end * fps),
            })
    return {
        "schema_version": "rambla-resolve-combined-1",
        "project_id": project_id,
        "fps": int(fps),
        "timeline_basis": "source transcript word timestamps",
        "transcript_signature": load_phrase_intents(run).get("transcript_signature"),
        "title_count": len(title_export["items"]),
        "subtitle_count": len(subtitles),
        "titles": title_export["items"],
        "subtitles": subtitles,
    }
