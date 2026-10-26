"""Listening cutaway over the original preceding dialogue audio."""
def listening_overlay(decision,previous,sources,fps,minimum,occupied=None):
    minimum=max(minimum,__import__('math').ceil(1.5*fps))
    if not previous or previous.get('narrative_role')!='tension' or decision.get('narrative_role')!='resolution':return None
    if decision.get('manual') or previous.get('manual') or decision.get('reaction_enabled') is False:return None
    ranges=previous.get('source_ranges',[previous]);available=sum(r['end_frame']-r['start_frame'] for r in ranges)
    duration=max(round(2*fps),minimum);margin=max(1,round(.12*fps))
    if duration>min(available-round(.8*fps),round(3*fps)):return None
    from active_speaker import verify_listener
    candidates=sorted([decision,*decision.get('alternatives',[])],key=lambda r:r.get('score',0),reverse=True)
    for row in candidates:
        if row['media_id']==previous['media_id']:continue
        if row.get('shot_size') not in {'close','medium'} or row.get('speaker_coverage')=='absent':continue
        source=next((s for s in sources if s['media_id']==row['media_id'] and s.get('take_id')==row.get('take_id')),None)
        if not source:continue
        anchor=row.get('matched_start_frame',row['start_frame']);end=anchor-margin;start=end-duration
        if start<source.get('start_frame',0) or end>source.get('end_frame',source['duration_frames']):continue
        retained=[r for d in occupied or [] if d['media_id']==row['media_id'] for r in d.get('source_ranges',[d])]+[r for d in occupied or [] for r in d.get('action_after',[]) if r['media_id']==row['media_id']]
        if any(r['start_frame']<end and start<r['end_frame'] for r in retained):continue
        try:proof=verify_listener(source,start,end,anchor,row.get('matched_end_frame',row['end_frame']))
        except Exception:continue
        if not proof.get('verified'):continue
        return {'kind':'reaction','basis':'verified_listener','media_id':row['media_id'],'take_id':row['take_id'],'start_frame':start,'end_frame':end,'offset_frames':available-duration,'shot_size':row['shot_size'],'character':decision.get('dialogue_character',''),'speaker_coverage':'visible','enabled':True,'evidence':proof}
    return None

def _retained(decisions,media_id):
    rows=[]
    for d in decisions:
        if d['media_id']==media_id:rows.extend(d.get('source_ranges',[d]))
        rows.extend(a for a in d.get('action_after',[]) if a['media_id']==media_id)
        o=d.get('reaction_overlay')
        if o and o['media_id']==media_id:rows.append(o)
    return rows

def add_dialogue_listening(decisions,candidates,sources,beats,profiles,fps,minimum,events=None):
    """Same-beat listening coverage; original speaking audio remains untouched."""
    from active_speaker import verify_listener
    from edit_selector import analyze_audio
    minimum=max(minimum,__import__('math').ceil(1.5*fps))
    by_media={s['media_id']:s for s in sources};rooms={}
    for b in beats:
        if b.get('kind')=='dialogue' and b.get('character'):rooms.setdefault(b.get('scene_id'),set()).add(b['character'])
    partners={r:set().union(*(cast-{r} for cast in rooms.values() if r in cast)) for r in set().union(*rooms.values())} if rooms else {}
    from editorial_director import resolve_event,listening_window,existing_listener
    reactions=[];cursor=0;last=-10*fps;directed=events is not None;events=events or []
    for i,d in enumerate(decisions):
        length=sum(r['end_frame']-r['start_frame'] for r in d.get('source_ranges',[d]));at=cursor;cursor+=length
        if d.get('reaction_overlay') or d.get('manual') or d.get('reaction_enabled') is False:continue
        event=resolve_event(d,events)
        if event and not event.get('reactor_character'):continue
        if event:d['editorial_event']={**event,'status':'searching_coverage'}
        if existing_listener(d,event,profiles,fps):
            profile=profiles[d['media_id']]
            try:base_proof=verify_listener(by_media[d['media_id']],d['start_frame'],d['end_frame'],profile['start'],profile['end'])
            except Exception:base_proof={}
            if base_proof.get('verified'):
                d['editorial_event']['status']='covered_by_base'
                d['editorial_event']['evidence']=base_proof
                continue
        extra=0
        required=minimum+round(.8*fps)-length
        if event and event.get('return_to_speaker') is False and 0<required<=round(.5*fps):
            source=by_media[d['media_id']];end=d['end_frame']+required
            try:measured=analyze_audio(source)
            except Exception:measured={}
            silent=measured.get('status')=='ok' and any(g['start_frame']<=d['end_frame'] and g['end_frame']>=end for g in measured.get('silences',[]))
            words=[w for seg in source.get('segments',[]) for w in seg.get('words',[]) if w['end_frame']>w['start_frame']]
            clear=not any(w['start_frame']<end and d['end_frame']<w['end_frame'] for w in words) and not any(r['start_frame']<end and d['end_frame']<r['end_frame'] for r in _retained(decisions,d['media_id']))
            if silent and clear and end<=source.get('end_frame',source['duration_frames']):extra=required
        virtual={**d,'end_frame':d['end_frame']+extra,'source_ranges':[dict(r) for r in d.get('source_ranges',[d])]}
        virtual['source_ranges'][-1]['end_frame']+=extra
        window=listening_window(virtual,event,by_media[d['media_id']],fps,minimum)
        if window is None:
            if event:d['editorial_event']['status']='insufficient_readable_time_or_anchor'
            continue
        offset=window['offset'];duration=window['duration'];returning=window['return_to_speaker']
        spacing=minimum if event and event.get('priority')=='high' else 4*fps
        if at+offset-last<spacing:
            if event:d['editorial_event']['status']='reaction_density_limit'
            continue
        nxt=decisions[i+1] if i+1<len(decisions) else None
        ranked=sorted(candidates[i],key=lambda row:row.get('semantic',0),reverse=True)
        for row in ranked:
            mid=row['media_id'];profile=profiles.get(mid);source=by_media.get(mid)
            if mid==d['media_id'] or not profile or not source or row.get('shot_size') not in {'close','medium'}:continue
            if profile['role'] not in partners.get(d.get('dialogue_character'),set()):continue
            if event and event.get('reactor_character') and profile['role']!=event['reactor_character']:continue
            end=row.get('matched_end_frame',row['end_frame'])
            if not returning and nxt and nxt['media_id']==mid:
                if abs(nxt['start_frame']-end)>fps:continue
                end=nxt['start_frame']
            start=end-duration
            if start<source.get('start_frame',0) or end>source.get('end_frame',source['duration_frames']):continue
            if any(r['start_frame']<end and start<r['end_frame'] for r in _retained(decisions,mid)):continue
            try:proof=verify_listener(source,start,end,profile['start'],profile['end'])
            except Exception:continue
            if not proof.get('verified'):continue
            overlay={'kind':'reaction','basis':'verified_listener','media_id':mid,'take_id':row['take_id'],'start_frame':start,'end_frame':end,'offset_frames':offset,'shot_size':row['shot_size'],'character':profile['role'],'speaker_coverage':'visible','enabled':True,'evidence':{**proof,'alignment':row.get('alignment_basis','same_script_beat')}}
            if extra:
                d['end_frame']+=extra
                if d.get('source_ranges'):d['source_ranges'][-1]['end_frame']+=extra
                d.setdefault('pacing',{})['duration_frames']=length+extra
                d.setdefault('warnings',[]).append('Coda ambiente misurata conservata per evitare una reazione troppo breve.')
                cursor+=extra
            overlay['return_to_speaker']=returning
            if event:d['editorial_event']['status']='inserted';overlay['editorial_reason']=event.get('reason','')
            d['reaction_overlay']=overlay;reactions.append(overlay);last=at+offset+duration;break
        if event and d['editorial_event']['status']=='searching_coverage':d['editorial_event']['status']='no_verified_coverage'
    return reactions

def add_scripted_breaths(decisions,sources,beats,profiles,fps,audio=None):
    """Short continuous holds only on explicit script pauses and measured silent source."""
    import re
    from active_speaker import verify_listener
    from edit_selector import analyze_audio
    by_media={s['media_id']:s for s in sources};positions={b['beat_id']:i for i,b in enumerate(beats)};audio={} if audio is None else audio;holds=[]
    for i,d in enumerate(decisions):
        if d.get('manual') or d.get('action_after'):continue
        nxt=decisions[i+1] if i+1<len(decisions) else None
        if nxt and nxt['beat_id']==d['beat_id']:continue
        between=beats[positions[d['beat_id']]+1:positions[nxt['beat_id']] if nxt else len(beats)]
        pauses=[b for b in between if b.get('kind')=='action' and re.search(r'silenz|tens|guarda|sospett|^nulla$',b.get('text',''),re.I)]
        if not pauses:continue
        overlay=d.get('reaction_overlay');length=sum(r['end_frame']-r['start_frame'] for r in d.get('source_ranges',[d]))
        view=overlay if overlay and overlay['offset_frames']+overlay['end_frame']-overlay['start_frame']==length else d
        mid=view['media_id'];source=by_media[mid];profile=profiles.get(mid)
        if not profile:continue
        if mid not in audio:
            try:audio[mid]=analyze_audio(source)
            except Exception:audio[mid]={}
        measured=audio[mid]
        if measured.get('status')!='ok':continue
        start=view['end_frame'];gap=next((g for g in measured.get('silences',[]) if g['start_frame']<=start and g['end_frame']>start),None)
        if not gap:continue
        end=min(gap['end_frame'],start+round(.8*fps),source.get('end_frame',source['duration_frames']))
        if any(w['start_frame']<end and start<w['end_frame'] for seg in source.get('segments',[]) for w in seg.get('words',[]) if w['end_frame']>w['start_frame']):continue
        if any(r['start_frame']<end and start<r['end_frame'] for r in _retained(decisions,mid)):continue
        if nxt and nxt['media_id']==mid and end!=nxt['start_frame']:continue
        if end-start<round(.4*fps):continue
        try:proof=verify_listener(source,start,end,profile['start'],profile['end'])
        except Exception:continue
        if not proof.get('verified'):continue
        hold={'kind':'action','basis':'script_measured_hold','beat_id':pauses[0]['beat_id'],'media_id':mid,'take_id':view['take_id'],'start_frame':start,'end_frame':end,'shot_size':view['shot_size'],'evidence':{**proof,'silence_measured':True}}
        d['action_after']=[hold];holds.append(hold)
    return holds
