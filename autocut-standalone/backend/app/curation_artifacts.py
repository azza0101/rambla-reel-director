from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

from .video_preview import probe_preview

from .curation import CurationCandidate, build_candidate_shelf


@dataclass(frozen=True, slots=True)
class CurationChunkView:
    chunk_id: str
    text: str
    video_candidates: tuple[CurationCandidate, ...]
    image_candidates: tuple[CurationCandidate, ...]


@dataclass(frozen=True, slots=True)
class CurationRunView:
    chunks: tuple[CurationChunkView, ...]
    candidate_index: dict[str, CurationCandidate]
    errors: tuple[str, ...] = ()


def _video_candidate(cid: str, row: dict, *, discovery: bool = False) -> CurationCandidate:
    preview_path = row.get("preview_path")
    playable = probe_preview(preview_path)["playable"] if preview_path else False
    poster = row.get("poster_path") or (preview_path if preview_path and not playable else None)
    remote_preview = None if preview_path else row.get("preview_url") or row.get("thumbnail_url")
    clip_verified = bool(row.get("clip_verified")) and playable
    explicit_status = str(row.get("preview_status") or "").strip()
    if clip_verified:
        acquisition_state = "CLIP_READY"
        preview_status = "ready"
    else:
        acquisition_state = str(row.get("acquisition_state") or ("PREVIEW_ONLY" if (preview_path or remote_preview) else "MANUAL_LINK"))
        if explicit_status in {"preview_pending", "manual", "discovery"}:
            preview_status = explicit_status
        elif discovery:
            preview_status = "preview_pending" if (preview_path or remote_preview) else "manual"
        else:
            # Legacy candidate rows used a thumbnail as discovery evidence only.
            # Never silently upgrade those old artifacts to PREVIEW_ONLY just
            # because a local JPEG path exists.
            preview_status = "discovery"
    provider = str(row.get("source") or row.get("provider") or "online")
    provider_id = str(row.get("provider_id") or row.get("id") or "source")
    asset_id = f"{cid}--{row.get('id') or provider + ':' + provider_id}"
    title = str(row.get("title") or row.get("description") or row.get("id") or provider)
    return CurationCandidate(
        asset_id, cid, "video", provider, str(row.get("source_page") or row.get("source_url") or ""),
        title, str(row.get("description") or title), float(row.get("score", 0.0)),
        str(row.get("rights_state") or "review_required"), str(row.get("orientation") or "unknown"),
        preview_path=preview_path, poster_path=poster,
        preview_status=preview_status,
        local_asset_path=preview_path if playable else None,
        preview_url=remote_preview,
        license_name=row.get("license_name"), license_url=row.get("license_url"),
        attribution=row.get("attribution") or row.get("creator_name"),
        shot_id=row.get("shot_id"), matched_query=row.get("matched_query", row.get("query")),
        quality_state=row.get("quality_state") or ("source_found" if discovery else None),
        clip_verified=clip_verified, quality_reasons=tuple(row.get("quality_reasons", [])),
        source_start_seconds=row.get("source_start_seconds"), source_end_seconds=row.get("source_end_seconds"),
        acquisition_state=acquisition_state, manual_reason=row.get("manual_reason"),
    )


def load_curation_run(run_dir: Path) -> CurationRunView:
    chunks = json.loads((run_dir / "semantic-chunks.json").read_text(encoding="utf-8"))
    from .editorial_import import retrieval_bundle, VERSION
    plan_path = run_dir / 'visual-plan.json'
    imported = plan_path.is_file() and json.loads(plan_path.read_text(encoding='utf-8')).get('schema_version') == VERSION
    if imported:
        run_dir, chunks, _, _ = retrieval_bundle(run_dir)
    online = json.loads((run_dir / "online-candidates.json").read_text(encoding="utf-8")) if (run_dir / "online-candidates.json").is_file() else []
    images = json.loads((run_dir / "image-candidates.json").read_text(encoding="utf-8")) if (run_dir / "image-candidates.json").is_file() else {"chunks": {}}
    errors=[]
    if imported:
        from .retrieval_quality import VERSION as QUALITY_VERSION
        from .quality_video import QUALITY_VERSION as VIDEO_QUALITY_VERSION
        if images.get('chunks') and images.get('schema_version') != QUALITY_VERSION:
            errors.append('Image retrieval predates quality filtering: rerun image search.')
            images={'chunks':{}}
        if any(slot.get('quality_version')!=VIDEO_QUALITY_VERSION for slot in online):
            errors.append('Video retrieval predates clip verification: rerun video search.')
            online=[slot for slot in online if slot.get('quality_version')==VIDEO_QUALITY_VERSION]
    from .envato_download_bridge import load_registry
    envato_downloads = load_registry(run_dir)["assets"]
    found: dict[str, list[CurationCandidate]] = {}
    for slot in online:
        cid = slot.get("parent_beat_id")
        if not cid:
            continue
        seen_ids: set[str] = set()
        for row in slot.get("candidates", []):
            if not isinstance(row, dict):
                continue
            candidate = _video_candidate(str(cid), row)
            downloaded = envato_downloads.get(candidate.asset_id) if candidate.provider == "envato" else None
            downloaded_path = Path(str((downloaded or {}).get("media_path") or ""))
            if downloaded_path.is_file() and probe_preview(downloaded_path)["playable"]:
                candidate = replace(
                    candidate,
                    local_asset_path=str(downloaded_path.resolve()),
                    clip_verified=True,
                    acquisition_state="CLIP_READY",
                    preview_status="ready",
                )
            seen_ids.add(candidate.asset_id)
            found.setdefault(str(cid), []).append(candidate)
        # Discovery is intentionally kept separate from final verified candidates.
        # It is still valuable for TikTok/Instagram/news: a failed automatic
        # download must remain visible as PREVIEW_ONLY or MANUAL_LINK.
        for row in slot.get("discovery_sources", []):
            if not isinstance(row, dict):
                continue
            candidate = _video_candidate(str(cid), row, discovery=True)
            if candidate.asset_id in seen_ids:
                continue
            seen_ids.add(candidate.asset_id)
            found.setdefault(str(cid), []).append(candidate)
    for cid, value in images.get("chunks", {}).items():
        for row in value.get("candidates", []):
            found.setdefault(cid, []).append(CurationCandidate(f"{cid}--{row['provider']}:{row['provider_id']}", cid, "image", row["provider"], row["source_page"], row["title"], row.get("description", ""), float(row.get("score", 0.0)), row["rights_state"], row["orientation"], preview_path=row.get("preview_path"), local_asset_path=row.get("preview_path"), preview_url=None if row.get("preview_path") else row.get("thumbnail_url") or row.get("full_url"),license_name=row.get("license_name"),license_url=row.get("license_url"),attribution=row.get("attribution"),shot_id=row.get("shot_id"),matched_query=row.get("matched_query",row.get("query")),quality_state=row.get("quality_state"),clip_verified=bool(row.get("clip_verified")),quality_reasons=tuple(row.get("quality_reasons",[])),source_start_seconds=row.get("source_start_seconds"),source_end_seconds=row.get("source_end_seconds")))
    views=[]; index={}
    for row in chunks:
        # Keep the accumulated provider pages available to the UI gallery.
        # Pagination is a presentation concern; truncating stock here made
        # every successful "Cerca altre 6" round appear to find nothing.
        shelf=build_candidate_shelf(found.get(row["id"], []), video_limit=96, social_limit=96)
        for candidate in (*shelf.video,*shelf.images): index[candidate.asset_id]=candidate
        views.append(CurationChunkView(row["id"],row.get("text", ""),shelf.video,shelf.images))
    return CurationRunView(tuple(views),index,tuple(errors))
