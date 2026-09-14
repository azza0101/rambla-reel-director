"""Online B-roll/evidence sourcing orchestration.

Searches providers concurrently, materializes lightweight previews, Qwen-ranks
a bounded mixed-source pool, exposes diverse crop-aware A/B proposals, and
localizes promising short windows inside long-video candidates before any
large acquisition occurs.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any, Protocol

from .asset_cache import AssetCache, CachedAsset, PreviewAsset, public_provenance
from .online_assets import ProviderError, RemoteCandidate, dedupe_candidates
from .proposals import select_proposals
from .qwen_stack import QwenMultimodalRanker
from .scene_locator import SceneEvidence, locate_windows
from .taste_profile import TasteContext


class OnlineSource(Protocol):
    async def search(
        self,
        query: str,
        *,
        orientation: str | None,
        min_duration: float,
        max_duration: float,
        limit: int,
    ) -> list[Any]: ...


class PreviewCache(Protocol):
    async def materialize_preview(self, candidate: Any) -> PreviewAsset: ...


def _normalize_queries(values: list[str]) -> list[str]:
    """Strip whitespace and remove equivalent queries while preserving priority."""

    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        clean = " ".join(value.split())
        if not clean:
            continue
        key = clean.casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(clean)
    return output


def _scene_evidence_rows(candidate: Any) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in getattr(candidate, "scene_evidence", ()) or ():
        if isinstance(row, SceneEvidence):
            output.append(asdict(row))
        elif isinstance(row, dict):
            output.append(dict(row))
    return output


def _localize_proposal_scene(proposal: dict[str, Any], query: str) -> None:
    raw = proposal.get("scene_evidence") or []
    source_duration = float(proposal.get("source_duration") or 0.0)
    if not raw or source_duration <= 0:
        return
    evidence: list[SceneEvidence] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        try:
            evidence.append(
                SceneEvidence(
                    timestamp_seconds=float(row["timestamp_seconds"]),
                    text=str(row.get("text") or ""),
                    image_path=(str(row["image_path"]) if row.get("image_path") else None),
                    metadata_score=float(row.get("metadata_score", 0.0)),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    if not evidence:
        return
    windows = locate_windows(
        query,
        evidence,
        target_seconds=3.5,
        source_duration=source_duration,
    )
    if not windows:
        return
    best = windows[0]
    proposal["source_start_seconds"] = best.start_seconds
    proposal["source_end_seconds"] = best.end_seconds
    proposal["scene_window_score"] = best.score
    proposal["scene_evidence_timestamps"] = list(best.evidence_timestamps)


class OnlineSourcingEngine:
    def __init__(
        self,
        *,
        sources: list[OnlineSource],
        cache: AssetCache | PreviewCache,
        ranker: QwenMultimodalRanker,
        max_results_per_query: int = 12,
        max_preview_candidates: int = 12,
        max_queries: int = 4,
        preview_concurrency: int = 6,
        download_selected: bool = False,
    ):
        if not sources:
            raise ValueError("at least one online source is required")
        if min(max_results_per_query, max_preview_candidates, max_queries, preview_concurrency) <= 0:
            raise ValueError("online sourcing bounds must be positive")
        self.sources = list(sources)
        self.cache = cache
        self.ranker = ranker
        self.max_results_per_query = max_results_per_query
        self.max_preview_candidates = max_preview_candidates
        self.max_queries = max_queries
        self.preview_concurrency = preview_concurrency
        self.download_selected = download_selected
        self._search_cache: dict[
            tuple[int, str, str | None, float, float, int], tuple[Any, ...]
        ] = {}
        self._search_cache_max_entries = 256

    async def source_beat(
        self,
        *,
        beat_id: str,
        client_id: str,
        queries: list[str],
        min_duration: float,
        max_duration: float,
        orientation: str | None = None,
        taste: TasteContext | None = None,
        visual_route: str | None = None,
    ) -> dict[str, Any]:
        clean_queries = _normalize_queries(queries)
        if not beat_id or not client_id:
            raise ValueError("beat and client identity are required")
        if taste is not None and taste.client_id != client_id:
            raise ValueError("taste context violates client isolation")
        if not clean_queries:
            return self._empty(beat_id, [], [], taste=taste, visual_route=visual_route)
        if len(clean_queries) > self.max_queries:
            raise ValueError(f"queries exceed max_queries={self.max_queries}")
        if orientation is not None and orientation not in {"portrait", "landscape", "square"}:
            raise ValueError("unsupported orientation")
        if min_duration < 0 or max_duration <= 0 or min_duration > max_duration:
            raise ValueError("invalid duration bounds")

        outcomes = await asyncio.gather(
            *[
                self._search_one(
                    source,
                    query,
                    orientation=orientation,
                    min_duration=min_duration,
                    max_duration=max_duration,
                )
                for query in clean_queries
                for source in self.sources
            ]
        )
        errors: list[dict[str, str]] = []
        remote: list[Any] = []
        for rows, error in outcomes:
            remote.extend(rows)
            if error:
                errors.append(error)
        unique = dedupe_candidates(remote)[: self.max_preview_candidates]
        if not unique:
            return self._empty(
                beat_id,
                clean_queries,
                errors,
                taste=taste,
                visual_route=visual_route,
            )

        semaphore = asyncio.Semaphore(self.preview_concurrency)

        async def materialize(candidate: Any):
            async with semaphore:
                return candidate, await self.cache.materialize_preview(candidate)

        preview_outcomes = await asyncio.gather(
            *(materialize(candidate) for candidate in unique), return_exceptions=True
        )
        assets: list[dict[str, Any]] = []
        candidate_by_id: dict[str, Any] = {}
        asset_by_id: dict[str, dict[str, Any]] = {}
        cache_hits = 0
        for outcome in preview_outcomes:
            if isinstance(outcome, BaseException):
                errors.append({"provider": "preview", "code": type(outcome).__name__})
                continue
            candidate, preview = outcome
            cache_hits += int(preview.cache_hit)
            asset_id = f"{candidate.provider}:{candidate.provider_id}"
            candidate_by_id[asset_id] = candidate
            provenance = public_provenance(candidate)
            asset = {
                "id": asset_id,
                "client_id": client_id,
                "path": str(preview.path),
                "keyframe_path": str(preview.path),
                "preview_path": str(preview.path),
                "preview_sha256": preview.sha256,
                "description": " ".join(
                    part for part in (candidate.title, candidate.description) if part
                ).strip(),
                "kind": "image",
                "source": candidate.provider,
                "source_page": candidate.source_page,
                "provider_id": candidate.provider_id,
                "creator": provenance.get("creator"),
                "rights_state": candidate.rights_state,
                "query": candidate.query,
                "width": candidate.width,
                "height": candidate.height,
                "orientation": candidate.orientation,
                "selected_full_download": False,
                "scene_evidence": _scene_evidence_rows(candidate),
                "source_duration": float(getattr(candidate, "source_duration", candidate.duration)),
                "acquisition_mode": str(getattr(candidate, "acquisition_mode", "full_asset")),
            }
            # Stock is intrinsically a STOCK route. Other providers may expose a
            # more precise route through the ranker/adapter; absent that, the
            # requested route remains selection context rather than fabricated
            # candidate evidence.
            if str(candidate.provider).casefold() in {"pexels", "pixabay", "coverr"}:
                asset["route"] = "STOCK"
            assets.append(asset)
            asset_by_id[asset_id] = asset
        if not assets:
            return self._empty(
                beat_id,
                clean_queries,
                errors,
                cache_hits,
                taste=taste,
                visual_route=visual_route,
            )

        ranked = self.ranker.rank(clean_queries[0], assets)
        for row in ranked:
            source_asset = asset_by_id[row["id"]]
            for key in (
                "width",
                "height",
                "orientation",
                "preview_sha256",
                "scene_evidence",
                "source_duration",
                "acquisition_mode",
            ):
                row[key] = source_asset[key]
            if "route" in source_asset:
                row.setdefault("route", source_asset["route"])
            row.setdefault("providers", {})["retrieval"] = row.get("source", "online")

        minimum = taste.default_proposal_count if taste is not None else 2
        proposals = select_proposals(
            ranked,
            minimum=minimum,
            taste=taste,
            visual_route=visual_route,
        )
        for key in ("proposal_A", "proposal_B", "proposal_C"):
            proposal = proposals.get(key)
            if isinstance(proposal, dict):
                _localize_proposal_scene(proposal, clean_queries[0])

        selected_cache_hit = False
        selected = proposals["proposal_A"]
        direct_full_asset = (
            selected is not None
            and selected.get("acquisition_mode", "full_asset") != "bounded_window"
        )
        if (
            self.download_selected
            and direct_full_asset
            and hasattr(self.cache, "materialize_selected")
        ):
            candidate = candidate_by_id.get(selected["id"])
            if candidate is not None:
                try:
                    cached: CachedAsset = await self.cache.materialize_selected(candidate)  # type: ignore[attr-defined]
                    update = {
                        "path": str(cached.path),
                        "kind": "video",
                        "content_sha256": cached.sha256,
                        "selected_full_download": True,
                    }
                    selected.update(update)
                    for row in ranked:
                        if row["id"] == selected["id"]:
                            row.update(update)
                            break
                    selected_cache_hit = cached.cache_hit
                except Exception as exc:
                    errors.append(
                        {
                            "provider": candidate.provider,
                            "code": f"selected_download_{type(exc).__name__}",
                        }
                    )

        return {
            "beat_id": beat_id,
            "queries": clean_queries,
            "candidates": ranked,
            "proposals": proposals,
            "visual_route": visual_route,
            "taste_profile_version": taste.profile_version if taste is not None else None,
            "taste_profile_hash": taste.profile_hash if taste is not None else None,
            "errors": _dedupe_errors(errors),
            "preview_cache_hits": cache_hits,
            "selected_cache_hit": selected_cache_hit,
        }

    def _empty(
        self,
        beat_id: str,
        queries: list[str],
        errors: list[dict[str, str]],
        cache_hits: int = 0,
        *,
        taste: TasteContext | None = None,
        visual_route: str | None = None,
    ) -> dict[str, Any]:
        minimum = taste.default_proposal_count if taste is not None else 2
        return {
            "beat_id": beat_id,
            "queries": queries,
            "candidates": [],
            "proposals": select_proposals(
                [],
                minimum=minimum,
                taste=taste,
                visual_route=visual_route,
            ),
            "visual_route": visual_route,
            "taste_profile_version": taste.profile_version if taste is not None else None,
            "taste_profile_hash": taste.profile_hash if taste is not None else None,
            "errors": _dedupe_errors(errors),
            "preview_cache_hits": cache_hits,
            "selected_cache_hit": False,
        }

    async def _search_one(
        self,
        source: OnlineSource,
        query: str,
        *,
        orientation: str | None,
        min_duration: float,
        max_duration: float,
    ) -> tuple[list[Any], dict[str, str] | None]:
        cache_key = (
            id(source),
            query.casefold(),
            orientation,
            float(min_duration),
            float(max_duration),
            self.max_results_per_query,
        )
        cached = self._search_cache.get(cache_key)
        if cached is not None:
            return list(cached), None

        try:
            rows = await source.search(
                query,
                orientation=orientation,
                min_duration=min_duration,
                max_duration=max_duration,
                limit=self.max_results_per_query,
            )
            if len(self._search_cache) >= self._search_cache_max_entries:
                self._search_cache.pop(next(iter(self._search_cache)))
            self._search_cache[cache_key] = tuple(rows)
            return list(rows), None
        except ProviderError as exc:
            return [], {"provider": exc.provider, "code": exc.code}
        except Exception as exc:
            return [], {"provider": type(source).__name__, "code": type(exc).__name__}


def _dedupe_errors(errors: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    output = []
    for row in errors:
        key = (row["provider"], row["code"])
        if key not in seen:
            seen.add(key)
            output.append(row)
    return output
