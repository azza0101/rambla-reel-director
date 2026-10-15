"""Frozen CUT provenance translated to a native Resolve source/frame contract."""
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
import hashlib
import json,subprocess

def native_cut_format(width,height,rotation=0):
    if int(rotation)%180:width,height=height,width
    if min(width,height)<=0:raise ValueError('Formato sorgente non valido')
    scale=1080/min(width,height)
    return max(2,round(width*scale/2)*2),max(2,round(height*scale/2)*2)

def validate_native_cut(cut):
    rate=Fraction(str(cut['fps']))
    if rate<=0:raise ValueError('FPS CUT non validi')
    cursor=0;previous=-1
    for row in cut['segments']:
        a,b,c,d=(row[k] for k in ('source_in_frame','source_out_frame','edited_in_frame','edited_out_frame'))
        if any(type(x) is not int for x in (a,b,c,d)) or not 0<=a<b<=cut['source_duration_frames'] or a<previous or c!=cursor or d-c!=b-a:raise ValueError('Mappa CUT non valida: frame sorgente/destinazione incoerenti')
        previous=b;cursor=d
    if not cursor or cursor!=cut['duration_frames']:raise ValueError('Durata CUT incoerente')

def load_native_cut(project_root,projects_root):
    project_root=Path(project_root);origin=project_root/'cut-origin.json'
    if origin.is_file():
        provenance=json.loads(origin.read_text(encoding='utf-8'))
        plan=deepcopy(provenance['plan']);source=Path(provenance['source_path'])
    else:
        plan=deepcopy(json.loads((project_root/'cut'/'plan.json').read_text(encoding='utf-8')))
        from .curation_project import ProjectStore
        from .video_preview import probe_preview
        project=ProjectStore(Path(projects_root), probe_runner=lambda path: probe_preview(str(path))).load(project_root.name)
        if project.analysis_signature!=plan['source_signature']:raise ValueError('Il video è cambiato: ricalcola CUT prima di esportare')
        source=Path(project.source_video.path)
    if not source.is_file():raise ValueError('Video originale non disponibile: ripristina il file lungo')
    source = source.resolve()
    stat = source.stat()
    physical_signature = hashlib.sha256(f'{source}|{stat.st_size}|{stat.st_mtime_ns}'.encode()).hexdigest()
    if not origin.is_file() and physical_signature != project.source_video.signature:
        raise ValueError('Il video originale è cambiato: ricalcola CUT prima di esportare')
    if origin.is_file():
        expected_signature = provenance.get('source_signature')
        if not expected_signature and not provenance.get('source_identity'):
            from .curation_project import ProjectStore
            parent = ProjectStore(Path(projects_root), probe_runner=lambda _: {}).load(provenance['project_id'])
            if not parent.source_video or Path(parent.source_video.path).resolve() != source:
                raise ValueError('Identità della vecchia sorgente CUT non verificabile: riconferma il CUT originale')
            expected_signature = parent.source_video.signature
        if expected_signature and expected_signature != physical_signature:
            raise ValueError('La sorgente originale del CUT congelato è cambiata')
    if (source.parent.name == 'cut' and source.name.startswith(('clean-','preview-'))) or source==project_root/'source'/'clean.mp4':raise ValueError('Il CUT nativo richiede il video lungo originale')
    validate_native_cut(plan)
    probe=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate,avg_frame_rate:stream_tags=rotate:stream_side_data=rotation','-of','json',str(source)],capture_output=True,text=True,check=True)
    streams=json.loads(probe.stdout)['streams'];stream=streams[0]
    # VFR phone files have a slightly different average rate; Resolve's clip
    # frame grid and the CUT plan use the original nominal source rate.
    source_rate=Fraction(stream.get('r_frame_rate') or stream['avg_frame_rate'])
    if abs(float(source_rate)-float(Fraction(plan['fps'])))>.002:raise ValueError('FPS originale diversi dal piano CUT')
    rotation=next((s.get('rotation',0) for s in stream.get('side_data_list',[]) if 'rotation' in s),stream.get('tags',{}).get('rotate',0))
    width,height=native_cut_format(stream['width'],stream['height'],rotation)
    stat=source.stat()
    identity = {'size':stat.st_size,'mtime_ns':stat.st_mtime_ns}
    if origin.is_file() and provenance.get('source_identity') and provenance['source_identity'] != identity:
        raise ValueError('Il video originale congelato è stato modificato: ripristina la sorgente')
    return {**plan,'source_path':str(source.resolve()),'fps':str(source_rate),'width':width,'height':height,
            'source_identity':identity,'export_schema':'rmbl-native-cut-1'}


def find_native_cut_receipt(project_root, projects_root, cut):
    """The uploaded parent and its confirmed CUT share the same verified base."""
    roots = [Path(project_root)]
    origin = roots[0] / 'cut-origin.json'
    if origin.is_file():
        provenance = json.loads(origin.read_text(encoding='utf-8'))
        parent_id = str(provenance.get('project_id') or '')
        if parent_id and parent_id not in {'.', '..'} and all(c.isalnum() or c in '_-' for c in parent_id):
            roots.append(Path(projects_root) / parent_id)
    receipts = []
    for owner in roots:
        for path in (owner / 'resolve-outbox').glob('*/package.json'):
            try:
                row = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            result = row.get('result') or {}
            if (row.get('status') == 'completed' and result.get('timeline_id')
                    and result.get('cut_revision') == cut['revision']
                    and result.get('source_identity') == cut['source_identity']):
                receipts.append(row)
    return max(receipts, key=lambda row: row.get('updated_at', ''), default={}).get('result')
