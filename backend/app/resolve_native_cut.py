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
            if callable(source_start) and source_start() != segment['source_in_frame']:
                raise RuntimeError(f'Verifica CUT {kind} fallita: IN sorgente diverso dal piano')
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


def create_native_cut_base(resolve, project, payload, *, progress=None):
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
        from .resolve_native_multitrack import create_multitrack_cut
        return create_multitrack_cut(resolve,project,payload,progress=progress)
    original = project.GetCurrentTimeline()
    folder = pool.GetCurrentFolder()
    timeline = None
    try:
        source_items = pool.ImportMedia([str(source_path)]) or []
        if len(source_items) != 1:
            raise RuntimeError('Resolve non riesce a importare il video lungo originale')
        source = source_items[0]
        name = f"RMBL CUT {datetime.now():%Y%m%d %H%M%S} {uuid.uuid4().hex[:6]}"
        timeline = pool.CreateEmptyTimeline(name)
        if timeline and checkpoint:
            from .atomic_io import write_json
            write_json(checkpoint, {'project': project.GetName(), 'timeline_id': timeline.GetUniqueId(),
                                    'timeline_name': name, 'revision': cut['revision']})
        if not timeline or not project.SetCurrentTimeline(timeline):
            raise RuntimeError('Impossibile attivare la nuova timeline CUT')
        configure_native_timeline(timeline, cut)
        base = int(timeline.GetStartFrame())
        convention = None
        for index, segment in enumerate(cut['segments']):
            clips, convention = append_exact_segment(pool, timeline, source, segment, base, convention=convention)
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
                or not items[0].SetClipColor('Red')):
                raise RuntimeError('Verifica della take alternativa disattivata non riuscita')
            timeline.SetTrackName('video', track, 'RMBL TAKE ALTERNATIVA')
        return dict(timeline=timeline, fps=cut['fps'], base_frame=base,
                    timeline_id=timeline.GetUniqueId(), timeline_name=name, **counts)
    except Exception:
        if timeline:
            delete_owned_native_cut(project, pool, timeline, original, payload)
        raise
    finally:
        pool.SetCurrentFolder(folder)
