"""Read-only Resolve source snapshots and deterministic multitrack CUT mapping."""
from fractions import Fraction
from pathlib import Path
import math
import hashlib
import json


def fingerprint(value):
    # This module is imported by Resolve's standalone Python, without app packages.
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def frame_rate(value):
    text = str(value)
    return {'23.976':Fraction(24000,1001),'29.97':Fraction(30000,1001),
            '59.94':Fraction(60000,1001)}.get(text, Fraction(text))


def file_identity(path):
    stat = Path(path).stat()
    return {'size':stat.st_size,'mtime_ns':stat.st_mtime_ns}


def _frame(value):
    number = float(value)
    if not math.isfinite(number) or abs(number-round(number)) > .001:
        raise ValueError('Clip con confini subframe: CUT nativo non supportato')
    return round(number)


def capture_cut_source(timeline, mark_in, mark_out):
    """mark_out is inclusive, matching Resolve's IN/OUT capture contract."""
    rate = frame_rate(timeline.GetSetting('timelineFrameRate'))
    result = dict(schema='rmbl-resolve-cut-source-1', supported=True,
        timeline_id=str(timeline.GetUniqueId()), mark_in=int(mark_in), mark_out=int(mark_out)+1,
        fps=str(rate),width=int(timeline.GetSetting('timelineResolutionWidth') or 0),
        height=int(timeline.GetSetting('timelineResolutionHeight') or 0),tracks=[],issues=[])
    properties = {'Pan','Tilt','ZoomX','ZoomY','ZoomGang','RotationAngle','AnchorPointX','AnchorPointY',
        'Pitch','Yaw','FlipX','FlipY','CropLeft','CropRight','CropTop','CropBottom','CropSoftness',
        'CropRetain','Opacity','CompositeMode','Scaling','ResizeFilter','AudioVolume','AudioPan',
        'AudioVolumeEnabled','AudioPanEnabled','TransformEnabled','CroppingEnabled','CompositeEnabled'}
    for kind in ('video','audio'):
        for index in range(1,int(timeline.GetTrackCount(kind) or 0)+1):
            track = dict(kind=kind,index=index,name=str(timeline.GetTrackName(kind,index) or ''),
                enabled=timeline.GetIsTrackEnabled(kind,index) is not False,clips=[])
            if kind == 'audio':
                track['subtype'] = timeline.GetTrackSubType(kind,index)
                if track['subtype'] not in {'mono','stereo'}:
                    result['issues'].append(f'Traccia audio {index}: formato non supportato')
            result['tracks'].append(track)
            for item in timeline.GetItemListInTrack(kind,index) or []:
                try:
                    start,end = _frame(item.GetStart()),_frame(item.GetEnd())
                    left,right = max(start,mark_in),min(end,mark_out+1)
                    if right <= left:
                        continue
                    media = item.GetMediaPoolItem()
                    if not media or int(item.GetFusionCompCount() or 0):
                        raise ValueError('Titolo, composizione o clip annidata non supportata')
                    path = str(media.GetClipProperty('File Path') or '')
                    if not path or not Path(path).is_file():
                        raise ValueError('Sorgente originale non disponibile o clip annidata')
                    speed = item.GetSpeed()
                    if not isinstance(speed,dict) or float(speed.get('Percentage',0)) != 100:
                        raise ValueError('Retime/freeze non supportato')
                    source_rate = frame_rate(media.GetClipProperty('FPS') or str(rate))
                    ratio = source_rate/rate
                    source_start = Fraction(str(item.GetSourceStartFrame()))
                    source_end = Fraction(str(item.GetSourceEndFrame()))+1
                    if abs(float(source_end-source_start-(end-start)*ratio)) > 1.01:
                        raise ValueError('Mappa temporale sorgente non lineare o non verificabile')
                    getter = getattr(item,'GetProperties',None)
                    raw_properties = getter() if callable(getter) else item.GetProperty()
                    raw_properties = raw_properties or {}
                    row = dict(id=str(item.GetUniqueId()),media_id=str(media.GetUniqueId()),
                        path=str(Path(path).resolve()),identity=file_identity(path),source_fps=str(source_rate),
                        timeline_in=left-mark_in,timeline_out=right-mark_in,
                        source_in=float(source_start+(left-start)*ratio),
                        source_out=float(source_start+(right-start)*ratio),
                        enabled=item.GetClipEnabled() is not False,
                        properties={k:v for k,v in raw_properties.items() if (callable(getter) or k in properties)
                            and isinstance(v,(str,int,float,bool))})
                    if kind == 'audio':
                        row['audio_mapping'] = item.GetSourceAudioChannelMapping()
                    track['clips'].append(row)
                except (OSError,TypeError,ValueError,AttributeError) as exc:
                    result['issues'].append(f'{kind} {index}: {exc}')
    result['supported'] = not result['issues'] and any(t['clips'] for t in result['tracks'] if t['kind']=='video')
    if not result['supported'] and not result['issues']:
        result['issues'].append('Nessuna clip video originale nel range')
    result['signature'] = fingerprint(result)
    return result


def verify_snapshot_files(snapshot):
    if not snapshot.get('supported'):
        raise ValueError('Sorgente Resolve non ricostruibile: '+' · '.join(snapshot.get('issues',[])))
    for track in snapshot['tracks']:
        for clip in track['clips']:
            if file_identity(clip['path']) != clip['identity']:
                raise ValueError('Una sorgente originale Resolve è cambiata: ricalcola audio e CUT')


def remap_source_cut(snapshot, cut):
    from .native_cut_export import validate_native_cut
    if not snapshot.get('supported'):
        raise ValueError('Sorgente Resolve non supportata')
    validate_native_cut(cut)
    rate = frame_rate(cut['fps'])
    if rate != frame_rate(snapshot['fps']) or cut['source_duration_frames'] != snapshot['mark_out']-snapshot['mark_in']:
        raise ValueError('Range o FPS CUT diversi dalla sorgente Resolve')
    output = []
    for track in snapshot['tracks']:
        for clip in track['clips']:
            for segment in cut['segments']:
                left = max(clip['timeline_in'],segment['source_in_frame'])
                right = min(clip['timeline_out'],segment['source_out_frame'])
                if right <= left:
                    continue
                ratio = frame_rate(clip['source_fps'])/rate
                source_in = Fraction(str(clip['source_in']))+(left-clip['timeline_in'])*ratio
                source_out = source_in+(right-left)*ratio
                record = segment['edited_in_frame']+left-segment['source_in_frame']
                output.append({**clip,'kind':track['kind'],'track_index':track['index'],
                    'track_name':track['name'],'track_enabled':track['enabled'],
                    'track_subtype':track.get('subtype'),'record_in':record,'record_out':record+right-left,
                    'source_in':float(source_in),'source_out':float(source_out)})
    return sorted(output,key=lambda r:(r['record_in'],r['kind'],r['track_index']))
