"""Deterministic, Resolve-independent Director Engine for offline review plans."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Protocol


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
    """Credential boundary; never silently invokes a cloud service."""

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
            rows.append({"id": asset["id"], "client_id": asset["client_id"], "path": asset["path"],
                         "description": asset.get("description", ""), "kind": asset.get("kind", "unknown"),
                         "score": score, "embedding_score": None, "reranker_score": None,
                         "providers": {"embedding": None, "reranker": None, "retrieval": "metadata-overlap-v1"},
                         "reason": f"metadata overlap: {', '.join(matched) or 'none'}"})
        return sorted(rows, key=lambda row: (-row["score"], row["id"]))


class RuleDirector:
    def decide(self, beat: dict[str, Any], selected: dict[str, Any] | None) -> tuple[str, str, dict[str, Any]]:
        intent = beat["intent"].lower()
        if selected is not None:
            return "BROLL", "Client-local visual evidence matches the semantic intent.", {"fit": "COVER"}
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
                if len(text) >= 42 or word["end"] - current[0]["start"] >= 3 or word["text"].strip().endswith((".", "?", "!")):
                    chunks.append(current)
                    current = []
            if current:
                chunks.append(current)
            for chunk in chunks:
                text = " ".join(item["text"].strip() for item in chunk).strip()
                captions.append({"start_frame": _frame(chunk[0]["start"], fps),
                                 "end_frame": min(source_frames, max(_frame(chunk[-1]["end"], fps), _frame(chunk[0]["start"], fps) + 1)),
                                 "text": text, "emphasis_candidates": [], "review_state": "ASR_UNREVIEWED"})
        else:
            text = segment["text"].strip()
            captions.append({"start_frame": _frame(segment["start"], fps),
                             "end_frame": min(source_frames, max(_frame(segment["end"], fps), _frame(segment["start"], fps) + 1)),
                             "text": text, "emphasis_candidates": [], "review_state": "ASR_UNREVIEWED"})
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


def build_edit_plan(
    transcript: dict[str, Any], beat_outline: dict[str, Any], assets: list[dict[str, Any]],
    *, client_id: str, source_frames: int, director: DirectorAdapter | None = None,
    reranker: Reranker | None = None,
) -> dict[str, Any]:
    fps = int(transcript["timeline_fps"])
    if fps <= 0 or source_frames <= 0 or not client_id:
        raise ValueError("source timing and client identity required")
    director = director or RuleDirector()
    reranker = reranker or TextReranker()
    local_assets = LocalAssetProvider(assets).list_assets(client_id)
    captions = _captions(transcript, fps, source_frames)
    beats = []
    for outline, (start, end) in zip(beat_outline["beats"], _outline_ranges(beat_outline, fps, source_frames)):
        query = (outline.get("broll_queries") or [""])[0]
        semantic_query = f"{outline['intent']}; {query}" if query else ""
        candidates = reranker.rank(query, local_assets) if query else []
        selected = candidates[0] if candidates and candidates[0]["score"] >= 0.7 else None
        action, rationale, metadata = director.decide(outline, selected)
        if action != "BROLL":
            selected = None
        provider_name = getattr(director, "last_provider", "deterministic-rule-v1")
        candidate_providers = candidates[0].get("providers", {}) if candidates else {}
        beat_captions = [row["text"] for row in captions if row["start_frame"] < end and row["end_frame"] > start]
        beats.append({"id": outline["id"], "start_frame": start, "end_frame": end, "intent": outline["intent"],
                      "transcript": " ".join(segment["text"].strip() for segment in transcript["segments"]
                                             if _frame(segment["start"], fps) < end and _frame(segment["end"], fps) > start),
                      "action": action, "rationale": rationale, "parameters": metadata,
                      "broll_query": semantic_query, "selected_asset": selected, "candidates": candidates,
                      "providers": {"director": provider_name,
                                    "embedding": candidate_providers.get("embedding"),
                                    "reranker": candidate_providers.get("reranker"),
                                    "retrieval": candidate_providers.get("retrieval", "client-local")},
                      "caption_text": " ".join(beat_captions)})
    plan = {"schema_version": "director-offline-1", "status": "DRAFT", "client_id": client_id,
            "source": {"media": transcript.get("source", ""), "fps": fps, "start_frame": transcript.get("timeline_start_frame", 0), "duration_frames": source_frames},
            "asr": {"adapter": "faster-whisper-artifact", "language": transcript.get("language", "und"), "review_state": "UNREVIEWED"},
            "director": {"adapter": getattr(director, "provider_name", "deterministic-rule-v1")},
            "retrieval": {"local_client_only": True, "external": "credential-gated"},
            "beats": beats, "captions": captions}
    validate_edit_plan(plan)
    canonical = json.dumps(plan, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    plan["content_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return plan


def validate_edit_plan(plan: dict[str, Any]) -> None:
    if plan.get("schema_version") != "director-offline-1" or plan.get("status") != "DRAFT":
        raise ValueError("unsupported offline plan schema/status")
    frames = plan["source"]["duration_frames"]
    if not isinstance(frames, int) or frames <= 0 or plan["source"]["fps"] <= 0:
        raise ValueError("invalid source timebase")
    cursor = 0
    for beat in plan["beats"]:
        if beat["start_frame"] != cursor or beat["end_frame"] <= cursor:
            raise ValueError("beat coverage has a gap/overlap")
        cursor = beat["end_frame"]
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
    if not plan["captions"]:
        raise ValueError("captions missing")
    for caption in plan["captions"]:
        if not (0 <= caption["start_frame"] < caption["end_frame"] <= frames) or not caption["text"]:
            raise ValueError("caption has invalid timing/text")
