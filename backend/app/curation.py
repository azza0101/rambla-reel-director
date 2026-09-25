from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


CandidateKind = Literal["video", "image"]
VERTICAL_SOCIAL_PROVIDERS = {"youtube_shorts", "tiktok", "instagram"}


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
    preview_url: str | None = None
    license_name: str | None = None
    license_url: str | None = None
    attribution: str | None = None
    shot_id: str | None = None
    matched_query: str | None = None
    quality_state: str | None = None
    clip_verified: bool = False
    quality_reasons: tuple[str, ...] = ()
    acquisition_state: str | None = None
    manual_reason: str | None = None


@dataclass(frozen=True, slots=True)
class CandidateShelf:
    video: tuple[CurationCandidate, ...]
    images: tuple[CurationCandidate, ...]
    social: tuple[CurationCandidate, ...] = ()
    stock: tuple[CurationCandidate, ...] = ()
    vertical_social: tuple[CurationCandidate, ...] = ()
    general_social: tuple[CurationCandidate, ...] = ()


def build_candidate_shelf(
    rows: list[CurationCandidate], *, video_limit: int = 3, image_limit: int = 4, social_limit: int | None = None
) -> CandidateShelf:
    if video_limit < 0 or image_limit < 0:
        raise ValueError("curation shelf limits must be non-negative")
    social_limit = video_limit if social_limit is None else social_limit
    if social_limit < 0: raise ValueError("social_limit must be non-negative")
    seen: set[tuple[str, str]] = set()
    ordered: list[CurationCandidate] = []
    for row in sorted(rows, key=lambda item: (-item.score, item.asset_id)):
        key = (row.kind, row.source_page.casefold())
        if key not in seen:
            seen.add(key)
            ordered.append(row)

    def balanced(bucket: list[CurationCandidate], limit: int) -> tuple[CurationCandidate, ...]:
        primary=[]; remaining=[]; shots=set()
        for row in bucket:
            if row.shot_id not in shots:
                primary.append(row); shots.add(row.shot_id)
            else:
                remaining.append(row)
        return tuple((primary+remaining)[:limit])

    videos=[r for r in ordered if r.kind=='video']
    shorts=balanced([r for r in videos if r.provider=='youtube_shorts' and r.orientation=='portrait'],social_limit)
    tiktok=balanced([r for r in videos if r.provider=='tiktok' and r.orientation=='portrait'],social_limit)
    instagram=balanced([r for r in videos if r.provider=='instagram' and r.orientation=='portrait'],social_limit)
    web=balanced([r for r in videos if r.provider=='web_video'],video_limit)
    envato=balanced([r for r in videos if r.provider=='envato'],video_limit)
    general=balanced([r for r in videos if r.provider not in {'pexels','envato','web_video'} and r.provider not in VERTICAL_SOCIAL_PROVIDERS],video_limit)
    stock=balanced([r for r in videos if r.provider=='pexels'],video_limit)
    images=balanced([r for r in ordered if r.kind=='image'],image_limit)
    vertical=tuple(sorted((*shorts,*tiktok,*instagram),key=lambda row:(-row.score,row.asset_id)))
    social=vertical+web+general
    # Each UI shelf gets its own bounded candidate budget. TikTok, Instagram and
    # Shorts must not evict one another before the curator can compare them; the
    # legacy aggregate vertical_social still remains globally score-ordered.
    return CandidateShelf(video=vertical+web+general+envato+stock,images=images,social=social,stock=stock,vertical_social=vertical,general_social=web+general)
