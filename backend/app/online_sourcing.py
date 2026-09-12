"""Online B-roll sourcing orchestration.

Searches remote providers concurrently, materializes only lightweight previews,
and feeds the bounded preview pool to the existing multimodal ranker.  Full
media download remains a later stage after selection.
"""

from __future__ import annotations

import asyncio
from typing import Any, Protocol

from .asset_cache import AssetCache, PreviewAsset, public_provenance
from .online_assets import ProviderError, RemoteCandidate, dedupe_candidates
from .qwen_stack import QwenMultimodalRanker


class OnlineSource(Protocol):
    async def search(
        self,
        query: str,
        *,
        orientation: str,
        min_duration: float,
        max_duration: float,
        limit: int,
    ) -> list[RemoteCandidate]: ...


class PreviewCache(Protocol):
    async def materialize_preview(self, candidate: RemoteCandidate) -> PreviewAsset: ...


class OnlineSourcingEngine:
    """Bounded online retrieval followed by one Qwen embedding batch per beat."""

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

    async def source_beat(
        self,
        *,
        beat_id: str,
        client_id: str,
        queries: list[str],
        min_duration: float,
        max_duration: float,
        orientation: str = "portrait",
    ) -> dict[str, Any]:
        clean_queries = [query.strip() for query in queries if isinstance(query, str) and query.strip()]
        if not beat_id or not client_id:
            raise ValueError("beat and client identity are required")
        if not clean_queries:
            return {"beat_id": beat_id, "queries": [], "candidates": [], "errors": [], "preview_cache_hits": 0}
        if len(clean_queries) > self.max_queries:
            raise ValueError(f"queries exceed max_queries={self.max_queries}")
        if min_duration < 0 or max_duration <= 0 or min_duration > max_duration:
            raise ValueError("invalid duration bounds")

        tasks = [
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
        outcomes = await asyncio.gather(*tasks)

        errors: list[dict[str, str]] = []
        remote: list[RemoteCandidate] = []
        for rows, error in outcomes:
            remote.extend(rows)
            if error is not None:
                errors.append(error)

        unique = dedupe_candidates(remote)[: self.max_preview_candidates]
        if not unique:
            return {
                "beat_id": beat_id,
                "queries": clean_queries,
                "candidates": [],
                "errors": _dedupe_errors(errors),
                "preview_cache_hits": 0,
            }

        semaphore = asyncio.Semaphore(self.preview_concurrency)

        async def materialize(candidate: RemoteCandidate):
            async with semaphore:
                return candidate, await self.cache.materialize_preview(candidate)

        preview_outcomes = await asyncio.gather(
            *(materialize(candidate) for candidate in unique),
            return_exceptions=True,
        )

        assets: list[dict[str, Any]] = []
        cache_hits = 0
        for outcome in preview_outcomes:
            if isinstance(outcome, BaseException):
                errors.append({"provider": "preview", "code": type(outcome).__name__})
                continue
            candidate, preview = outcome
            cache_hits += int(preview.cache_hit)
            provenance = public_provenance(candidate)
            creator = provenance.get("creator")
            assets.append(
                {
                    "id": f"{candidate.provider}:{candidate.provider_id}",
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
                    "creator": creator,
                    "rights_state": candidate.rights_state,
                    "query": candidate.query,
                    "selected_full_download": False,
                }
            )

        if not assets:
            return {
                "beat_id": beat_id,
                "queries": clean_queries,
                "candidates": [],
                "errors": _dedupe_errors(errors),
                "preview_cache_hits": cache_hits,
            }

        ranked = self.ranker.rank(clean_queries[0], assets)
        for row in ranked:
            row.setdefault("providers", {})["retrieval"] = row.get("source", "online")

        return {
            "beat_id": beat_id,
            "queries": clean_queries,
            "candidates": ranked,
            "errors": _dedupe_errors(errors),
            "preview_cache_hits": cache_hits,
        }

    async def _search_one(
        self,
        source: OnlineSource,
        query: str,
        *,
        orientation: str,
        min_duration: float,
        max_duration: float,
    ) -> tuple[list[RemoteCandidate], dict[str, str] | None]:
        try:
            rows = await source.search(
                query,
                orientation=orientation,
                min_duration=min_duration,
                max_duration=max_duration,
                limit=self.max_results_per_query,
            )
            return rows, None
        except ProviderError as exc:
            return [], {"provider": exc.provider, "code": exc.code}
        except Exception as exc:
            return [], {"provider": type(source).__name__, "code": type(exc).__name__}


def _dedupe_errors(errors: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    output = []
    for row in errors:
        key = (row["provider"], row["code"])
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output
