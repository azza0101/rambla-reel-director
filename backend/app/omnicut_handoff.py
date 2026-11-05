"""A versioned, local handoff for a future OmniCut adapter.

Values come from existing RMBL selections. Unknown visual properties remain
unknown; this format does not claim that OmniCut currently imports it.
"""
from pathlib import Path
from typing import Any
import json


def media_category(row: dict[str, Any]) -> str:
    if str(row.get('kind') or '').lower() == 'image' or str(row.get('role') or '') == 'fallback_image':
        return 'IMMAGINI'
    if str(row.get('role') or '') == 'generic' or str(row.get('beat_id') or '').casefold() in {'generic-tail', 'coperture generiche'}:
        return 'GENERICHE'
    return 'VIDEO'


def media_context(row: dict[str, Any], *, media_path: str | None = None) -> dict[str, Any]:
    result = {
        'asset_id': str(row.get('asset_id') or row.get('provider_id') or ''),
        'beat_id': str(row.get('beat_id') or ''),
        'title': str(row.get('title') or ''),
        'provider': str(row.get('provider') or ''),
        'source_page': str(row.get('source_page') or ''),
        'kind': str(row.get('kind') or 'video'),
        'role': str(row.get('role') or 'coverage'),
        'category': media_category(row),
        'media_path': str(media_path if media_path is not None else row.get('media_path') or ''),
        'original_text': str(row.get('original_text') or ''),
        'editorial_meaning': str(row.get('editorial_meaning') or ''),
        'place': str(row.get('place') or ''),
        'verification_reason': str(row.get('verification_reason') or ''),
        'enabled': row.get('enabled', True),
    }
    for source, target in [('track_index','track_index'),('record_start_frame','record_in_frame'),
                           ('record_end_frame','record_out_frame'),('source_start_frame','source_in_frame'),
                           ('source_end_frame','source_out_frame')]:
        if row.get(source) is not None: result[target] = row[source]
    return result


def build_handoff(payload: dict[str, Any], *, project_root: Path | None = None,
                  path_map: dict[str, str] | None = None) -> dict[str, Any]:
    rows=[]
    for row in payload.get('broll_clips') or []:
        path=str(row.get('media_path') or '')
        if path_map is not None and path not in path_map: continue
        rows.append(media_context(row, media_path=path_map[path] if path_map is not None else None))
    for row in payload.get('generic_broll_clips') or []:
        path=str(row.get('media_path') or '')
        if path_map is not None and path not in path_map: continue
        data=media_context({**row,'role':'generic'}, media_path=path_map[path] if path_map is not None else None)
        data['placement'] = 'resolve_tail_pending'
        rows.append(data)
    seen = {(row['asset_id'], row['media_path']) for row in rows}
    for row in payload.get('unplaced_images') or []:
        path = str(row.get('media_path') or '')
        if path_map is not None and path not in path_map: continue
        data = media_context({**row, 'kind':'image', 'role':'unplaced_image', 'enabled':False},
                             media_path=path_map[path] if path_map is not None else None)
        if (data['asset_id'], data['media_path']) not in seen:
            data['placement'] = 'unplaced'
            rows.append(data)
    transcript=[]
    if project_root is not None:
        try:
            chunks=json.loads((Path(project_root)/'run'/'semantic-chunks.json').read_text(encoding='utf-8'))
            if isinstance(chunks,list):
                transcript=[{key: row[key] for key in ('id','text','start','end','words') if key in row}
                            for row in chunks if isinstance(row,dict)]
        except (OSError,ValueError,TypeError): pass
    original=payload.get('original_video') or payload.get('native_cut') or payload.get('native_cut_reference') or {}
    source_path=str(original.get('source_path') or '') if isinstance(original,dict) else ''
    if path_map is not None: source_path=path_map.get(source_path,'')
    return {'schema':'rambla-omnicut-handoff-1',
            'project':{'id':str(payload.get('project_id') or ''),'name':str(payload.get('project_name') or '')},
            'timeline':{'fps':payload.get('fps'),'duration_seconds':payload.get('duration_seconds'),
                        'resolve_project':str(payload.get('source_project_name') or ''),
                        'resolve_timeline_id':str(payload.get('source_timeline_id') or '')},
            'source_video':{'media_path':source_path} if source_path else None,
            'transcript':transcript,'titles':payload.get('titles') or [],'subtitles':payload.get('subtitles') or [],
            'media':rows,'unavailable':payload.get('broll_unavailable') or []}
