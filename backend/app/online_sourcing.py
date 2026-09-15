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

from pathlib import Path
from .video_preview import materialize_clip

from .evidence_intent import EvidenceIntent
from .source_strategy import SourceStrategy, plan_source_strategy
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
    seen: set[str] = set()
    output = []
    for value in values:
        if not isinstance(value, str):
            continue
        clean = " ".join(value.split())
        if clean and clean.casefold() not in seen:
            seen.add(clean.casefold())
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
        max_queries: int = 8,
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
        self._search_cache: dict[tuple[Any, ...], tuple[Any, ...]] = {}
        self._search_inflight: dict[tuple[Any, ...], asyncio.Task[list[Any]]] = {}
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
        evidence_intent: EvidenceIntent | None = None,
        source_strategy: SourceStrategy | None = None,
        retrieval_intent: str | None = None,
    ) -> dict[str, Any]:
        if getattr(self,'quality_mode',False):
            from .quality_video import source_video_beat
            return await source_video_beat(self,beat_id=beat_id,client_id=client_id,queries=queries,min_duration=min_duration,max_duration=max_duration,orientation=orientation,retrieval_intent=retrieval_intent)
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

        if evidence_intent is not None:
            if taste is None:
                raise ValueError("editorial sourcing requires a TasteContext")
            strategy = source_strategy or plan_source_strategy(evidence_intent, visual_route or "CONCEPT", taste)
            return await self._source_beat_editorial(
                beat_id=beat_id, client_id=client_id, queries=clean_queries,
                min_duration=min_duration, max_duration=max_duration, orientation=orientation,
                taste=taste, visual_route=visual_route, evidence_intent=evidence_intent,
                source_strategy=strategy,
            )

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
                "source_class": str(getattr(candidate, "source_class", "CLOSE_SEMANTIC_EDITORIAL")),
                "source_authenticity": getattr(candidate, "source_authenticity", None),
                "provider_id": candidate.provider_id,
                "creator": provenance.get("creator"),
                "rights_state": candidate.rights_state,
                "license_name": "Pexels License" if candidate.provider=="pexels" else None,
                "license_url": "https://www.pexels.com/license/" if candidate.provider=="pexels" else None,
                "attribution": (provenance.get("creator") or {}).get("name"),
                "query": candidate.query,
                "width": candidate.width,
                "height": candidate.height,
                "orientation": candidate.orientation,
                "selected_full_download": False,
                "scene_evidence": _scene_evidence_rows(candidate),
                "source_duration": float(getattr(candidate, "source_duration", candidate.duration)),
                "acquisition_mode": str(getattr(candidate, "acquisition_mode", "full_asset")),
            }
            from .media_quality import perceptual_hash
            try:
                asset['perceptual_hash'] = perceptual_hash(Path(preview.path))
            except (OSError, ValueError, ImportError):
                pass
            asset['preview_status'] = 'discovery'
            asset['poster_path'] = str(preview.path)
            if candidate.provider == 'pexels':
                try:
                    clip = await asyncio.to_thread(materialize_clip, getattr(candidate, 'preview_rendition_url', None) or candidate.selected_rendition_url, Path(preview.path).parent/'clips', asset_id)
                    asset.update(clip)
                    asset['kind'] = 'video'
                except Exception:
                    errors.append({'provider':'pexels','code':'video_preview_failed_discovery_only'})
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

        ranked = []
        for query in clean_queries:
            group = [a for a in assets if a.get('query') == query]
            if group:
                ranked.extend(self.ranker.rank(getattr(self, 'query_intents', {}).get(query, query), group))
        ranked.sort(key=lambda r: -float(r.get('score',0)))
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
                "source_class",
                "source_authenticity",
            ):
                row[key] = source_asset[key]
            for key in ('preview_path','poster_path','preview_status','preview_duration','preview_mime','perceptual_hash','kind','license_name','license_url','attribution'):
                if key in source_asset: row[key] = source_asset[key]
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

    async def _source_beat_editorial(
        self,
        *,
        beat_id: str,
        client_id: str,
        queries: list[str],
        min_duration: float,
        max_duration: float,
        orientation: str | None,
        taste: TasteContext,
        visual_route: str | None,
        evidence_intent: EvidenceIntent,
        source_strategy: SourceStrategy,
    ) -> dict[str, Any]:
        """Search source classes in order, stopping when distinct eligible A/B exist."""
        accumulated: dict[str, dict[str, Any]] = {}
        searched: list[str] = []
        unsupported: list[str] = []
        errors: list[dict[str, str]] = []
        cache_hits = 0
        chosen = select_proposals([], minimum=taste.default_proposal_count,
                                  taste=taste, evidence_intent=evidence_intent)
        for source_class in source_strategy.classes:
            if len(searched) >= self.max_queries or len(accumulated) >= self.max_preview_candidates:
                break
            compatible = [
                source for source in self.sources
                if source_class in tuple(getattr(source, "supported_source_classes", ("CLOSE_SEMANTIC_EDITORIAL",)))
            ]
            if not compatible:
                unsupported.append(source_class)
                continue
            query = source_strategy.query_families[source_class][0]
            round_engine = OnlineSourcingEngine(
                sources=compatible,
                cache=self.cache,
                ranker=self.ranker,
                max_results_per_query=self.max_results_per_query,
                max_preview_candidates=self.max_preview_candidates - len(accumulated),
                max_queries=1,
                preview_concurrency=self.preview_concurrency,
                download_selected=False,
            )
            round_engine._search_cache = self._search_cache
            round_engine._search_inflight = self._search_inflight
            outcome = await round_engine.source_beat(
                beat_id=beat_id, client_id=client_id, queries=[query],
                min_duration=min_duration, max_duration=max_duration,
                orientation=orientation,
            )
            searched.append(source_class)
            errors.extend(outcome["errors"])
            cache_hits += int(outcome["preview_cache_hits"])
            for candidate in outcome["candidates"]:
                if candidate.get("source_class") != source_class:
                    continue
                # A thumbnail score cannot certify a long-video insert. Only a
                # score computed from the final selected window can pass the gate.
                if (candidate.get("acquisition_mode") == "bounded_window"
                        and candidate.get("final_segment_semantic_score") is None):
                    candidate["final_segment_semantic_score"] = 0.0
                accumulated.setdefault(str(candidate["id"]), candidate)
            chosen = select_proposals(
                list(accumulated.values()), minimum=taste.default_proposal_count,
                taste=taste, visual_route=visual_route, evidence_intent=evidence_intent,
            )
            if chosen["review_state"] == "READY":
                break
        for key in ("proposal_A", "proposal_B", "proposal_C"):
            proposal = chosen.get(key)
            if isinstance(proposal, dict):
                _localize_proposal_scene(proposal, queries[0])
        rejected = chosen.get("rejected_candidates", [])
        return {
            "beat_id": beat_id,
            "queries": queries,
            "candidates": list(accumulated.values()),
            "proposals": chosen,
            "visual_route": visual_route,
            "evidence_intent": asdict(evidence_intent),
            "source_strategy": {
                "classes": list(source_strategy.classes),
                "query_families": {key: list(value) for key, value in source_strategy.query_families.items()},
            },
            "searched_source_classes": searched,
            "unsupported_source_classes": unsupported,
            "rejected_candidates": rejected,
            "quality_floor_state": chosen["review_state"] if "QUALITY_FLOOR" in chosen["review_state"] else None,
            "eligible_candidate_count": chosen["usable_candidate_count"],
            "rejected_candidate_count": len(rejected),
            "source_class_search_rounds": len(searched),
            "generic_stock_selected_count": sum(
                int(isinstance(chosen.get(key), dict) and chosen[key].get("source_class") == "GENERIC_STOCK")
                for key in ("proposal_A", "proposal_B")
            ),
            "distinct_proposal_source_count": len({
                chosen[key].get("provider_id")
                for key in ("proposal_A", "proposal_B")
                if isinstance(chosen.get(key), dict)
            }),
            "taste_profile_version": taste.profile_version,
            "taste_profile_hash": taste.profile_hash,
            "errors": _dedupe_errors(errors),
            "preview_cache_hits": cache_hits,
            "selected_cache_hit": False,
            "resolve_calls": 0,
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
        evidence_intent: EvidenceIntent | None = None,
        source_strategy: SourceStrategy | None = None,
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
        cache_key = (id(source), query.casefold(), orientation,
                     float(min_duration), float(max_duration), self.max_results_per_query)
        cached = self._search_cache.get(cache_key)
        if cached is not None:
            return list(cached), None
        task: asyncio.Task[list[Any]] | None = None
        try:
            task = self._search_inflight.get(cache_key)
            if task is None:
                task = asyncio.create_task(source.search(
                    query, orientation=orientation, min_duration=min_duration,
                    max_duration=max_duration, limit=self.max_results_per_query,
                ))
                self._search_inflight[cache_key] = task
            rows = await task
            if len(self._search_cache) >= self._search_cache_max_entries:
                self._search_cache.pop(next(iter(self._search_cache)))
            self._search_cache[cache_key] = tuple(rows)
            return list(rows), None
        except ProviderError as exc:
            return [], {"provider": exc.provider, "code": exc.code}
        except Exception as exc:
            return [], {"provider": type(source).__name__, "code": type(exc).__name__}
        finally:
            if task is not None and self._search_inflight.get(cache_key) is task:
                self._search_inflight.pop(cache_key, None)


def _dedupe_errors(errors: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    output = []
    for row in errors:
        key = (row["provider"], row["code"])
        if key not in seen:
            seen.add(key)
            output.append(row)
    return output
