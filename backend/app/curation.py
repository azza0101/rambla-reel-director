from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


CandidateKind = Literal["video", "image"]


@dataclass(frozen=True, slots=True)
class CurationCandidate:
    asset_id: str
    chunk_id: str
    kind: CandidateKind
    provider: str
    source_page: str
    title: str
    description: str
    score: float
    rights_state: str
    orientation: str
    source_start_seconds: float | None = None
    source_end_seconds: float | None = None
    preview_path: str | None = None
    poster_path: str | None = None
    local_asset_path: str | None = None
    preview_status: str = "pending"
    preview_error: str | None = None


@dataclass(frozen=True, slots=True)
class CandidateShelf:
    video: tuple[CurationCandidate, ...]
    images: tuple[CurationCandidate, ...]


def build_candidate_shelf(
    rows: list[CurationCandidate], *, video_limit: int = 3, image_limit: int = 4
) -> CandidateShelf:
    if video_limit < 0 or image_limit < 0:
        raise ValueError("curation shelf limits must be non-negative")
    seen: set[tuple[str, str]] = set()
    ordered: list[CurationCandidate] = []
    for row in sorted(rows, key=lambda item: (-item.score, item.asset_id)):
        key = (row.kind, row.source_page.casefold())
        if key not in seen:
            seen.add(key)
            ordered.append(row)
    return CandidateShelf(
        video=tuple(row for row in ordered if row.kind == "video")[:video_limit],
        images=tuple(row for row in ordered if row.kind == "image")[:image_limit],
    )
