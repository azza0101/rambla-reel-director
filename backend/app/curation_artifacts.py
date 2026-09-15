from __future__ import annotations

import json
from dataclasses import dataclass
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


def load_curation_run(run_dir: Path) -> CurationRunView:
    chunks = json.loads((run_dir / "semantic-chunks.json").read_text(encoding="utf-8"))
    online = json.loads((run_dir / "online-candidates.json").read_text(encoding="utf-8")) if (run_dir / "online-candidates.json").is_file() else []
    images = json.loads((run_dir / "image-candidates.json").read_text(encoding="utf-8")) if (run_dir / "image-candidates.json").is_file() else {"chunks": {}}
    found: dict[str, list[CurationCandidate]] = {}
    for slot in online:
        cid = slot.get("parent_beat_id")
        for row in slot.get("candidates", []):
            playable = probe_preview(row.get('preview_path'))['playable']
            poster = row.get('poster_path') or (row.get('preview_path') if not playable else None)
            found.setdefault(cid, []).append(CurationCandidate(f"{cid}--{row['id']}", cid, "video", str(row.get("source", "online")), str(row.get("source_page", "")), str(row.get("description", row["id"])), str(row.get("description", "")), float(row.get("score", 0)), str(row.get("rights_state", "review_required")), str(row.get("orientation", "unknown")), preview_path=row.get("preview_path"), poster_path=poster, preview_status="ready" if playable else "discovery", local_asset_path=row.get("preview_path") if playable else None))
    for cid, value in images.get("chunks", {}).items():
        for row in value.get("candidates", []):
            found.setdefault(cid, []).append(CurationCandidate(f"{cid}--{row['provider']}:{row['provider_id']}", cid, "image", row["provider"], row["source_page"], row["title"], row.get("description", ""), float(row.get("score", 0.0)), row["rights_state"], row["orientation"], preview_path=row.get("preview_path"), local_asset_path=row.get("preview_path"), preview_url=None if row.get("preview_path") else row.get("thumbnail_url") or row.get("full_url")))
    views=[]; index={}
    for row in chunks:
        shelf=build_candidate_shelf(found.get(row["id"], []))
        for candidate in (*shelf.video,*shelf.images): index[candidate.asset_id]=candidate
        views.append(CurationChunkView(row["id"],row.get("text", ""),shelf.video,shelf.images))
    return CurationRunView(tuple(views),index)
