def choose_latest_complete(takes):
    if not takes:
        raise ValueError("Nessuna take candidata")
    complete = [take for take in takes if take.get("complete")]
    pool = complete or list(takes)
    selected = max(pool, key=lambda take: (take.get("take_index", 0), take.get("score", 0)))
    return {"selected": selected, "fallback": not bool(complete),
            "alternatives": [take for take in sorted(takes, key=lambda t: (t.get("take_index", 0), t.get("score", 0)), reverse=True)
                             if take is not selected]}


DEFAULT_PACING = {'enabled': True, 'max_pause_seconds': .45, 'minimum_shot_seconds': 1.2,
                  'respect_script_pauses': True, 'comic_hold_seconds': 1.0}


def pacing_options(options=None):
    import math
    result={**DEFAULT_PACING,**(options or {})}
    for key,lo,hi in [('max_pause_seconds',0,2),('minimum_shot_seconds',0,5),('comic_hold_seconds',0,3)]:
        value=result[key]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not lo<=value<=hi:
            raise ValueError('Regolazione ritmo non valida: '+key)
    for key in ['enabled','respect_script_pauses']:
        if not isinstance(result[key],bool):raise ValueError('Regolazione ritmo non valida: '+key)
    return {key:result[key] for key in DEFAULT_PACING}


def rms_silences(samples, sample_rate, fps):
    """Conservative low-energy detection, not a semantic/voice classifier."""
    import numpy as np
    if sample_rate<=0 or fps<=0:raise ValueError('Frequenza audio/video non valida')
    data=np.asarray(samples,dtype=np.float32)
    if data.ndim!=1 or not len(data) or not np.isfinite(data).all():raise ValueError('Audio PCM non valido')
    step=max(1,round(.02*sample_rate))
    rms=np.array([float(np.sqrt(np.mean(data[i:i+step].astype(np.float64)**2))) for i in range(0,len(data),step)])
    db=20*np.log10(np.maximum(rms,1e-9))
    floor=float(np.percentile(db,20));threshold=min(-22.,max(-48.,floor+9.))
    quiet=db<threshold
    spans=[];start=None
    for index,is_quiet in enumerate(list(quiet)+[False]):
        if is_quiet and start is None:start=index
        elif not is_quiet and start is not None:
            if (index-start)*step/sample_rate>=.18:
                spans.append({'start_frame':round(start*step/sample_rate*fps),
                              'end_frame':min(round(index*step/sample_rate*fps),round(len(data)/sample_rate*fps))})
            start=None
    return {'silences':spans,'threshold_dbfs':threshold,'noise_floor_dbfs':floor,
            'duration_frames':round(len(data)/sample_rate*fps),'method':'audio_rms_20ms_v1'}


def analyze_audio(source):
    import subprocess,shutil
    from pathlib import Path
    import numpy as np
    candidates=[shutil.which('ffmpeg'),r'C:\Program Files\FFmpeg\ffmpeg.exe']
    executable=next((str(p) for p in candidates if p and Path(p).is_file()),None)
    if executable is None:return {'status':'unavailable','reason':'FFmpeg non trovato: pause conservate senza tagli audio automatici'}
    path=Path(source['path'])
    if not path.is_file():raise ValueError('File audio/video non disponibile')
    fps=float(source.get('fps',25));seconds=float(source['duration_frames'])/fps
    if not 0<seconds<=3600:return {'status':'unavailable','reason':'Analisi audio limitata a clip di massimo un’ora'}
    command=[executable,'-nostdin','-hide_banner','-loglevel','error','-i',str(path),'-t',str(seconds),'-map','0:a:0','-vn','-ac','1','-ar','16000','-f','f32le','pipe:1']
    try:
        run=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=120,
                           creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except (OSError,subprocess.TimeoutExpired):return {'status':'unavailable','reason':'Decodifica audio non disponibile o scaduta: pause conservate'}
    if run.returncode or not run.stdout:return {'status':'unavailable','reason':'Traccia audio non decodificabile: pause conservate'}
    return {'status':'ok',**rms_silences(np.frombuffer(run.stdout,dtype='<f4'),16000,fps)}


def _speech_words(source):
    from transcript_align import normalize
    return sorted([w for seg in source.get('segments',[]) for w in seg.get('words',[])
                   if normalize(w.get('text','')) and w.get('text','').strip()!='(...)' and w['end_frame']>w['start_frame']],key=lambda w:w['start_frame'])


def _protected_beats(beats):
    import re
    protected=set();previous=None
    for beat in beats:
        if beat.get('kind')=='dialogue':previous=beat['beat_id']
        elif previous and re.search(r'\b(pausa|silenzio|attesa|attende|reazione)\b',beat.get('text',''),re.I):protected.add(previous)
    return protected


def pace_plan(plan, sources, audio, beats, fps, options=None):
    import copy
    settings=pacing_options(options)
    if not isinstance(fps,(float,int)) or fps<=0:raise ValueError('Frame rate non valido')
    result=copy.deepcopy(plan)
    base=copy.deepcopy(plan.get('base_decisions',plan.get('decisions',[])))
    result['base_decisions']=copy.deepcopy(base)
    decisions=copy.deepcopy(base)
    by_take={s.get('take_id'):s for s in sources};by_media={s['media_id']:s for s in sources}
    protected=_protected_beats(beats) if settings['respect_script_pauses'] else set()
    minimum=round(settings['minimum_shot_seconds']*fps)
    keep=max(round(settings['max_pause_seconds']*fps),round(.16*fps))
    removed=0;holds=0;short=0;protected_count=0;unavailable=set();cursor=0
    previous=None;group_duration=0
    for decision in decisions:
        if settings['enabled'] and previous and decision['end_frame']-decision['start_frame']<minimum and decision['media_id']!=previous['media_id'] and not decision.get('manual') and decision.get('narrative_role','free')=='free':
            good=[a for a in decision.get('alternatives',[]) if a.get('speaker_coverage') != 'absent' and (decision.get('speaker_coverage') != 'visible' or a.get('speaker_coverage') == 'visible') and a['media_id']==previous['media_id'] and a.get('score',0)>=decision.get('score',0)-.025 and a['media_id'] in by_media]
            if good:
                alt=max(good,key=lambda a:a.get('score',0));original=copy.deepcopy(decision)
                decision.update({k:v for k,v in alt.items() if k!='alternatives'})
                decision['matched_start_frame']=alt['start_frame'];decision['matched_end_frame']=alt['end_frame']
                decision['alternatives']=[{k:v for k,v in original.items() if k!='alternatives'}]+decision.get('alternatives',[])
                decision['shot_size']=previous.get('shot_size','unknown')
                decision.setdefault('rationale_codes',[]).append('HOLD_COVERAGE_FOR_SHORT_REPLY');holds+=1
        source=by_take.get(decision.get('take_id')) or by_media.get(decision['media_id'])
        if not source:raise ValueError('Sorgente del piano non disponibile')
        lo,hi=int(decision['start_frame']),int(decision['end_frame'])
        floor=source.get('start_frame',0);ceiling=source.get('end_frame',source['duration_frames'])
        if lo<floor or hi>ceiling or hi<=lo:raise ValueError('Intervallo fuori dalla take')
        words=_speech_words(source)
        measured=audio.get(decision['media_id'],{})
        active=settings['enabled'] and measured.get('status')=='ok'
        if settings['enabled'] and not active:unavailable.add(decision['media_id'])
        protect=bool(decision['preserve_pause']) if 'preserve_pause' in decision else decision.get('beat_id') in protected or decision.get('narrative_role')=='tension'
        if protect and settings['enabled']:protected_count+=1
        silences=measured.get('silences',[]) if active else []
        original_lo,original_hi=lo,hi
        original_length=hi-lo
        if active and protect:
            matched_end=decision.get('matched_end_frame',hi)
            gap=next((s for s in silences if s['start_frame']<=matched_end+round(.08*fps) and s['end_frame']>matched_end),None)
            if gap:
                next_word=min((w['start_frame'] for w in words if w['start_frame']>=matched_end),default=ceiling)
                hi=max(hi,min(ceiling,gap['end_frame'],next_word,matched_end+round(settings['comic_hold_seconds']*fps)))
        edge_removed=0
        if active and not protect and not decision.get('manual'):
            relevant=[w for w in words if w['start_frame']<hi and w['end_frame']>lo]
            first=min((w['start_frame'] for w in relevant),default=hi)
            last=max((w['end_frame'] for w in relevant),default=lo)
            new_lo,new_hi=lo,hi
            for silence in silences:
                if silence['start_frame']<=lo<silence['end_frame']:
                    new_lo=max(lo,min(silence['end_frame'],first)-round(.12*fps))
                if silence['start_frame']<hi<=silence['end_frame']:
                    new_hi=min(hi,max(silence['start_frame'],last)+round(.25*fps))
            if relevant and new_hi-new_lo>=minimum:
                edge_removed=(new_lo-lo)+(hi-new_hi);lo,hi=new_lo,new_hi
        cuts=[]
        if active and not protect and not decision.get('manual'):
            # Silence alone is insufficient: never discard an ASR word interval.
            for silence in silences:
                a,b=max(lo,silence['start_frame']),min(hi,silence['end_frame'])
                if b<=a:continue
                pieces=[(a,b)]
                for word in words:
                    if word['end_frame']<=a or word['start_frame']>=b:continue
                    remainder=[]
                    for x,y in pieces:
                        if word['end_frame']<=x or word['start_frame']>=y:remainder.append((x,y))
                        else:
                            if x<word['start_frame']:remainder.append((x,word['start_frame']))
                            if word['end_frame']<y:remainder.append((word['end_frame'],y))
                    pieces=remainder
                for x,y in pieces:
                    if y-x<=keep+round(.18*fps):continue
                    # Leave real breathing room, and avoid producing flash edits.
                    left=x+keep//2;right=y-(keep-keep//2)
                    segment_start=cuts[-1][1] if cuts else lo
                    if left-segment_start<minimum or hi-right<minimum:continue
                    cuts.append((left,right))
        ranges=[];position=lo
        for a,b in sorted(cuts):
            if a<position:continue
            ranges.append({'start_frame':position,'end_frame':a});position=b
        ranges.append({'start_frame':position,'end_frame':hi})
        duration=sum(r['end_frame']-r['start_frame'] for r in ranges)
        cut_frames=edge_removed+sum(b-a for a,b in cuts)
        removed+=cut_frames
        if previous and previous['media_id']==decision['media_id'] and previous.get('shot_size')==decision.get('shot_size'):group_duration+=duration
        else:group_duration=duration
        exception=settings['enabled'] and group_duration<minimum
        if exception:short+=1
        decision.update({'start_frame':lo,'end_frame':hi,'source_ranges':ranges,'timeline_start_frame':cursor,
                         'pacing':{'removed_frames':cut_frames,'protected_pause':protect,'short_exception':bool(exception),
                                   'input_start_frame':original_lo,'input_end_frame':original_hi,'audio_measured':active,'duration_frames':duration,'added_hold_frames':max(0,hi-lo-original_length)}})
        cursor+=duration;previous=decision
    groups=[]
    for decision in decisions:
        if groups and groups[-1][-1]['media_id']==decision['media_id'] and groups[-1][-1].get('shot_size')==decision.get('shot_size'):groups[-1].append(decision)
        else:groups.append([decision])
    short=0
    for group in groups:
        exception=settings['enabled'] and sum(d['pacing']['duration_frames'] for d in group)<minimum
        short+=int(exception)
        for decision in group:decision['pacing']['short_exception']=bool(exception)
    result['decisions']=decisions
    result['pacing_settings']=settings
    result['pacing_summary']={'removed_frames':removed,'removed_seconds':round(removed/fps,3),'duration_frames':cursor,
                              'protected_beats':protected_count,'coverage_holds':holds,'short_shot_exceptions':short,
                              'unavailable_media':sorted(unavailable),'measured_media':sum(v.get('status')=='ok' for v in audio.values())}
    return result
