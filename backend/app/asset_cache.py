"""Filesystem cache for remote previews, selected stock media and evidence windows.

Only public provider/source metadata is durable. Temporary/signed preview and
media URLs remain transient so review artifacts cannot leak credentials.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from .online_assets import RemoteCandidate


FetchBytes = Callable[[str], Awaitable[bytes]]
AcquireToPath = Callable[[Path], Awaitable[None] | None]


@dataclass(frozen=True, slots=True)
class PreviewAsset:
    path: Path
    metadata_path: Path
    sha256: str
    cache_hit: bool


@dataclass(frozen=True, slots=True)
class CachedAsset:
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
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _safe_evidence_source_url(value: str | None) -> str | None:
    """Preserve stable public identifiers while removing transient credentials.

    YouTube's stable ``v`` parameter is retained because it identifies the
    source video. Other query parameters are discarded from durable metadata.
    """

    if not value:
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return None
    hostname = parsed.hostname.lower()
    query = ""
    if hostname in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        video_ids = [(key, val) for key, val in parse_qsl(parsed.query, keep_blank_values=False) if key == "v" and val]
        query = urlencode(video_ids[:1])
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))


def public_provenance(candidate: RemoteCandidate) -> dict:
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
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.preview_root = self.root / "previews"
        self.media_root = self.root / "selected"
        self.window_root = self.root / "windows"
        self.metadata_root = self.root / "metadata"

    def _preview_key(self, candidate: RemoteCandidate) -> str:
        material = f"{candidate.provider}\0{candidate.provider_id}\0{candidate.preview_url}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def _media_key(self, candidate: RemoteCandidate) -> str:
        material = (
            f"{candidate.provider}\0{candidate.provider_id}\0"
            f"{candidate.rendition_width}x{candidate.rendition_height}"
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @staticmethod
    def _window_key(
        provider: str,
        provider_id: str,
        start: float,
        end: float,
        kind: str,
    ) -> str:
        material = f"{provider}\0{provider_id}\0{start:.3f}\0{end:.3f}\0{kind}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    async def materialize_preview(self, candidate: RemoteCandidate, *, fetch: FetchBytes | None = None) -> PreviewAsset:
        key = self._preview_key(candidate)
        extension = _preview_extension(candidate.preview_url)
        path = self.preview_root / f"{key}{extension}"
        metadata_path = self.metadata_root / f"preview-{key}.json"
        cached = self._read_valid_cache(path, metadata_path, "preview_sha256")
        if cached is not None:
            return PreviewAsset(path, metadata_path, cached, True)
        payload = await (fetch or self._fetch_bytes)(candidate.preview_url)
        data = bytes(payload)
        if not data:
            raise ValueError("preview fetch returned no bytes")
        digest = _sha256_bytes(data)
        self._atomic_write(path, data)
        self._write_metadata(metadata_path, {
            **public_provenance(candidate),
            "preview_file": path.name,
            "preview_sha256": digest,
        })
        return PreviewAsset(path, metadata_path, digest, False)

    async def materialize_selected(self, candidate: RemoteCandidate, *, fetch: FetchBytes | None = None) -> CachedAsset:
        key = self._media_key(candidate)
        path = self.media_root / f"{key}.mp4"
        metadata_path = self.metadata_root / f"selected-{key}.json"
        cached = self._read_valid_cache(path, metadata_path, "content_sha256")
        if cached is not None:
            return CachedAsset(path, metadata_path, cached, True)
        payload = await (fetch or self._fetch_bytes)(candidate.selected_rendition_url)
        data = bytes(payload)
        if not data:
            raise ValueError("selected media fetch returned no bytes")
        digest = _sha256_bytes(data)
        self._atomic_write(path, data)
        self._write_metadata(metadata_path, {
            **public_provenance(candidate),
            "local_file": path.name,
            "content_sha256": digest,
            "rendition": {"width": candidate.rendition_width, "height": candidate.rendition_height},
        })
        return CachedAsset(path, metadata_path, digest, False)

    async def materialize_acquired_window(
        self,
        *,
        provider: str,
        provider_id: str,
        source_page: str,
        source_start_seconds: float,
        source_end_seconds: float,
        rights_state: str,
        acquire: AcquireToPath,
        kind: str = "video_window",
    ) -> CachedAsset:
        """Cache one bounded long-video window or still using an injected producer."""

        if not provider or not provider_id:
            raise ValueError("provider identity is required")
        if source_start_seconds < 0 or source_end_seconds <= source_start_seconds:
            raise ValueError("evidence window time range is invalid")
        if kind not in {"video_window", "still"}:
            raise ValueError("unsupported evidence cache kind")
        safe_source = _safe_evidence_source_url(source_page)
        if not safe_source:
            raise ValueError("evidence source page is not public http/https")

        key = self._window_key(
            provider,
            provider_id,
            source_start_seconds,
            source_end_seconds,
            kind,
        )
        extension = ".mp4" if kind == "video_window" else ".jpg"
        path = self.window_root / f"{key}{extension}"
        metadata_path = self.metadata_root / f"window-{key}.json"
        cached = self._read_valid_cache(path, metadata_path, "content_sha256")
        if cached is not None:
            return CachedAsset(path, metadata_path, cached, True)

        self.window_root.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        if tmp.exists():
            tmp.unlink()
        result = acquire(tmp)
        if inspect.isawaitable(result):
            await result
        if not tmp.is_file() or tmp.stat().st_size <= 0:
            raise ValueError("evidence acquisition produced no file")
        digest = _sha256_file(tmp)
        tmp.replace(path)
        self._write_metadata(
            metadata_path,
            {
                "provider": provider,
                "provider_id": provider_id,
                "source_page": safe_source,
                "source_start_seconds": round(float(source_start_seconds), 4),
                "source_end_seconds": round(float(source_end_seconds), 4),
                "rights_state": rights_state,
                "kind": kind,
                "local_file": path.name,
                "content_sha256": digest,
            },
        )
        return CachedAsset(path, metadata_path, digest, False)

    def _atomic_write(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.metadata_root.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)

    @staticmethod
    def _write_metadata(path: Path, metadata: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)

    @staticmethod
    def _read_valid_cache(path: Path, metadata_path: Path, hash_field: str) -> str | None:
        if not path.is_file() or not metadata_path.is_file():
            return None
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            expected = str(metadata[hash_field])
        except (OSError, ValueError, KeyError, TypeError):
            return None
        actual = _sha256_file(path)
        return actual if actual == expected else None

    @staticmethod
    async def _fetch_bytes(url: str) -> bytes:
        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.content
        except httpx.HTTPError as exc:
            raise RuntimeError(f"remote asset download failed: {type(exc).__name__}") from exc
