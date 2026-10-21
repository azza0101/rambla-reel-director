"""Keep original editable items to the right on the same timeline identity."""
from datetime import datetime
from fractions import Fraction
from pathlib import Path
import json,time


def call(item,name,default=None):
    method=getattr(item,name,None)
    return method() if callable(method) else default


def capture_items(timeline):
    records=[]
    for kind in ('video','audio','subtitle'):
        for track in range(1,int(timeline.GetTrackCount(kind) or 0)+1):
            for item in timeline.GetItemListInTrack(kind,track) or []:
                records.append({'id':item.GetUniqueId(),'item':item,'kind':kind,'track':track,
                    'start':item.GetStart(),'end':item.GetEnd(),'name':item.GetName(),
                    'properties':call(item,'GetProperty',{}),'color':call(item,'GetClipColor',''),
                    'enabled':call(item,'GetClipEnabled',True),'source_in':call(item,'GetSourceStartFrame'),
                    'source_out':call(item,'GetSourceEndFrame'),'fusion_count':call(item,'GetFusionCompCount',0),
                    'speed':call(item,'GetSpeed'),'fades':call(item,'GetFades'),
                    'links':len(call(item,'GetLinkedItems',[]) or [])})
    return {'timeline_id':timeline.GetUniqueId(),'markers':timeline.GetMarkers() or {},'records':records}


def verify_shift(timeline,before,delta):
    after=capture_items(timeline)
    if after['timeline_id']!=before['timeline_id']:raise RuntimeError('Identità della timeline cambiata: spostamento non valido')
    if after['markers']!=before['markers']:raise RuntimeError('Marker modificati durante lo spostamento')
    def key(row):return row['kind'],row['track'],row['start'],row['end']
    expected=[]
    for row in before['records']:
        expected.append({**row,'start':row['start']+delta,'end':row['end']+delta})
    expected.sort(key=key);actual=sorted(after['records'],key=key)
    if len(expected)!=len(actual):raise RuntimeError('Numero di clip cambiato durante lo spostamento')
    for wanted,found in zip(expected,actual):
        fields=set(wanted)-{'id','item'}
        if any(wanted[k]!=found[k] for k in fields):raise RuntimeError('Tracce, tempi o proprietà delle clip non conservati nello spostamento')
    return after


def transfer_items(timeline,records,timecode,driver,guard):
    guard();driver.focus_timeline();driver.select_all();guard()
    selected={item.GetUniqueId() for item in timeline.GetSelectedClips() or []}
    if selected!={row['id'] for row in records}:raise RuntimeError('La selezione non comprende esattamente tutte le clip: nessun taglio eseguito')
    driver.cut();guard()
    deadline=time.monotonic()+4
    while True:
        guard()
        remaining=sum(len(timeline.GetItemListInTrack(kind,track) or []) for kind in ('video','audio','subtitle') for track in range(1,int(timeline.GetTrackCount(kind) or 0)+1))
        if not remaining:break
        if time.monotonic()>=deadline:raise RuntimeError('Taglia nativo incompleto: nessun CUT aggiunto. Recupero disponibile nel file di emergenza')
        time.sleep(.05)
    if not timeline.SetCurrentTimecode(timecode):raise RuntimeError('Impossibile impostare la posizione di recupero delle clip')
    driver.focus_timeline();guard();driver.paste();guard()


def shift_to_right(resolve,project,timeline,cut,*,recovery_root,driver=None):
    if driver is None:
        from .resolve_native_input import WindowsResolveInput
        driver=WindowsResolveInput(project.GetName())
    before=capture_items(timeline)
    if not before['records']:raise RuntimeError('Timeline vuota: nessun originale da conservare')
    if timeline.GetSetting('timelineDropFrameTimecode') not in ('0',0,None):raise RuntimeError('Spostamento su timeline drop-frame non ancora supportato: usa Nuova timeline')
    base=int(timeline.GetStartFrame());rate=Fraction(cut['fps']);fps=round(float(rate))
    first=min(row['start'] for row in before['records']);last=max(row['end'] for row in before['records'])
    # A gap keeps all parked content outside the final CUT and its export marks.
    offset=cut['duration_frames']+round(float(rate)*2)
    delta=base+offset-first
    frame=base+offset;hours,rest=divmod(frame,fps*3600);minutes,rest=divmod(rest,fps*60);seconds,frames=divmod(rest,fps)
    tc=f'{hours:02}:{minutes:02}:{seconds:02}:{frames:02}'
    root=Path(recovery_root).resolve();root.mkdir(parents=True,exist_ok=True)
    recovery=root/('before-apply-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.drt')
    # This is an external transaction recovery file, not another Media Pool timeline.
    if not timeline.Export(str(recovery),resolve.EXPORT_DRT,resolve.EXPORT_NONE) or not recovery.is_file() or not recovery.stat().st_size:
        raise RuntimeError('File di recupero non creato: nessuna clip spostata')
    locks=[(kind,track,bool(timeline.GetIsTrackLocked(kind,track))) for kind in ('video','audio','subtitle') for track in range(1,int(timeline.GetTrackCount(kind) or 0)+1)]
    current_id=timeline.GetUniqueId();project_name=project.GetName()
    def guard():
        active=resolve.GetProjectManager().GetCurrentProject()
        current=active.GetCurrentTimeline() if active else None
        if not active or active.GetName()!=project_name or not current or current.GetUniqueId()!=current_id:
            raise RuntimeError('Progetto o timeline cambiati: spostamento sospeso')
    try:
        if not resolve.OpenPage('edit'):raise RuntimeError('Pagina Edit non disponibile')
        for kind,track,locked in locks:
            if locked and timeline.SetTrackLock(kind,track,False) is False:raise RuntimeError('Impossibile sbloccare una traccia per lo spostamento')
        transfer_items(timeline,before['records'],tc,driver,guard)
        deadline=time.monotonic()+5
        while True:
            guard()
            try:
                after=verify_shift(timeline,before,delta)
                break
            except RuntimeError:
                if time.monotonic()>=deadline:raise
                time.sleep(.1)
        for row in after['records']:
            if row['item'].SetClipEnabled(False) is False:raise RuntimeError('Impossibile disattivare una clip originale conservata')
        result={'editable_archive':True,'name':'Timeline Backups','timeline':timeline,'clips':[r['item'] for r in after['records']],
            'markers':before['markers'],'properties':{},'recovery_path':str(recovery),'original_start_frame':base+offset,
            'original_end_frame':last+delta,'export_in_frame':base,'export_out_frame':base+cut['duration_frames']}
        report={k:v for k,v in result.items() if k not in ('timeline','clips')}
        report.update(timeline_id=current_id,clip_count=len(after['records']),offset_frames=delta,native_backup_forced=False)
        (recovery.with_suffix('.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
        return result
    except Exception as exc:
        raise RuntimeError(str(exc)+' · Recupero completo: '+str(recovery)) from exc
    finally:
        for kind,track,locked in locks:timeline.SetTrackLock(kind,track,locked)
