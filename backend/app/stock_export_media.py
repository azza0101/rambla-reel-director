"""Download explicitly selected stock videos, independently of search previews."""
import json
import asyncio
import os
from pathlib import Path
import uuid

import httpx

from .atomic_io import write_json
from .generic_coverage import candidate_dict
from .online_assets import PexelsSource
from .video_preview import probe_preview


def preserve_selected_generics(existing, results):
    selected = set(map(str, existing.get('selected') or []))
    retained = [row for row in existing.get('items') or [] if str(row['provider_id']) in selected]
    seen = {str(row['provider_id']) for row in retained}
    return retained + [row for row in results if str(row['provider_id']) not in seen]


def stock_media_path(run: Path, provider_id: str) -> Path:
    if not str(provider_id).isdigit():
        raise ValueError('Invalid Pexels video ID')
    return run / 'resolve-media' / 'pexels' / f'pexels_{provider_id}.mp4'


async def pexels_metadata(provider_id: str) -> dict:
    if not str(provider_id).isdigit():
        raise ValueError('Invalid Pexels video ID')
    key = os.environ.get('PEXELS_API_KEY', '').strip()
    if not key:
        raise ValueError('PEXELS_API_KEY non configurata')
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(f'https://api.pexels.com/videos/videos/{provider_id}', headers={'Authorization':key})
        response.raise_for_status()
    candidate = PexelsSource._normalize_video(response.json(), query='Selected video', provider_rank=1)
    if candidate is None:
        raise ValueError(f'Pexels {provider_id}: file video non disponibile')
    return candidate_dict(candidate)


async def prepare_pexels_video(run: Path, provider_id: str, progress=None) -> dict:
    target = stock_media_path(run, provider_id)
    metadata_path = target.with_suffix('.json')
    if target.is_file() and metadata_path.is_file() and probe_preview(str(target)).get('duration', 0) > 0:
        return json.loads(metadata_path.read_text(encoding='utf-8'))
    row = await pexels_metadata(provider_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f'{target.stem}.{uuid.uuid4().hex}.mp4')
    try:
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=10), follow_redirects=True) as client:
                    async with client.stream('GET', row['selected_rendition_url']) as response:
                        response.raise_for_status()
                        total = int(response.headers.get('content-length') or 0)
                        received = 0
                        with temporary.open('wb') as stream:
                            async for block in response.aiter_bytes():
                                stream.write(block)
                                received += len(block)
                                if progress:
                                    progress(received, total)
                break
            except httpx.TransportError as exc:
                if attempt:
                    raise ValueError(f'Pexels {provider_id}: trasferimento interrotto o senza dati per 30 secondi. Riprova INVIA; i video già pronti restano salvati.') from exc
                await asyncio.sleep(.5)
        facts = probe_preview(str(temporary))
        if float(facts.get('duration') or 0) <= 0 or not facts.get('width'):
            raise ValueError(f'Pexels {provider_id}: download non decodificabile')
        os.replace(temporary, target)
        row.update(media_path=str(target.resolve()), duration=facts['duration'])
        write_json(metadata_path, row)
        return row
    finally:
        temporary.unlink(missing_ok=True)
