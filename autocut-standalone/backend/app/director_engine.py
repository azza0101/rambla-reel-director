"""Deterministic, Resolve-independent Director Engine for offline review plans."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol

from .coverage import CoverageSlot, plan_coverage_slots
from .taste_profile import ROUTES, TasteContext
from .visual_routing import VisualRouteDecision


ACTIONS = {"TALKING_HEAD", "BROLL", "EDITORIAL_INSERT", "PUNCH_IN", "STICKER", "CAPTION_EMPHASIS"}


class ASRAdapter(Protocol):
    def load(self) -> dict[str, Any]: ...


class FasterWhisperArtifact:
    """Read the existing isolated faster-whisper artifact without loading a model."""

    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8"))


class DirectorAdapter(Protocol):
    def decide(self, beat: dict[str, Any], selected: dict[str, Any] | None) -> tuple[str, str, dict[str, Any]]: ...


class AssetProvider(Protocol):
    def list_assets(self, client_id: str) -> list[dict[str, Any]]: ...


class Reranker(Protocol):
    def rank(self, query: str, assets: list[dict[str, Any]]) -> list[dict[str, Any]]: ...


class ResolveApply(Protocol):
    """Future boundary only: offline planning must never call this port."""

    def apply_approved_plan(self, plan: dict[str, Any]) -> dict[str, Any]: ...


class LocalAssetProvider:
    def __init__(self, assets: list[dict[str, Any]]):
        self.assets = assets

    def list_assets(self, client_id: str) -> list[dict[str, Any]]:
        return [dict(asset) for asset in self.assets if asset.get("client_id") == client_id]


class StockProvider:
    """Legacy credential boundary retained for compatibility with earlier callers."""

    def __init__(self, name: str, credential: str | None = None):
        if name not in {"pexels", "pixabay"}:
            raise ValueError("unsupported stock provider")
        self.name = name
        self.credential = credential

    def list_assets(self, client_id: str) -> list[dict[str, Any]]:
        return []

    def availability(self) -> str:
        return "CONFIGURED" if self.credential else "CREDENTIAL_REQUIRED"


class PexelsProvider(StockProvider):
    def __init__(self, credential: str | None = None):
        super().__init__("pexels", credential)


class PixabayProvider(StockProvider):
    def __init__(self, credential: str | None = None):
        super().__init__("pixabay", credential)


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[\wÀ-ÿ]+", text.lower()) if len(token) > 2}


class TextReranker:
    def rank(self, query: str, assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        terms = _tokens(query)
        rows = []
        for asset in assets:
            haystack = " ".join([asset.get("description", ""), *asset.get("tags", []), asset.get("path", "")])
            matched = sorted(terms & _tokens(haystack))
            score = round(len(matched) / max(1, len(terms)), 4)
            rows.append(
                {
                    "id": asset["id"],
                    "client_id": asset["client_id"],
                    "path": asset["path"],
                    "description": asset.get("description", ""),
                    "kind": asset.get("kind", "unknown"),
                    "score": score,
                    "embedding_score": None,
                    "reranker_score": None,
                    "providers": {"embedding": None, "reranker": None, "retrieval": "metadata-overlap-v1"},
                    "reason": f"metadata overlap: {', '.join(matched) or 'none'}",
                }
            )
        return sorted(rows, key=lambda row: (-row["score"], row["id"]))


class RuleDirector:
    def decide(self, beat: dict[str, Any], selected: dict[str, Any] | None) -> tuple[str, str, dict[str, Any]]:
        intent = beat["intent"].lower()
        if selected is not None:
            return "BROLL", "Available visual evidence matches the semantic intent.", {"fit": "COVER"}
        if "hook" in intent:
            return "PUNCH_IN", "Brief emphasis on the opening hook; retain the speaker.", {"scale": 1.08}
        if "reveal" in intent:
            return "CAPTION_EMPHASIS", "Emphasize the verbal reveal without an unverified visual asset.", {"style": "keyword"}
        return "TALKING_HEAD", "Preserve the speaker and avoid an unsupported insert.", {}


def _frame(seconds: float, fps: int) -> int:
    return math.floor(seconds * fps + 0.5)


def _captions(transcript: dict[str, Any], fps: int, source_frames: int) -> list[dict[str, Any]]:
    captions = []
    for segment in transcript["segments"]:
        words = segment.get("words") or []
        if words:
            chunks: list[list[dict[str, Any]]] = []
            current: list[dict[str, Any]] = []
            for word in words:
                current.append(word)
                text = " ".join(item["text"].strip() for item in current)
                if (
                    len(text) >= 42
                    or word["end"] - current[0]["start"] >= 3
                    or word["text"].strip().endswith((".", "?", "!"))
                ):
                    chunks.append(current)
                    current = []
            if current:
                chunks.append(current)
            for chunk in chunks:
                text = " ".join(item["text"].strip() for item in chunk).strip()
                captions.append(
                    {
                        "start_frame": _frame(chunk[0]["start"], fps),
                        "end_frame": min(
                            source_frames,
                            max(_frame(chunk[-1]["end"], fps), _frame(chunk[0]["start"], fps) + 1),
                        ),
                        "text": text,
                        "emphasis_candidates": [],
                        "review_state": "ASR_UNREVIEWED",
                    }
                )
        else:
            text = segment["text"].strip()
            captions.append(
                {
                    "start_frame": _frame(segment["start"], fps),
                    "end_frame": min(
                        source_frames,
                        max(_frame(segment["end"], fps), _frame(segment["start"], fps) + 1),
                    ),
                    "text": text,
                    "emphasis_candidates": [],
                    "review_state": "ASR_UNREVIEWED",
                }
            )
    return captions


def _outline_ranges(outline: dict[str, Any], fps: int, source_frames: int) -> list[tuple[int, int]]:
    beats = outline["beats"]
    if not beats:
        raise ValueError("at least one semantic beat required")
    edges = [0]
    for left, right in zip(beats, beats[1:]):
        if left["start_seconds"] >= right["start_seconds"] or left["end_seconds"] > right["start_seconds"]:
            raise ValueError("semantic beats overlap or are unordered")
        edges.append(_frame((left["end_seconds"] + right["start_seconds"]) / 2, fps))
    edges.append(source_frames)
    if any(a >= b for a, b in zip(edges, edges[1:])):
        raise ValueError("semantic beats collapse at source frame rate")
    return list(zip(edges, edges[1:]))


def _ranked_explicit_candidates(rows: list[dict[str, Any]], client_id: str) -> list[dict[str, Any]]:
    copied = [dict(row) for row in rows]
    if any(row.get("client_id") != client_id for row in copied):
        raise ValueError("candidate violates client isolation")
    if any("score" not in row for row in copied):
        raise ValueError("explicit online candidates must already be ranked")
    return sorted(copied, key=lambda row: (-float(row["score"]), str(row.get("id", ""))))


def _coverage_rows(
    beat_outline: dict[str, Any],
    fps: int,
    source_frames: int,
    coverage_slots_by_beat: dict[str, list[dict[str, Any]]] | None,
) -> list[dict[str, Any]]:
    if coverage_slots_by_beat is None:
        source_slots: list[CoverageSlot | dict[str, Any]] = list(plan_coverage_slots(beat_outline["beats"]))
    else:
        source_slots = []
        for beat in beat_outline["beats"]:
            source_slots.extend(coverage_slots_by_beat.get(str(beat["id"]), []))

    source_seconds = source_frames / fps
    output: list[dict[str, Any]] = []
    for source in source_slots:
        row = asdict(source) if isinstance(source, CoverageSlot) else dict(source)
        start_seconds = float(row["start_seconds"])
        end_seconds = float(row["end_seconds"])
        if not (0 <= start_seconds < end_seconds <= source_seconds + (0.5 / fps)):
            raise ValueError("coverage slot timing is outside source")
        row["start_seconds"] = round(start_seconds, 4)
        row["end_seconds"] = round(end_seconds, 4)
        row["start_frame"] = _frame(start_seconds, fps)
        row["end_frame"] = min(source_frames, max(row["start_frame"] + 1, _frame(end_seconds, fps)))
        row["queries"] = list(row.get("queries") or [])
        row["minimum_proposals"] = int(row.get("minimum_proposals", 2))
        output.append(row)
    return sorted(output, key=lambda row: (row["start_frame"], row["end_frame"], str(row["id"])))


def _route_payload(value: VisualRouteDecision | dict[str, Any]) -> dict[str, Any]:
    return asdict(value) if isinstance(value, VisualRouteDecision) else dict(value)


def _decorate_coverage_with_taste(
    coverage_slots: list[dict[str, Any]],
    *,
    taste_context: TasteContext | None,
    route_by_slot: dict[str, VisualRouteDecision | dict[str, Any]],
) -> None:
    for slot in coverage_slots:
        route = route_by_slot.get(str(slot["id"]))
        if route is not None:
            payload = _route_payload(route)
            route_name = str(payload.get("route") or "").strip()
            if route_name not in ROUTES:
                raise ValueError("coverage slot visual route is unsupported")
            confidence = float(payload.get("confidence", 0.0))
            if not 0.0 <= confidence <= 1.0:
                raise ValueError("coverage slot route confidence is invalid")
            slot["visual_route"] = route_name
            slot["route_reason"] = str(payload.get("reason") or "")
            slot["route_confidence"] = confidence
            if payload.get("search_hint"):
                slot["route_search_hint"] = str(payload["search_hint"])
        if taste_context is not None:
            slot["taste_profile_version"] = taste_context.profile_version
            slot["taste_profile_hash"] = taste_context.profile_hash
            slot["applicable_guardrails"] = dict(taste_context.guardrails)


def build_edit_plan(
    transcript: dict[str, Any],
    beat_outline: dict[str, Any],
    assets: list[dict[str, Any]],
    *,
    client_id: str,
    source_frames: int,
    director: DirectorAdapter | None = None,
    reranker: Reranker | None = None,
    candidate_assets_by_beat: dict[str, list[dict[str, Any]]] | None = None,
    coverage_slots_by_beat: dict[str, list[dict[str, Any]]] | None = None,
    confidence_review_threshold: float = 0.7,
    taste_context: TasteContext | None = None,
    route_by_slot: dict[str, VisualRouteDecision | dict[str, Any]] | None = None,
) -> dict[str, Any]:
    fps = int(transcript["timeline_fps"])
    if fps <= 0 or source_frames <= 0 or not client_id:
        raise ValueError("source timing and client identity required")
    if not 0 <= confidence_review_threshold <= 1:
        raise ValueError("invalid confidence review threshold")
    if taste_context is not None and taste_context.client_id != client_id:
        raise ValueError("taste context violates client isolation")

    director = director or RuleDirector()
    reranker = reranker or TextReranker()
    local_assets = LocalAssetProvider(assets).list_assets(client_id)
    explicit_by_beat = candidate_assets_by_beat or {}
    captions = _captions(transcript, fps, source_frames)
    coverage_slots = _coverage_rows(beat_outline, fps, source_frames, coverage_slots_by_beat)
    _decorate_coverage_with_taste(
        coverage_slots,
        taste_context=taste_context,
        route_by_slot=route_by_slot or {},
    )
    beats = []
    used_online = False

    for outline, (start, end) in zip(
        beat_outline["beats"], _outline_ranges(beat_outline, fps, source_frames)
    ):
        query = (outline.get("broll_queries") or [""])[0]
        semantic_query = f"{outline['intent']}; {query}" if query else ""
        explicit = explicit_by_beat.get(outline["id"])

        if explicit is not None:
            used_online = True
            candidates = _ranked_explicit_candidates(explicit, client_id)
            selected = candidates[0] if candidates else None
            if selected is None:
                review_state = "NO_SELECTION"
            elif float(selected["score"]) < confidence_review_threshold:
                review_state = "REVIEW_REQUIRED_LOW_CONFIDENCE"
            else:
                review_state = "AUTO_SELECTED"
        else:
            candidates = reranker.rank(query, local_assets) if query else []
            selected = candidates[0] if candidates and candidates[0]["score"] >= 0.7 else None
            review_state = "AUTO_SELECTED" if selected is not None else "NO_SELECTION"

        action, rationale, metadata = director.decide(outline, selected)
        if action != "BROLL":
            selected = None
            if review_state == "AUTO_SELECTED":
                review_state = "NO_SELECTION"
        provider_name = getattr(director, "last_provider", "deterministic-rule-v1")
        candidate_providers = candidates[0].get("providers", {}) if candidates else {}
        beat_captions = [
            row["text"] for row in captions if row["start_frame"] < end and row["end_frame"] > start
        ]
        beats.append(
            {
                "id": outline["id"],
                "start_frame": start,
                "end_frame": end,
                "intent": outline["intent"],
                "transcript": " ".join(
                    segment["text"].strip()
                    for segment in transcript["segments"]
                    if _frame(segment["start"], fps) < end and _frame(segment["end"], fps) > start
                ),
                "action": action,
                "rationale": rationale,
                "parameters": metadata,
                "broll_query": semantic_query,
                "selected_asset": selected,
                "candidates": candidates,
                "review_state": review_state,
                "providers": {
                    "director": provider_name,
                    "embedding": candidate_providers.get("embedding"),
                    "reranker": candidate_providers.get("reranker"),
                    "retrieval": candidate_providers.get("retrieval", "client-local"),
                },
                "caption_text": " ".join(beat_captions),
            }
        )

    plan = {
        "schema_version": "director-offline-1",
        "status": "DRAFT",
        "client_id": client_id,
        "source": {
            "media": transcript.get("source", ""),
            "fps": fps,
            "start_frame": transcript.get("timeline_start_frame", 0),
            "duration_frames": source_frames,
        },
        "asr": {
            "adapter": "faster-whisper-artifact",
            "language": transcript.get("language", "und"),
            "review_state": "UNREVIEWED",
        },
        "director": {"adapter": getattr(director, "provider_name", "deterministic-rule-v1")},
        "retrieval": {
            "local_client_only": not used_online,
            "external": "online-sourcing-v1" if used_online else "credential-gated",
        },
        "beats": beats,
        "coverage_slots": coverage_slots,
        "captions": captions,
    }
    if taste_context is not None:
        plan["taste_snapshot"] = {
            "client_id": taste_context.client_id,
            "profile_version": taste_context.profile_version,
            "profile_hash": taste_context.profile_hash,
        }

    validate_edit_plan(plan)
    canonical = json.dumps(plan, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    plan["content_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return plan


def validate_edit_plan(plan: dict[str, Any]) -> None:
    if plan.get("schema_version") != "director-offline-1" or plan.get("status") != "DRAFT":
        raise ValueError("unsupported offline plan schema/status")
    frames = plan["source"]["duration_frames"]
    fps = plan["source"]["fps"]
    if not isinstance(frames, int) or frames <= 0 or fps <= 0:
        raise ValueError("invalid source timebase")

    taste_snapshot = plan.get("taste_snapshot")
    if taste_snapshot is not None:
        if not isinstance(taste_snapshot, dict):
            raise ValueError("taste snapshot is invalid")
        if taste_snapshot.get("client_id") != plan["client_id"]:
            raise ValueError("taste snapshot violates client isolation")
        if int(taste_snapshot.get("profile_version", 0)) < 1 or not str(taste_snapshot.get("profile_hash") or ""):
            raise ValueError("taste snapshot is invalid")

    cursor = 0
    beat_ranges: dict[str, tuple[int, int]] = {}
    for beat in plan["beats"]:
        if beat["start_frame"] != cursor or beat["end_frame"] <= cursor:
            raise ValueError("beat coverage has a gap/overlap")
        cursor = beat["end_frame"]
        beat_ranges[str(beat["id"])] = (beat["start_frame"], beat["end_frame"])
        if beat["action"] not in ACTIONS:
            raise ValueError("unknown editorial action")
        selected = beat["selected_asset"]
        if selected and (selected["client_id"] != plan["client_id"] or selected not in beat["candidates"]):
            raise ValueError("selected asset violates client isolation")
        if any(item["client_id"] != plan["client_id"] for item in beat["candidates"]):
            raise ValueError("candidate violates client isolation")
        if beat["action"] == "BROLL" and selected is None:
            raise ValueError("BROLL requires a selected asset")
    if cursor != frames:
        raise ValueError("beat coverage does not reach source end")

    last_slot_end = 0
    for slot in sorted(plan.get("coverage_slots", []), key=lambda row: row["start_frame"]):
        start = slot.get("start_frame")
        end = slot.get("end_frame")
        if not isinstance(start, int) or not isinstance(end, int) or not (0 <= start < end <= frames):
            raise ValueError("coverage slot has invalid timing")
        if start < last_slot_end:
            raise ValueError("coverage slot overlap is not allowed")
        last_slot_end = end
        beat_range = beat_ranges.get(str(slot.get("beat_id")))
        if beat_range is None:
            raise ValueError("coverage slot references unknown beat")
        if start < beat_range[0] or end > beat_range[1]:
            raise ValueError("coverage slot falls outside owning beat")
        minimum_proposals = int(slot.get("minimum_proposals", 0))
        if minimum_proposals < 1:
            raise ValueError("coverage slot requires at least one proposal")

        route = slot.get("visual_route")
        if route is not None and route not in ROUTES:
            raise ValueError("coverage slot visual route is unsupported")
        if "route_confidence" in slot and not 0.0 <= float(slot["route_confidence"]) <= 1.0:
            raise ValueError("coverage slot route confidence is invalid")

        slot_taste_hash = slot.get("taste_profile_hash")
        slot_taste_version = slot.get("taste_profile_version")
        if slot_taste_hash is not None or slot_taste_version is not None:
            if taste_snapshot is None:
                raise ValueError("coverage slot taste snapshot has no top-level snapshot")
            if (
                str(slot_taste_hash) != str(taste_snapshot["profile_hash"])
                or int(slot_taste_version or 0) != int(taste_snapshot["profile_version"])
            ):
                raise ValueError("coverage slot taste snapshot does not match plan taste snapshot")

        proposal_ids: list[str] = []
        for key in ("proposal_A", "proposal_B", "proposal_C"):
            proposal = slot.get(key)
            if proposal is None:
                continue
            if not isinstance(proposal, dict) or not str(proposal.get("id") or ""):
                raise ValueError("coverage slot proposal is invalid")
            if proposal.get("client_id") not in {None, plan["client_id"]}:
                raise ValueError("coverage slot proposal violates client isolation")
            proposal_id = str(proposal["id"])
            if proposal_id in proposal_ids:
                raise ValueError("coverage slot proposals must be distinct")
            proposal_ids.append(proposal_id)

        selected_proposal_id = slot.get("selected_proposal_id")
        if selected_proposal_id is not None and str(selected_proposal_id) not in proposal_ids:
            raise ValueError("selected proposal is not present in coverage slot proposals")
        if slot.get("review_state") == "READY" and len(proposal_ids) < minimum_proposals:
            raise ValueError("coverage slot READY state lacks required proposals")
        if slot.get("evidence_intent"):
            if not isinstance(slot.get("source_strategy"), dict):
                raise ValueError("editorial coverage slot requires source strategy")
            if not isinstance(slot.get("searched_source_classes"), list):
                raise ValueError("editorial coverage slot requires searched source classes")
            if not isinstance(slot.get("rejected_candidates"), list):
                raise ValueError("editorial coverage slot requires rejected candidates")
            for key in ("proposal_A", "proposal_B", "proposal_C"):
                proposal = slot.get(key)
                if proposal is None:
                    continue
                if not proposal.get("recommended_presentation_mode") or not proposal.get("score_components"):
                    raise ValueError("editorial proposal requires presentation and score components")

    if not plan["captions"]:
        raise ValueError("captions missing")
    for caption in plan["captions"]:
        if not (0 <= caption["start_frame"] < caption["end_frame"] <= frames) or not caption["text"]:
            raise ValueError("caption has invalid timing/text")
