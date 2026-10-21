"""Build native CUT clips exclusively on a newly owned timeline."""
from datetime import datetime
from fractions import Fraction
from pathlib import Path
import uuid
import json

from .native_cut_export import validate_native_cut


def checkpoint_path(payload):
    raw = payload.get('handoff_progress_path')
    return Path(raw).with_name('native-cut-checkpoint.json') if raw else None


def configure_native_timeline(timeline, cut):
    rate = Fraction(cut['fps'])
    ntsc = {Fraction(24000, 1001): '23.976', Fraction(30000, 1001): '29.97', Fraction(60000, 1001): '59.94'}
    label = ntsc.get(rate, str(int(rate)) if rate.denominator == 1 else str(float(rate)))
    values = {'useCustomSettings': '1', 'timelineFrameRate': label, 'timelineDropFrameTimecode': '0',
              'timelineResolutionWidth': str(cut['width']), 'timelineResolutionHeight': str(cut['height'])}
    setter = getattr(timeline, 'SetSettings', None)
    if callable(setter):
        write = lambda key, value: setter({key: value})
    else:
        setter = getattr(timeline, 'SetSetting', None)
        if not callable(setter):
            raise RuntimeError('API impostazioni timeline non disponibile')
        write = setter
    for key, value in values.items():
        if write(key, value):
            continue
        # Resolve21 Timeline API can use NTSC enum tokens23/29/59, unlike
        # Project settings. Verify the displayed fractional rate after setting.
        if key == 'timelineFrameRate' and rate in ntsc and write(key, str(int(rate))):
            continue
        raise RuntimeError(f'Resolve non accetta impostazione CUT {key}={value}')
    getter = getattr(timeline, 'GetSettings', None)
    actual = getter() if callable(getter) else timeline.GetSetting()
    if (abs(float(actual['timelineFrameRate']) - float(rate)) > .002
        or str(actual['timelineDropFrameTimecode']) != '0'
        or int(actual['timelineResolutionWidth']) != cut['width']
        or int(actual['timelineResolutionHeight']) != cut['height']):
        raise RuntimeError('Formato/FPS della timeline non corrispondono alla sorgente')


def clear_native_cut_checkpoint(payload):
    path = checkpoint_path(payload)
    if path:
        path.unlink(missing_ok=True)


def verify_source_identity(cut):
    if cut.get('resolve_source'):
        from .resolve_cut_source import verify_snapshot_files
        verify_snapshot_files(cut['resolve_source'])
        return None
    source = Path(cut['source_path'])
    if not source.is_file():
        raise ValueError('Video lungo originale non disponibile')
    stat = source.stat()
    if cut['source_identity'] != {'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}:
        raise ValueError('Video originale modificato dopo l’invio: prepara un nuovo pacchetto')
    return source


def recover_native_cut_result(project, payload):
    path = checkpoint_path(payload)
    if not path or not path.is_file():
        return None
    saved = json.loads(path.read_text(encoding='utf-8'))
    if not saved.get('result') or saved.get('project') != project.GetName():
        return None
    verify_source_identity(payload['native_cut'])
    for index in range(1, int(project.GetTimelineCount()) + 1):
        timeline = project.GetTimelineByIndex(index)
        if timeline.GetUniqueId() == saved['timeline_id']:
            verify_native_cut_base(timeline, payload['native_cut'], int(timeline.GetStartFrame()))
            project.SetCurrentTimeline(timeline)
            return saved['result']
    return None


def record_native_cut_result(project, payload, result):
    path = checkpoint_path(payload)
    if path:
        from .atomic_io import write_json
        write_json(path, {'project': project.GetName(), 'timeline_id': result['timeline_id'],
                          'timeline_name': result['timeline_name'], 'result': result})


def delete_owned_native_cut(project, pool, timeline, original, payload):
    if original:
        project.SetCurrentTimeline(original)
    if not pool.DeleteTimelines([timeline]):
        raise RuntimeError(f"Ripristino CUT non riuscito: timeline parziale '{timeline.GetName()}' ({timeline.GetUniqueId()}). Rimuovila dal progetto test prima di riprovare; nessuna nuova copia verrà creata.")
    clear_native_cut_checkpoint(payload)


def append_exact_segment(pool, timeline, source, segment, base_frame, *, convention=None):
    """Calibrate endFrame on our new clips, then enforce half-open CUT bounds."""
    start = base_frame + segment['edited_in_frame']
    end = base_frame + segment['edited_out_frame']
    adjustments = [0, 1] if convention is None else [convention]
    for adjustment in adjustments:
        rows = [dict(mediaPoolItem=source, startFrame=segment['source_in_frame'],
                     endFrame=segment['source_out_frame'] - adjustment,
                     mediaType=kind, trackIndex=1, recordFrame=start) for kind in (1, 2)]
        clips = pool.AppendToTimeline(rows) or []
        bounds = [(c.GetStart(), c.GetEnd()) for c in clips]
        if bounds == [(start, end)] * 2:
            return clips, adjustment
        # Never ripple delete: only the clips just returned by this append belong to us.
        if clips and not timeline.DeleteClips(clips, False):
            raise RuntimeError('Impossibile rimuovere il taglio di verifica dalla nuova timeline CUT')
        if len(clips) != 2:
            raise RuntimeError('Resolve non ha creato entrambe le clip video/audio del CUT')
        if adjustment != 0 or bounds != [(start, end + 1)] * 2:
            raise RuntimeError('Resolve ha restituito tempi diversi dal piano CUT')
    raise RuntimeError('Resolve non rispetta gli intervalli del CUT')


def verify_native_cut_base(timeline, cut, base_frame):
    if cut.get('resolve_source'):
        from .resolve_native_multitrack import verify_multitrack_base
        return verify_multitrack_base(timeline,cut,base_frame)
    if cut.get('source_identity'):
        verify_source_identity(cut)
    expected = [(base_frame + s['edited_in_frame'], base_frame + s['edited_out_frame'])
                for s in cut['segments']]
    counts = {}
    for kind in ('video', 'audio'):
        items = timeline.GetItemListInTrack(kind, 1) or []
        actual = sorted((c.GetStart(), c.GetEnd()) for c in items)
        if actual != expected:
            raise RuntimeError(f'Verifica CUT {kind} fallita: tagli o sincronizzazione non corrispondono')
        for item, segment in zip(sorted(items, key=lambda c: c.GetStart()), cut['segments']):
            source_start = getattr(item, 'GetSourceStartFrame', None)
            if callable(source_start):
                actual_in = source_start()
                expected_in = segment['source_in_frame']
                if actual_in != expected_in:
                    # Resolve can report the preceding decoded frame for VFR media.
                    # Accept only a one-frame discrepancy corroborated by the exact
                    # trim offset; destination bounds and source identity stay strict.
                    left_offset = getattr(item, 'GetLeftOffset', None)
                    corroborated = (isinstance(actual_in, (int, float))
                                    and abs(actual_in - expected_in) <= 1
                                    and callable(left_offset) and left_offset() == expected_in)
                    if not corroborated:
                        raise RuntimeError(f'Verifica CUT {kind} fallita: IN sorgente diverso dal piano '
                                           f'(atteso {expected_in}, letto {actual_in})')
            # For VFR phone media GetSourceEndFrame can report the last decoded
            # source frame rather than the CFR cut boundary (one fewer frame).
            # OUT is checked by the append's verified destination length; IN
            # and original media identity are checked here independently.
            if cut.get('source_path'):
                media = item.GetMediaPoolItem()
                if not media or Path(media.GetClipProperty('File Path')).resolve() != Path(cut['source_path']).resolve():
                    raise RuntimeError('Una clip CUT non usa il video lungo originale')
        counts[kind + '_count'] = len(items)
    return counts


def alternative_duration(cut, alternative):
    """Cap a discarded take to its chosen phrase on the compacted frame map."""
    start = alternative['edited_in_frame']
    group = cut['groups'][alternative['group_index']]
    chosen = group['source_ranges'][group['selected_take']]
    ends = [s['edited_in_frame'] + min(s['source_out_frame'], chosen['out_frame']) - s['source_in_frame']
            for s in cut['segments']
            if max(s['source_in_frame'], chosen['in_frame']) < min(s['source_out_frame'], chosen['out_frame'])]
    end = max(ends, default=start)
    return max(0, min(alternative['source_out_frame'] - alternative['source_in_frame'],
                      end - start, cut['duration_frames'] - start))


def set_alternative_color(item):
    # Resolve 21.1's clip palette has Pink but rejects Red (marker palette differs).
    return bool(item.SetClipColor('Red') or item.SetClipColor('Pink'))


def validate_active_source(clips,base,cut):
    # Phone VFR files can have a slightly different container duration from
    # Resolve's decoded frame count. File identity + zero trim offsets prove
    # full-source provenance; every retained OUT must still fit the real clip.
    ends=[]
    for clip in clips:
        media=clip.GetMediaPoolItem()
        if (not media or Path(media.GetClipProperty('File Path')).resolve()!=Path(cut['source_path']).resolve()
            or clip.GetStart()!=base or clip.GetEnd()<=base
            or clip.GetLeftOffset()>1 or clip.GetRightOffset()>1):
            raise RuntimeError('Il video integrale nella timeline è cambiato. Usa Nuova timeline o ricollega la sorgente.')
        ends.append(clip.GetEnd()-base)
    if max(ends)-min(ends)>1:
        raise RuntimeError('Audio e video della sorgente non sono allineati')
    if max(row['source_out_frame'] for row in cut['segments'])>min(ends):
        raise RuntimeError('Un taglio supera i frame disponibili della sorgente in Resolve')


def park_original(pool,timeline,source,cut,backup,base,convention):
    """Keep the full original reference after a two-second gap, disabled A/V."""
    start=cut['duration_frames']+round(float(Fraction(cut['fps']))*2)
    duration=backup['source_duration_frames']
    row=dict(source_in_frame=0,source_out_frame=duration,edited_in_frame=start,edited_out_frame=start+duration)
    clips,_=append_exact_segment(pool,timeline,source,row,base,convention=convention)
    if backup['properties'] and clips[0].SetProperty(backup['properties']) is False:
        raise RuntimeError('Impossibile conservare le proprietà del video originale')
    if not all(item.SetClipEnabled(False) for item in clips):
        raise RuntimeError('Impossibile disattivare video e audio originali conservati')
    if not timeline.SetClipsLinked(clips,True):raise RuntimeError('Impossibile collegare audio e video originali')
    occupied=set(timeline.GetMarkers() or {})
    for position,name,color in [(0,'CUT','Green'),(start,'ORIGINALE · disattivato','Blue')]:
        while position in occupied:position+=1
        if not timeline.AddMarker(position,color,name,'RMBL Auto-Cut',1):raise RuntimeError('Impossibile aggiungere marker '+name)
        occupied.add(position)
    if not timeline.SetMarkInOut(0,cut['duration_frames']-1):raise RuntimeError('Impossibile impostare IN OUT sul solo CUT')
    return {'original_start_frame':base+start,'original_end_frame':base+start+duration,
            'export_in_frame':base,'export_out_frame':base+cut['duration_frames']}


def prepare_active_cut(project,pool,timeline,cut):
    """Reject unrelated edits before creating the required backup or removing clips."""
    items={kind:[c for track in range(1,int(timeline.GetTrackCount(kind))+1)
        for c in (timeline.GetItemListInTrack(kind,track) or [])] for kind in ('video','audio','subtitle')}
    if len(items['video'])!=1 or len(items['audio'])!=1 or items['subtitle']:
        raise RuntimeError('La timeline attuale deve contenere soltanto il video integrale e il suo audio. Usa Nuova timeline.')
    base=int(timeline.GetStartFrame())
    validate_active_source(items['video']+items['audio'],base,cut)
    settings=timeline.GetSetting()
    if abs(float(settings['timelineFrameRate'])-float(Fraction(cut['fps'])))>.002:
        raise RuntimeError('FPS della timeline diversi dalla sorgente. Usa Nuova timeline.')
    from .resolve_textplus_timeline import next_backup_name,create_active_backup
    from .resolve_native_subtitles import ensure_media_pool_folder
    name=next_backup_name(project,timeline.GetName())
    _,backup=create_active_backup(timeline,name)
    backup_item=backup.GetMediaPoolItem()
    if not backup_item or not pool.MoveClips([backup_item],ensure_media_pool_folder(pool,'BCK')):
        project.SetCurrentTimeline(timeline)
        raise RuntimeError('Backup creato ma non archiviato in BCK: nessun taglio applicato')
    if not project.SetCurrentTimeline(timeline):raise RuntimeError('Impossibile tornare alla timeline originale; backup '+name)
    return {'name':name,'timeline':backup,'clips':items['video']+items['audio'],'markers':dict(timeline.GetMarkers() or {}),
            'properties':items['video'][0].GetProperty(),'source_duration_frames':items['video'][0].GetEnd()-items['video'][0].GetStart()}


def create_native_cut_base(resolve, project, payload, *, progress=None, target=None):
    cut = payload['native_cut']
    validate_native_cut(cut)
    source_path = verify_source_identity(cut)
    pool = project.GetMediaPool()
    checkpoint = checkpoint_path(payload)
    if checkpoint and checkpoint.is_file():
        previous = json.loads(checkpoint.read_text(encoding='utf-8'))
        if previous['project'] != project.GetName():
            raise RuntimeError('Il pacchetto CUT ha una timeline parziale in un altro progetto: ripristina quel progetto prima di riprovare')
        for index in range(1, int(project.GetTimelineCount()) + 1):
            existing = project.GetTimelineByIndex(index)
            if existing.GetUniqueId() == previous['timeline_id']:
                raise RuntimeError(f"Timeline CUT parziale ancora presente: {previous['timeline_name']}. Rimuovila prima di riprovare.")
        checkpoint.unlink()
    if cut.get('resolve_source'):
        if target is not None:raise RuntimeError('CUT multitraccia: usa Nuova timeline')
        from .resolve_native_multitrack import create_multitrack_cut
        return create_multitrack_cut(resolve,project,payload,progress=progress)
    original = project.GetCurrentTimeline()
    folder = pool.GetCurrentFolder()
    timeline = None
    backup = None
    try:
        source_items = pool.ImportMedia([str(source_path)]) or []
        if len(source_items) != 1:
            raise RuntimeError('Resolve non riesce a importare il video lungo originale')
        source = source_items[0]
        name = f"RMBL CUT {datetime.now():%Y%m%d %H%M%S} {uuid.uuid4().hex[:6]}"
        if target is None:
            timeline = pool.CreateEmptyTimeline(name)
        else:
            backup=prepare_active_cut(project,pool,target,cut)
            timeline=target;name=target.GetName()
            if not target.DeleteClips(backup['clips'],False):raise RuntimeError('Impossibile rimuovere le clip originali')
        if timeline and checkpoint:
            from .atomic_io import write_json
            write_json(checkpoint, {'project': project.GetName(), 'timeline_id': timeline.GetUniqueId(),
                                    'timeline_name': name, 'revision': cut['revision']})
        if not timeline or not project.SetCurrentTimeline(timeline):
            raise RuntimeError('Impossibile attivare la nuova timeline CUT')
        if target is None:configure_native_timeline(timeline, cut)
        base = int(timeline.GetStartFrame())
        convention = None
        for index, segment in enumerate(cut['segments']):
            clips, convention = append_exact_segment(pool, timeline, source, segment, base, convention=convention)
            if backup and backup['properties']:
                if clips[0].SetProperty(backup['properties']) is False:raise RuntimeError('Impossibile conservare le proprietà video')
            linker = getattr(timeline, 'SetClipsLinked', None)
            if callable(linker) and not linker(clips, True):
                raise RuntimeError('Resolve non riesce a collegare video e audio del CUT')
            if progress:
                progress(10 + int(55 * (index + 1) / len(cut['segments'])),
                         f"CUT nativo: {index + 1}/{len(cut['segments'])} tagli")
        counts = verify_native_cut_base(timeline, cut, base)
        alternatives = cut.get('alternatives') or []
        alternative_tracks = []
        for alternative in sorted(alternatives, key=lambda row: row['edited_in_frame']):
            duration = alternative_duration(cut, alternative)
            if duration <= 0:
                continue
            # Reuse tracks only when the alternatives do not overlap.
            slot = next((slot for slot in alternative_tracks if slot[1] <= alternative['edited_in_frame']), None)
            if slot is None:
                if not timeline.AddTrack('video'):
                    raise RuntimeError('Impossibile creare la traccia take alternativa')
                slot = [timeline.GetTrackCount('video'), 0]
                alternative_tracks.append(slot)
            track = slot[0]
            slot[1] = alternative['edited_in_frame'] + duration
            items = pool.AppendToTimeline([dict(mediaPoolItem=source,
                startFrame=alternative['source_in_frame'],
                endFrame=alternative['source_in_frame'] + duration - convention,
                mediaType=1, trackIndex=track, recordFrame=base + alternative['edited_in_frame'])]) or []
            if (len(items) != 1 or items[0].GetStart() != base + alternative['edited_in_frame']
                or items[0].GetEnd() != base + alternative['edited_in_frame'] + duration
                or not items[0].SetClipEnabled(False)
                or not set_alternative_color(items[0])):
                raise RuntimeError('Verifica della take alternativa disattivata non riuscita')
            timeline.SetTrackName('video', track, 'RMBL TAKE ALTERNATIVA')
        parked={}
        if backup:
            from .resolve_textplus_timeline import verify_timeline_markers
            verify_timeline_markers(timeline,backup['markers'])
            parked=park_original(pool,timeline,source,cut,backup,base,convention)
        return dict(timeline=timeline, backup_name=backup['name'] if backup else None, fps=cut['fps'], base_frame=base,
                    timeline_id=timeline.GetUniqueId(), timeline_name=name, **counts, **parked)
    except Exception as exc:
        if target is not None and backup:
            project.SetCurrentTimeline(backup['timeline'])
            raise RuntimeError('Applicazione alla timeline interrotta. Originale completo nel backup '+backup['name']+'. '+str(exc)) from exc
        if timeline and target is None:
            delete_owned_native_cut(project, pool, timeline, original, payload)
        raise
    finally:
        pool.SetCurrentFolder(folder)
