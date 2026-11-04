"""Explicit component selection shared by preparation and Resolve packets."""
from pydantic import BaseModel,ConfigDict,StrictBool

KEYS=('video','source_video','subtitles','highlights','broll','social','generic')
SOCIAL={'youtube','youtube_shorts','tiktok','instagram'}
class ExportComponents(BaseModel):
    model_config=ConfigDict(extra='forbid')
    video:StrictBool=False
    source_video:StrictBool=False
    subtitles:StrictBool=False
    highlights:StrictBool=False
    broll:StrictBool=False
    social:StrictBool=False
    generic:StrictBool=False

def normalize_components(value,*,has_native_cut=False):
    if value is None:return {key:key not in {'video','source_video'} or (key=='video' and has_native_cut) for key in KEYS}
    if isinstance(value,ExportComponents):value=value.model_dump()
    result=ExportComponents.model_validate(value).model_dump()
    if result['video'] and result['source_video']:raise ValueError('Seleziona Video originale oppure Video CUT, non entrambi')
    if not any(result.values()):raise ValueError('Seleziona almeno una componente da esportare')
    return result

def filter_selected_media(rows,components):
    def provider(row):return str(row.get('provider','') if isinstance(row,dict) else getattr(row,'provider',''))
    return [row for row in rows if components.get('social' if provider(row) in SOCIAL else 'broll',False)]
