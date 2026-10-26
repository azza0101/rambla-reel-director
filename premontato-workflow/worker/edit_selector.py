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
    from local_audio import load_pcm16
    from time import perf_counter
    import numpy as np
    try:
        clock=perf_counter();audio,metadata=load_pcm16(source);pcm_seconds=perf_counter()-clock
        clock=perf_counter();measured=rms_silences(audio.astype(np.float32)/32768,16000,float(source.get('fps') or 25));scan_seconds=perf_counter()-clock
        return {'status':'ok',**measured,'pcm_cache_hit':metadata['cache_hit'],'timing':{'pcm_seconds':pcm_seconds,'rms_seconds':scan_seconds}}
    except Exception as error:return {'status':'unavailable','reason':str(error)+': pause conservate'}


from runtime_trace import trace_rms

@trace_rms
def cached_audio(source):
    """One RMS cache for IPC, listening inserts and script breaths."""
    import os
    from pathlib import Path
    from cache import get_cache,cache_key,write_cache
    try:
        stat=Path(source['path']).stat()
        fingerprint=f"{source['media_id']}:{stat.st_size}:{stat.st_mtime_ns}"
    except (KeyError,OSError):
        return {**analyze_audio(source),'cache_hit':False}
    options={'fps':source.get('fps',25),'duration_frames':source['duration_frames']}
    root=os.environ.get('PREMONTATO_CACHE_DIR','.premontato-cache')
    cached=get_cache(root,fingerprint,'audio-rms-v1',options)
    if cached is not None:return {**cached,'cache_hit':True}
    result=analyze_audio(source)
    if result.get('status')=='ok':write_cache(root,cache_key(fingerprint,'audio-rms-v1',options),result)
    return {**result,'cache_hit':False}


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


def _reaction_preview(source, start, end):
    if not source.get('path'):return None
    cap=None
    try:
        import cv2,base64
        cap=cv2.VideoCapture(str(source['path']));frame_number=(start+end)//2
        cap.set(cv2.CAP_PROP_POS_FRAMES,frame_number);ok,frame=cap.read()
        if not ok:return None
        frame=cv2.resize(frame,(480,max(1,round(frame.shape[0]*480/frame.shape[1]))))
        ok,data=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,70])
        return {'frame':frame_number,'image':'data:image/jpeg;base64,'+base64.b64encode(data).decode()} if ok else None
    except Exception:return None
    finally:
        if cap is not None:cap.release()


def verified_reaction(decision, previous, sources, audio, beats, shots, fps, minimum, occupied=None):
    """A real silent preroll of the answering actor, never arbitrary reaction B-roll."""
    from shot_analyzer import speaker_coverage
    if not previous or previous.get('narrative_role')!='tension' or decision.get('narrative_role')!='resolution':return None
    if decision.get('manual') or decision.get('reaction_enabled') is False:return None
    character=next((b.get('character') for b in beats if b.get('beat_id')==decision['beat_id']),None)
    if not character:return None
    duration=max(round(.8*fps),minimum);margin=max(1,round(.12*fps))
    if duration>5*fps:return None
    candidates=[]
    for row in [decision,*decision.get('alternatives',[])]:
        if row.get('shot_size')!='close' or row.get('speaker_coverage')!='visible':continue
        source=next((s for s in sources if s.get('take_id')==row.get('take_id') and s['media_id']==row['media_id']),None)
        measured=audio.get(row['media_id'],{})
        if not source or measured.get('status')!='ok':continue
        anchor=row.get('matched_start_frame',row['start_frame'])
        floor=source.get('start_frame',0);ceiling=source.get('end_frame',source['duration_frames'])
        words=_speech_words(source)
        for silence in measured.get('silences',[]):
            end=min(anchor-margin,silence['end_frame'],ceiling)
            start=end-duration
            if start<max(floor,silence['start_frame']) or anchor-end>round(.6*fps):continue
            if any(w['start_frame']<end and start<w['end_frame'] for w in words):continue
            retained=[r for d in occupied or [] if d['media_id']==row['media_id'] for r in d.get('source_ranges',[d])]
            if any(r['start_frame']<end and start<r['end_frame'] for r in retained):continue
            if speaker_coverage(shots,row['media_id'],start,end,character)!='visible':continue
            if not any(s.get('media_id')==row['media_id'] and s.get('reviewed') and s.get('shot_size')=='close' and s['start_frame']<=start and s['end_frame']>=end for s in shots):continue
            reaction={'kind':'reaction','media_id':row['media_id'],'take_id':row['take_id'],'start_frame':start,'end_frame':end,'shot_size':'close','character':character,'enabled':True,'basis':'verified_silent_preroll','speaker_coverage':'visible'}
            candidates.append((source.get('take_index',0),row.get('score',0),reaction,source))
    if not candidates:return None
    _,_,reaction,source=max(candidates,key=lambda x:(x[0],x[1]))
    preview=_reaction_preview(source,reaction['start_frame'],reaction['end_frame'])
    if preview:reaction['still']=preview
    return reaction


def pace_plan(plan, sources, audio, beats, fps, options=None, shots=None):
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
        # Keep this angle continuous; shortening an internal silence creates a jump.
        cuts=[]
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
    # Extending a protected pause must never replay the next selected utterance's
    # preroll on the same source. Clamp only added silence, never matched speech.
    for left,right in zip(decisions,decisions[1:]):
        boundary=right['start_frame']
        if left['media_id']==right['media_id'] and not left.get('manual') and left.get('matched_end_frame',left['end_frame'])<=boundary<left['end_frame']:
            overlap=left['end_frame']-boundary
            left['source_ranges']=[{'start_frame':r['start_frame'],'end_frame':min(r['end_frame'],boundary)} for r in left['source_ranges'] if r['start_frame']<boundary]
            left['end_frame']=boundary
            left['pacing']['duration_frames']=sum(r['end_frame']-r['start_frame'] for r in left['source_ranges'])
            left['pacing']['added_hold_frames']=max(0,left['pacing']['added_hold_frames']-overlap)
            left.setdefault('rationale_codes',[]).append('HOLD_CLAMPED_TO_NEXT_BEAT')
    from continuity_editor import preserve_continuity
    continuity=preserve_continuity(decisions,sources,beats,fps)
    result.setdefault('warnings',[]).extend(continuity['warnings'])
    groups=[]
    for decision in decisions:
        if groups and groups[-1][-1]['media_id']==decision['media_id'] and groups[-1][-1].get('shot_size')==decision.get('shot_size'):groups[-1].append(decision)
        else:groups.append([decision])
    short=0
    for group in groups:
        exception=settings['enabled'] and sum(d['pacing']['duration_frames'] for d in group)<minimum
        short+=int(exception)
        for decision in group:decision['pacing']['short_exception']=bool(exception)
    reactions=0;cursor=0;previous=None;occupied=list(decisions)
    for decision in decisions:
        decision.pop('reaction_before',None)
        from listening_reaction import listening_overlay
        overlay=listening_overlay(decision,previous,sources,fps,minimum,decisions)
        if overlay:
            previous['reaction_overlay']=overlay
            decision['reaction_status']='inserted_listening'
            reactions+=1
        reaction=None if overlay else verified_reaction(decision,previous,sources,audio,beats,shots or [],fps,minimum,occupied)
        requested=previous and previous.get('narrative_role')=='tension' and decision.get('narrative_role')=='resolution'
        if reaction:
            reaction['timeline_start_frame']=cursor
            occupied.append(reaction)
            decision['reaction_before']=reaction;cursor+=reaction['end_frame']-reaction['start_frame'];reactions+=1
            decision['reaction_status']='inserted'
        elif overlay:pass
        elif requested:decision['reaction_status']='disabled' if decision.get('reaction_enabled') is False else 'unavailable'
        else:decision.pop('reaction_status',None)
        decision['timeline_start_frame']=cursor;cursor+=decision['pacing']['duration_frames']
        for action in decision.get('action_after',[]):
            action['timeline_start_frame']=cursor;cursor+=action['end_frame']-action['start_frame']
        previous=decision
    result['decisions']=decisions
    result['pacing_settings']=settings
    result['pacing_summary']={'removed_frames':removed,'removed_seconds':round(removed/fps,3),'duration_frames':cursor,
                              'reaction_count':reactions,'action_count':continuity['action_count'],'protected_beats':protected_count,'coverage_holds':holds,'short_shot_exceptions':short,
                              'unavailable_media':sorted(unavailable),'measured_media':sum(v.get('status')=='ok' for v in audio.values())}
    return result
