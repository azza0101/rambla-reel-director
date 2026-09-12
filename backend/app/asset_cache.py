"""Filesystem cache for remote B-roll previews and public provenance.

Only public provider metadata is durable.  Temporary/signed preview and media
URLs remain transient so review artifacts cannot leak provider credentials.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable
from urllib.parse import urlsplit, urlunsplit

import httpx

from .online_assets import RemoteCandidate


FetchBytes = Callable[[str], Awaitable[bytes]]


@dataclass(frozen=True, slots=True)
class PreviewAsset:
    path: Path
    metadata_path: Path
    sha256: str
    cache_hit: bool


def _safe_public_url(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def public_provenance(candidate: RemoteCandidate) -> dict:
    """Return durable provider evidence without transient download URLs."""

    source_page = _safe_public_url(candidate.source_page)
    if not source_page:
        raise ValueError("candidate has no safe public source page")

    creator = None
    creator_page = _safe_public_url(candidate.creator_page)
    if candidate.creator_name or creator_page:
        creator = {}
        if candidate.creator_name:
            creator["name"] = candidate.creator_name
        if creator_page:
            creator["profile_page"] = creator_page

    row = {
        "provider": candidate.provider,
        "provider_id": candidate.provider_id,
        "query": candidate.query,
        "source_page": source_page,
        "title": candidate.title,
        "description": candidate.description,
        "duration": candidate.duration,
        "width": candidate.width,
        "height": candidate.height,
        "orientation": candidate.orientation,
        "rights_state": candidate.rights_state,
        "provider_rank": candidate.provider_rank,
    }
    if creator:
        row["creator"] = creator
    return row


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _preview_extension(url: str) -> str:
    suffix = Path(urlsplit(url).path).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp"} else ".img"


class AssetCache:
    """Client/run-scoped cache root supplied by the caller."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.preview_root = self.root / "previews"
        self.metadata_root = self.root / "metadata"

    def _key(self, candidate: RemoteCandidate) -> str:
        material = f"{candidate.provider}\0{candidate.provider_id}\0{candidate.preview_url}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    async def materialize_preview(
        self,
        candidate: RemoteCandidate,
        *,
        fetch: FetchBytes | None = None,
    ) -> PreviewAsset:
        key = self._key(candidate)
        extension = _preview_extension(candidate.preview_url)
        path = self.preview_root / f"{key}{extension}"
        metadata_path = self.metadata_root / f"{key}.json"

        cached = self._read_valid_cache(path, metadata_path)
        if cached is not None:
            return PreviewAsset(path=path, metadata_path=metadata_path, sha256=cached, cache_hit=True)

        fetcher = fetch or self._fetch_bytes
        data = await fetcher(candidate.preview_url)
        if not isinstance(data, (bytes, bytearray)) or not data:
            raise ValueError("preview fetch returned no bytes")
        payload = bytes(data)
        digest = _sha256_bytes(payload)

        self.preview_root.mkdir(parents=True, exist_ok=True)
        self.metadata_root.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_bytes(payload)
        tmp_path.replace(path)

        metadata = {
            **public_provenance(candidate),
            "preview_file": path.name,
            "preview_sha256": digest,
        }
        tmp_metadata = metadata_path.with_suffix(".json.tmp")
        tmp_metadata.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tmp_metadata.replace(metadata_path)
        return PreviewAsset(path=path, metadata_path=metadata_path, sha256=digest, cache_hit=False)

    @staticmethod
    def _read_valid_cache(path: Path, metadata_path: Path) -> str | None:
        if not path.is_file() or not metadata_path.is_file():
            return None
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            expected = str(metadata["preview_sha256"])
        except (OSError, ValueError, KeyError, TypeError):
            return None
        actual = _sha256_file(path)
        return actual if actual == expected else None

    @staticmethod
    async def _fetch_bytes(url: str) -> bytes:
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.content
        except httpx.HTTPError as exc:
            # Do not echo the possibly signed URL into durable errors/logs.
            raise RuntimeError(f"preview download failed: {type(exc).__name__}") from exc
