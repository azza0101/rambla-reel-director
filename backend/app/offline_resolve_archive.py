"""Experimental Resolve 21 archive writer. Resolve is not used for generation.

Native timeline encoding is provided by the MIT-licensed pr2resolve project.
Text+ template and composition framing are based on the MIT-licensed drp-format.
"""
from __future__ import annotations

import copy
import io
import json
import math
import re
import struct
import subprocess
import uuid
import zipfile
import zlib
from fractions import Fraction
from pathlib import Path
from xml.etree import ElementTree as ET

from ..vendor.pr2resolve.pr2_native import export_native_drp

TITLE_TEMPLATE = Path(__file__).resolve().parents[1] / 'vendor' / 'resolve_offline' / 'fusion-kura-v9.xml'
KURA_PRESET = Path(__file__).resolve().parents[1] / 'assets' / 'resolve_titles' / 'KURA_paper_title_v9.drfx'
KURA_INSTALLER = KURA_PRESET.parent / 'installer'
SOCIAL = {'youtube', 'youtube_shorts', 'tiktok', 'instagram'}


def probe_media(path: Path) -> dict:
    result = subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)],
                            capture_output=True,text=True,check=True,timeout=30)
    data=json.loads(result.stdout)
    video=next((s for s in data.get('streams',[]) if s.get('codec_type')=='video'),None)
    if not video:
        raise ValueError(f'File video non riconosciuto: {path.name}')
    rate=Fraction(video.get('avg_frame_rate') or video.get('r_frame_rate') or '0')
    if rate<=0:
        raise ValueError(f'FPS non validi: {path.name}')
    still=path.suffix.casefold() in {'.png','.jpg','.jpeg','.webp','.tif','.tiff'}
    raw_duration=video.get('duration') or data.get('format',{}).get('duration') or 0
    try:duration=float(raw_duration)
    except (ValueError,TypeError):duration=0
    raw_frames=video.get('nb_frames')
    try:frames=int(raw_frames) if raw_frames not in (None,'N/A') else (1 if still else round(duration*float(rate)))
    except (ValueError,TypeError):frames=1 if still else round(duration*float(rate))
    audio=next((s for s in data.get('streams',[]) if s.get('codec_type')=='audio'),None)
    return {'fps':float(rate),'width':int(video.get('width') or 0),'height':int(video.get('height') or 0),
            'duration_frames':frames,'has_audio':bool(audio),'channels':int((audio or {}).get('channels') or 1),
            'sample_rate':int((audio or {}).get('sample_rate') or 48000),'codec':str(video.get('codec_name') or '')}


def _rate(parent, value):
    rate=ET.SubElement(parent,'rate'); fraction=Fraction(str(value)).limit_denominator(1001)
    ntsc=fraction.denominator==1001
    ET.SubElement(rate,'timebase').text=str(round(float(fraction)) if ntsc else int(fraction))
    ET.SubElement(rate,'ntsc').text='TRUE' if ntsc else 'FALSE'


def _append_clip(track, row, fps, source, spec, media_id, *, audio=False, channel=1):
    start,end=int(row['start']),int(row['end']); source_in=int(row.get('source_in') or 0)
    if start<0 or end<=start or source_in<0:
        raise ValueError('Intervallo media non valido')
    clip=ET.SubElement(track,'clipitem',id=uuid.uuid4().hex)
    for key,value in [('name',source.name),('start',start),('end',end),('in',source_in),('out',source_in+end-start)]:
        ET.SubElement(clip,key).text=str(value)
    _rate(clip,fps)
    file=ET.SubElement(clip,'file',id=media_id)
    ET.SubElement(file,'name').text=source.name
    ET.SubElement(file,'pathurl').text=source.resolve().as_uri()
    ET.SubElement(file,'duration').text=str(spec['duration_frames'])
    _rate(file,spec['fps'])
    media=ET.SubElement(file,'media'); video=ET.SubElement(media,'video'); samples=ET.SubElement(video,'samplecharacteristics')
    ET.SubElement(samples,'width').text=str(spec['width']); ET.SubElement(samples,'height').text=str(spec['height'])
    aud=ET.SubElement(media,'audio');ET.SubElement(aud,'channelcount').text=str(spec.get('channels') or 1)
    audsample=ET.SubElement(aud,'samplecharacteristics');ET.SubElement(audsample,'samplerate').text=str(spec.get('sample_rate') or 48000)
    if audio:
        st=ET.SubElement(clip,'sourcetrack');ET.SubElement(st,'mediatype').text='audio';ET.SubElement(st,'trackindex').text=str(channel)


def _text_blob(hexvalue, text):
    raw=bytes.fromhex(hexvalue); outer=zlib.decompress(raw[4:]); marker=outer.rfind(b'Compressed = true, }')
    if marker<0: raise ValueError('Template Fusion non riconosciuto')
    zero=outer.find(b'\0',marker)
    if zero<0: raise ValueError('Template Fusion incompleto')
    offset=zero+1; inner=zlib.decompress(outer[offset+4:]).decode('utf8')
    escaped=str(text).replace('\\','\\\\').replace('"','\\"').replace('\n','\\n').replace('\r','\\r').replace('\t','\\t')
    pattern=r'(StyledText = Input \{ Value = ")((?:[^"\\]|\\.)*)(")'
    inner,n=re.subn(pattern,lambda m:m.group(1)+escaped+m.group(3),inner,count=1)
    if n!=1: raise ValueError('Testo Fusion non modificabile')
    raw_inner=inner.encode('utf8'); frame=outer[:offset]+struct.pack('<I',len(raw_inner))+zlib.compress(raw_inner,9)
    composition_start=frame.find(b'Composition {')
    if composition_start<4: raise ValueError('Intestazione composizione Fusion non riconosciuta')
    frame=frame[:composition_start-4]+struct.pack('>I',len(frame)-composition_start)+frame[composition_start:]
    return (struct.pack('>I',len(frame))+zlib.compress(frame)).hex()


def _inject_text(drp: bytes, titles: list[dict], subtitles: list[dict], fps: float, disabled_clips=()) -> bytes:
    with zipfile.ZipFile(io.BytesIO(drp)) as archive: members={n:archive.read(n) for n in archive.namelist()}
    key=next((n for n in members if n.startswith('SeqContainer/') and n.endswith('.xml')),None)
    if not key: raise ValueError('Timeline nativa assente')
    seq=ET.fromstring(members[key]); video=seq.find('VideoTrackVec')
    if video is None or video.find('Element/Sm2TiTrack') is None: raise ValueError('Traccia video assente')
    base=video.find('Element/Sm2TiTrack')
    tracks=video.findall('Element/Sm2TiTrack')
    for track_index, start_frame in disabled_clips:
        matches=[x for x in tracks[track_index-1].findall('Items/Element/Sm2TiVideoClip') if int(x.findtext('Start', '-1'))==start_frame]
        if len(matches)!=1:raise ValueError('Impossibile identificare la copertura da disattivare')
        flags=matches[0].find('Flags');flags.text=str(int(flags.text or 0)|2)
    if titles:
        track=copy.deepcopy(base);track.set('DbId',str(uuid.uuid4()));track.find('Items').clear()
        for row in titles:
            start=int(row.get('start_frame',round(float(row.get('start_seconds',0))*fps)))
            end=int(row.get('end_frame',round(float(row.get('end_seconds',0))*fps)))
            if end<=start: raise ValueError('Intervallo titolo non valido')
            element=ET.fromstring(TITLE_TEMPLATE.read_text(encoding='utf8'))
            for node in element.iter():
                if 'DbId' in node.attrib:node.set('DbId',str(uuid.uuid4()))
            clip=element.find('Sm2TiVideoClip');clip.find('Start').text=str(start);clip.find('Duration').text=str(end-start)
            blob=clip.find('.//CompositionBA');blob.text=_text_blob(blob.text or '',str(row.get('text') or ''))
            track.find('Items').append(element)
        wrapper=ET.SubElement(video,'Element');wrapper.append(track)
    if subtitles:
        vector=seq.find('SubtitleTrackVec')
        if vector is None: vector=ET.SubElement(seq,'SubtitleTrackVec')
        vector.clear();wrapper=ET.SubElement(vector,'Element'); track=ET.SubElement(wrapper,'Sm2TiTrack',DbId=str(uuid.uuid4()))
        fields={'FieldsBlob':'000000010000000100000012004e0075006d004c00610079006500720073000000020000000000',
                'Type':'2','SubType':'19','Flags':'0','Sequence':base.findtext('Sequence') or ''}
        for k,v in fields.items():ET.SubElement(track,k).text=v
        items=ET.SubElement(track,'Items')
        for row in subtitles:
            start=int(row.get('start_frame',round(float(row.get('start_seconds',0))*fps)))
            end=int(row.get('end_frame',round(float(row.get('end_seconds',0))*fps)))
            if end<=start: raise ValueError('Intervallo sottotitolo non valido')
            el=ET.SubElement(items,'Element'); clip=ET.SubElement(el,'Sm2TiGenerator',DbId=str(uuid.uuid4()))
            vals={'FieldsBlob':'','PrettyType':'Subtitle','Name':str(row.get('text') or ''),'Start':str(start),'Duration':str(end-start),
                  'LinkedItemSync':'','WasDisbanded':'false','MarkersBA':'','UiMemento':'0','Flags':'0','PriorityIndex':'0',
                  'EffectFiltersBA':'','ImportExportMetadataBA':'','RenderTextEnabled':'true','RenderTextGanged':'true',
                  'RenderTextPrefixed':'true','In':''}
            for k,v in vals.items():ET.SubElement(clip,k).text=v
        for tag in ('FusionCompHolderItems','UserDefinedName','LayersVec'):ET.SubElement(track,tag)
    members[key]=ET.tostring(seq,encoding='utf8',xml_declaration=True)
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in members.items():z.writestr(name,data)
    return output.getvalue()


def create_offline_resolve_archive(payload: dict, target: Path, *, probe_media=probe_media) -> dict:
    if payload.get('titles') and not KURA_PRESET.is_file():
        raise ValueError('Preset KURA non disponibile: impossibile esportare i titoli')
    fps=float(Fraction(str(payload.get('fps') or 30)))
    if not math.isfinite(fps) or fps<=0:raise ValueError('FPS non validi')
    base=payload.get('native_cut') or payload.get('original_video') or {}
    if base.get('resolve_source'):raise ValueError('Il CUT da timeline Resolve non è ancora supportato offline')
    source_path=str(base.get('source_path') or '')
    coverage=list(payload.get('broll_clips') or [])
    generics=list(payload.get('generic_broll_clips') or [])
    all_paths=([source_path] if source_path else [])+[str(x.get('media_path') or '') for x in coverage+generics]
    paths=[]; names={}
    for value in all_paths:
        path=Path(value)
        if not value or not path.is_file():raise ValueError('Media selezionato non disponibile: '+(path.name or '(mancante)'))
        path=path.resolve();key=path.name.casefold()
        if key in names and names[key]!=path:raise ValueError('Due media hanno lo stesso nome: '+path.name)
        names[key]=path
        if path not in paths: paths.append(path)
    specs={path:probe_media(path) for path in paths}
    for path,spec in specs.items():
        if not spec.get('fps') or not spec.get('duration_frames') or not spec.get('width') or not spec.get('height'):
            raise ValueError('Specifiche media non valide: '+path.name)
        if path.suffix.casefold() not in {'.png','.jpg','.jpeg','.webp','.tif','.tiff'} and spec.get('codec') not in (None,'h264'):
            raise ValueError('Il DRA offline supporta solo video H.264 verificati; codec non supportato per '+path.name+': '+str(spec.get('codec')))
    seq=ET.Element('sequence');ET.SubElement(seq,'name').text=str(payload.get('project_name') or 'RMBL')
    _rate(seq,fps);media=ET.SubElement(seq,'media');video=ET.SubElement(media,'video');audio=ET.SubElement(media,'audio')
    fmt=ET.SubElement(video,'format');sample=ET.SubElement(fmt,'samplecharacteristics')
    ET.SubElement(sample,'width').text=str(base.get('width') or 1080);ET.SubElement(sample,'height').text=str(base.get('height') or 1920)
    tracks={1:ET.SubElement(video,'track')};audio_tracks=[]
    ids={p:'media-'+str(i) for i,p in enumerate(paths)}
    duration=int(round(float(payload.get('duration_seconds') or 0)*fps))
    if source_path:
        source=Path(source_path).resolve();spec=specs[source]
        use_audio=bool(base.get('source_has_audio',base.get('has_audio',spec.get('has_audio'))))
        if use_audio:
            if not spec.get('has_audio'):raise ValueError('Audio originale non presente nel file')
            channels=int(spec.get('channels') or 1)
            if channels != 1:raise ValueError('DRA offline: audio stereo o multicanale non ancora verificato; usa il bridge per mantenere il mix originale')
            audio_tracks=[ET.SubElement(audio,'track') for _ in range(channels)]
        segments=base.get('segments') or [{'source_in_frame':0,'edited_in_frame':0,'edited_out_frame':int(base.get('duration_frames') or spec['duration_frames'])}]
        for part in segments:
            row={'start':part['edited_in_frame'],'end':part['edited_out_frame'],'source_in':part['source_in_frame']}
            _append_clip(tracks[1],row,fps,source,spec,ids[source])
            for channel,track in enumerate(audio_tracks,1):_append_clip(track,row,fps,source,spec,ids[source],audio=True,channel=channel)
            duration=max(duration,int(row['end']))
    tail=duration+round(float(payload.get('generic_tail_gap_seconds') or 2)*fps)
    for item in generics:
        n=max(1,round(min(4.,float(item.get('duration') or 4))*fps))
        coverage.append({**item,'track_index':2,'record_start_frame':tail,'record_end_frame':tail+n,'source_start_frame':0})
        tail+=n
    disabled_clips=[]
    for item in coverage:
        idx=max(2,int(item.get('track_index') or 2))
        while len(tracks)<idx:tracks[len(tracks)+1]=ET.SubElement(video,'track')
        path=Path(item['media_path']).resolve()
        row={'start':int(item['record_start_frame']),'end':int(item['record_end_frame']),'source_in':int(item.get('source_start_frame') or 0)}
        _append_clip(tracks[idx],row,fps,path,specs[path],ids[path]);duration=max(duration,row['end'])
        if item.get('enabled') is False:disabled_clips.append((idx,row['start']))
    ET.SubElement(seq,'duration').text=str(max(duration,1))
    import tempfile
    target=Path(target)
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='rmbl-offline-',dir=target.parent) as temp:
        native=Path(temp)/'project.drp';export_native_drp(seq,native,str(payload.get('project_name') or 'RMBL'))
        data=_inject_text(native.read_bytes(),payload.get('titles') or [],payload.get('subtitles') or [],fps,disabled_clips)
        with zipfile.ZipFile(io.BytesIO(data)) as z:members={n:z.read(n) for n in z.namelist()}
        q=lambda n:struct.pack('>Q',n)
        mdat=q(4)+b'mdat'+q(1)+q(1)
        for path in paths:
            raw=str(path).encode('utf8');mdat+=q(len(raw))+raw+q(0)
        members['media.dat']=mdat;out=io.BytesIO()
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
            for n,data in members.items():z.writestr(n,data)
        safe=re.sub(r'[^\w .-]+','_',str(payload.get('project_name') or 'RMBL')).strip(' .') or 'RMBL'
        with zipfile.ZipFile(target,'w',allowZip64=True) as z:
            z.writestr(safe+'.dra/project.drp',out.getvalue())
            for path in paths:z.write(path,safe+'.dra/MediaFiles/'+path.name,compress_type=zipfile.ZIP_STORED)
            instructions='Estrai lo ZIP e in Resolve usa Restore Project Archive sulla cartella .dra.\n'
            if payload.get('titles'):
                z.write(KURA_PRESET,'KURA_paper_title_v9_STANDALONE_FIXED.drfx')
                for name in ('Installa KURA Windows.cmd','Installa KURA Windows.ps1','Installa KURA Mac.command'):
                    info=zipfile.ZipInfo(name)
                    info.create_system=3
                    info.external_attr=(0o100755 if name.endswith('.command') else 0o100644)<<16
                    z.writestr(info,(KURA_INSTALLER/name).read_bytes())
                instructions += ('\nPer i titoli KURA: se necessario esegui Installa KURA Windows.cmd oppure '
                                 'Installa KURA Mac.command prima di ripristinare il progetto. '
                                 'Se il preset identico e gia presente non viene duplicato. '
                                 'Serve anche il font Montserrat. Riavvia Resolve dopo una nuova installazione.\n')
            z.writestr('LEGGIMI.txt',instructions)
    return {'media_count':len(paths),'subtitle_count':len(payload.get('subtitles') or []),'title_count':len(payload.get('titles') or [])}
