"""Pure merge helpers for per-beat replace/append retrieval rounds."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable


def _candidate_key(candidate: dict[str, Any]) -> str:
    provider = str(candidate.get("provider") or candidate.get("source") or "").strip().casefold()
    provider_id = str(candidate.get("provider_id") or "").strip()
    if provider and provider_id:
        return f"{provider}:{provider_id}"
    source_url = str(candidate.get("source_url") or candidate.get("source_page") or "").strip()
    if source_url:
        return f"url:{source_url}"
    content_hash = str(candidate.get("content_sha256") or candidate.get("perceptual_hash") or "").strip()
    if content_hash:
        return f"hash:{content_hash}"
    return f"id:{candidate.get('id') or candidate.get('asset_id') or repr(candidate)}"


def seen_candidate_keys(candidates: Iterable[dict[str, Any]]) -> set[str]:
    return {_candidate_key(candidate) for candidate in candidates if isinstance(candidate, dict)}


def _merge_candidates(existing: list[dict[str, Any]], fresh: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    output = [deepcopy(row) for row in existing if isinstance(row, dict)]
    seen = seen_candidate_keys(output)
    for candidate in fresh:
        if not isinstance(candidate, dict): continue
        key = _candidate_key(candidate)
        if key in seen: continue
        seen.add(key); output.append(deepcopy(candidate))
        if len(output) >= limit: break
    return output[:limit]


def _row_key(row: dict[str, Any]) -> str:
    return str(row.get("coverage_slot_id") or row.get("beat_id") or "")


def _target(row: dict[str, Any], beat_id: str) -> bool:
    parent = str(row.get("parent_beat_id") or "")
    if parent: return parent == beat_id
    key = _row_key(row)
    return key == beat_id or key.startswith(beat_id + ":")


def _next_round(existing: list[dict[str, Any]], beat_id: str) -> int:
    rounds = [int(row.get("research_round") or 0) for row in existing if isinstance(row, dict) and _target(row, beat_id)]
    return max(rounds, default=0) + 1


def _cap_video_beat(rows: list[dict[str, Any]], beat_id: str, limit: int = 12) -> None:
    remaining = limit
    for row in rows:
        if not _target(row, beat_id): continue
        candidates = list(row.get("candidates") or [])
        row["candidates"] = candidates[:remaining]
        if row.get("quality_version"):
            from .quality_video import synchronize_proposals
            synchronize_proposals(row)
            row["eligible_candidate_count"] = sum(bool(c.get("clip_verified")) for c in row["candidates"])
        remaining -= len(row["candidates"])
        if remaining <= 0: remaining = 0


def merge_video_rows(existing: list[dict[str, Any]], fresh: list[dict[str, Any]], beat_id: str, mode: str) -> list[dict[str, Any]]:
    if mode not in {"replace", "append"}: raise ValueError("research mode must be replace or append")
    existing = [deepcopy(row) for row in existing if isinstance(row, dict)]
    fresh = [deepcopy(row) for row in fresh if isinstance(row, dict) and _target(row, beat_id)]
    research_round = _next_round(existing, beat_id)
    for row in fresh: row["research_round"] = research_round
    if mode == "replace":
        output: list[dict[str, Any]] = []; inserted = False
        for row in existing:
            if _target(row, beat_id):
                if not inserted: output.extend(deepcopy(fresh)); inserted = True
                continue
            output.append(row)
        if not inserted: output.extend(deepcopy(fresh))
        _cap_video_beat(output, beat_id)
        return output

    fresh_by_key = {_row_key(row): row for row in fresh}
    output = []
    matched: set[str] = set()
    for row in existing:
        if not _target(row, beat_id): output.append(row); continue
        key = _row_key(row); incoming = fresh_by_key.get(key)
        if not incoming:
            row["research_round"] = research_round; output.append(row); continue
        matched.add(key)
        merged = deepcopy(row)
        merged["discovery_sources"] = _merge_candidates(list(row.get("discovery_sources") or []), list(incoming.get("discovery_sources") or []), 12)
        merged["candidates"] = _merge_candidates(list(row.get("candidates") or []), list(incoming.get("candidates") or []), 12)
        for field in ("search_attempts", "errors", "rejected_candidates"):
            merged[field] = list(row.get(field) or []) + list(incoming.get(field) or [])
        for field, value in incoming.items():
            if field not in {"candidates", "discovery_sources", "search_attempts", "errors", "rejected_candidates"}:
                merged[field] = deepcopy(value)
        merged["research_round"] = research_round
        output.append(merged)
    for key, row in fresh_by_key.items():
        if key not in matched: output.append(deepcopy(row))
    _cap_video_beat(output, beat_id)
    return output


def merge_image_artifact(existing: dict[str, Any], fresh: dict[str, Any], beat_id: str, mode: str) -> dict[str, Any]:
    if mode not in {"replace", "append"}: raise ValueError("research mode must be replace or append")
    output = deepcopy(existing) if isinstance(existing, dict) else {}
    output.setdefault("chunks", {})
    fresh_chunks = fresh.get("chunks", {}) if isinstance(fresh, dict) else {}
    incoming = deepcopy(fresh_chunks.get(beat_id)) if isinstance(fresh_chunks, dict) else None
    old = deepcopy(output["chunks"].get(beat_id, {}))
    round_no = int(old.get("research_round") or 0) + 1
    if incoming is None:
        if mode == "replace": output["chunks"].pop(beat_id, None)
        return output
    incoming["research_round"] = round_no
    if mode == "replace" or not old:
        incoming["candidates"] = list(incoming.get("candidates") or [])[:16]
        output["chunks"][beat_id] = incoming
    else:
        merged = old
        merged["candidates"] = _merge_candidates(list(old.get("candidates") or []), list(incoming.get("candidates") or []), 16)
        for field in ("search_attempts", "errors", "rejected_candidates"):
            merged[field] = list(old.get(field) or []) + list(incoming.get(field) or [])
        for field, value in incoming.items():
            if field not in {"candidates", "search_attempts", "errors", "rejected_candidates"}:
                merged[field] = deepcopy(value)
        merged["research_round"] = round_no
        output["chunks"][beat_id] = merged
    if isinstance(fresh, dict) and fresh.get("schema_version"):
        output["schema_version"] = fresh["schema_version"]
    return output
