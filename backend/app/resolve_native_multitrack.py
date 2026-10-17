"""Rebuild a verified Resolve snapshot on a new, owned native CUT timeline."""
from datetime import datetime
from pathlib import Path
import uuid
import json
from .resolve_cut_source import capture_cut_source, verify_snapshot_files, remap_source_cut


def verify_project_source(project, snapshot):
    verify_snapshot_files(snapshot)
    source = next((project.GetTimelineByIndex(i) for i in range(1,int(project.GetTimelineCount())+1)
        if str(project.GetTimelineByIndex(i).GetUniqueId()) == snapshot['timeline_id']),None)
    if source is None:
        raise ValueError('Apri il progetto Resolve contenente la timeline originale del CUT')
    current = capture_cut_source(source,snapshot['mark_in'],snapshot['mark_out']-1)
    if current.get('signature') != snapshot.get('signature'):
        raise ValueError('La timeline originale è cambiata: ricalcola audio e CUT prima di applicare')
    return source


def append_mapped_clip(pool, timeline, media, row, base):
    for adjustment in (0,1):
        clips = pool.AppendToTimeline([dict(mediaPoolItem=media,startFrame=row['source_in'],
            endFrame=row['source_out']-adjustment,mediaType=1 if row['kind']=='video' else 2,
            trackIndex=row['track_index'],recordFrame=base+row['record_in'])]) or []
        expected = (base+row['record_in'],base+row['record_out'])
        if len(clips)==1 and (clips[0].GetStart(),clips[0].GetEnd()) == expected:
            item = clips[0]
            if abs(float(item.GetSourceStartFrame())-row['source_in']) > 1.01:
                raise RuntimeError('IN sorgente diverso dalla mappa multitraccia')
            if row.get('properties'):
                setter = getattr(item,'SetProperties',None)
                setter = setter if callable(setter) else item.SetProperty
                if setter(row['properties']) is False:
                    raise RuntimeError('Impossibile conservare le proprietà della clip originale')
            if row.get('audio_mapping') and item.SetSourceAudioChannelMapping(row['audio_mapping']) is False:
                raise RuntimeError('Impossibile conservare i canali audio originali')
            if item.SetClipEnabled(bool(row.get('enabled',True))) is False:
                raise RuntimeError('Impossibile conservare lo stato della clip originale')
            return item
        if clips and timeline.DeleteClips(clips,False) is False:
            raise RuntimeError('Impossibile rimuovere una clip di verifica dalla nuova timeline')
        if len(clips)!=1 or adjustment:
            break
    raise RuntimeError('Resolve non rispetta i tempi del CUT multitraccia')


def verify_multitrack_base(timeline, cut, base):
    verify_snapshot_files(cut['resolve_source'])
    rows = remap_source_cut(cut['resolve_source'],cut)
    counts = {'video_count':0,'audio_count':0}
    for track in cut['resolve_source']['tracks']:
        expected = sorted([r for r in rows if r['kind']==track['kind'] and r['track_index']==track['index']],key=lambda r:r['record_in'])
        actual = sorted(timeline.GetItemListInTrack(track['kind'],track['index']) or [],key=lambda c:c.GetStart())
        if len(actual)!=len(expected):
            raise RuntimeError('Numero clip diverso dalla mappa CUT multitraccia')
        for item,row in zip(actual,expected):
            if (item.GetStart(),item.GetEnd()) != (base+row['record_in'],base+row['record_out']):
                raise RuntimeError('Sincronizzazione CUT multitraccia non corretta')
            if Path(item.GetMediaPoolItem().GetClipProperty('File Path')).resolve() != Path(row['path']).resolve():
                raise RuntimeError('Il CUT multitraccia non usa la sorgente originale')
            if abs(float(item.GetSourceStartFrame())-row['source_in']) > 1.01:
                raise RuntimeError('Offset sorgente CUT multitraccia non corretto')
        counts[track['kind']+'_count'] += len(actual)
    return counts


def create_multitrack_cut(resolve, project, payload, *, progress=None):
    from .resolve_native_cut import (configure_native_timeline,checkpoint_path,
        delete_owned_native_cut,alternative_duration)
    from .atomic_io import write_json
    cut = payload['native_cut']
    snapshot = cut['resolve_source']
    verify_project_source(project,snapshot)  # before any timeline mutation
    rows = remap_source_cut(snapshot,cut)
    pool = project.GetMediaPool()
    original,folder = project.GetCurrentTimeline(),pool.GetCurrentFolder()
    timeline = None
    try:
        name = f'RMBL CUT {datetime.now():%Y%m%d %H%M%S} {uuid.uuid4().hex[:6]}'
        timeline = pool.CreateEmptyTimeline(name)
        if not timeline or not project.SetCurrentTimeline(timeline):
            raise RuntimeError('Impossibile creare la timeline CUT multitraccia')
        checkpoint = checkpoint_path(payload)
        if checkpoint:
            write_json(checkpoint,dict(project=project.GetName(),timeline_id=timeline.GetUniqueId(),
                timeline_name=name,revision=cut['revision']))
        configure_native_timeline(timeline,cut)
        for kind in ('video','audio'):
            tracks = [t for t in snapshot['tracks'] if t['kind']==kind]
            if kind=='audio':
                # Resolve refuses to delete its last audio track. Add the desired
                # subtypes first, then remove only the empty default tracks.
                defaults = int(timeline.GetTrackCount('audio') or 0)
                for track in tracks:
                    if timeline.AddTrack('audio',track['subtype']) is False:
                        raise RuntimeError('Impossibile creare le tracce audio originali del CUT')
                for index in range(defaults,0,-1):
                    if not tracks:
                        break
                    if timeline.DeleteTrack('audio',index) is False:
                        raise RuntimeError('Impossibile configurare le tracce audio CUT')
            for track in tracks:
                while int(timeline.GetTrackCount(kind) or 0) < track['index']:
                    added = timeline.AddTrack(kind,track['subtype']) if kind=='audio' else timeline.AddTrack(kind)
                    if added is False:
                        raise RuntimeError('Impossibile creare le tracce originali del CUT')
                if timeline.SetTrackName(kind,track['index'],track['name']) is False:
                    raise RuntimeError('Impossibile nominare le tracce del CUT')
                if timeline.SetTrackEnable(kind,track['index'],track['enabled']) is False:
                    raise RuntimeError('Impossibile conservare lo stato delle tracce CUT')
        base = int(timeline.GetStartFrame())
        imported = {}
        for index,row in enumerate(rows):
            if row['path'] not in imported:
                items = pool.ImportMedia([row['path']]) or []
                if len(items)!=1:
                    raise RuntimeError('Impossibile importare una sorgente originale del CUT')
                imported[row['path']] = items[0]
            append_mapped_clip(pool,timeline,imported[row['path']],row,base)
            if progress:
                progress(10+int(55*(index+1)/max(1,len(rows))),f'CUT multitraccia: {index+1}/{len(rows)} clip')
        counts = verify_multitrack_base(timeline,cut,base)
        for alternative in cut.get('alternatives') or []:
            duration = alternative_duration(cut,alternative)
            if duration<=0:
                continue
            local = {**cut,'duration_frames':duration,'segments':[dict(
                source_in_frame=alternative['source_in_frame'],source_out_frame=alternative['source_in_frame']+duration,
                edited_in_frame=0,edited_out_frame=duration)]}
            alt_rows = [r for r in remap_source_cut(snapshot,local) if r['kind']=='video']
            indexes = {}
            for row in alt_rows:
                if row['track_index'] not in indexes:
                    if timeline.AddTrack('video') is False:
                        raise RuntimeError('Impossibile creare la traccia take alternativa')
                    indexes[row['track_index']] = int(timeline.GetTrackCount('video'))
                    timeline.SetTrackName('video',indexes[row['track_index']],'RMBL TAKE ALTERNATIVA')
                mapped = {**row,'track_index':indexes[row['track_index']], 'enabled':False,
                    'record_in':row['record_in']+alternative['edited_in_frame'],
                    'record_out':row['record_out']+alternative['edited_in_frame']}
                if row['path'] not in imported:
                    items = pool.ImportMedia([row['path']]) or []
                    if len(items) != 1:
                        raise RuntimeError('Sorgente della take alternativa non disponibile')
                    imported[row['path']] = items[0]
                item = append_mapped_clip(pool,timeline,imported[row['path']],mapped,base)
                from .resolve_native_cut import set_alternative_color
                if not set_alternative_color(item):
                    raise RuntimeError('Impossibile colorare la take alternativa')
        verify_project_source(project,snapshot)  # originals and markers remain untouched
        return dict(timeline=timeline,fps=cut['fps'],base_frame=base,timeline_id=timeline.GetUniqueId(),
            timeline_name=name,**counts)
    except Exception:
        if timeline:
            delete_owned_native_cut(project,pool,timeline,original,payload)
        raise
    finally:
        pool.SetCurrentFolder(folder)
