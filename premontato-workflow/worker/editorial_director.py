"""Grounded narrative intentions; local timing and footage remain authoritative."""
import re,math
from transcript_align import normalize

def find_anchor_end(source,start,end,anchor):
    wanted=normalize(anchor).split();tokens=[]
    if not wanted:return None
    for seg in source.get('segments',[]):
        for word in seg.get('words',[]):
            if word['start_frame']<start or word['end_frame']>end or word['end_frame']<=word['start_frame']:continue
            tokens.extend((token,word['end_frame']) for token in normalize(word.get('text','')).split())
    for i in range(len(tokens)-len(wanted)+1):
        if [t[0] for t in tokens[i:i+len(wanted)]]==wanted:return tokens[i+len(wanted)-1][1]
    return None

def resolve_event(decision,events):
    text=' '+normalize(decision.get('matched_text',decision.get('text','')))+' '
    rows=[e for e in events if e.get('beat_id')==decision['beat_id'] and ' '+normalize(e.get('anchor_text',''))+' ' in text]
    return max(rows,key=lambda e:e.get('priority')=='high') if rows else None

def listening_window(decision,event,source,fps,minimum):
    length=sum(r['end_frame']-r['start_frame'] for r in decision.get('source_ranges',[decision]));minimum=max(minimum,math.ceil(1.5*fps))
    ending=bool(event and event.get('return_to_speaker') is False and event.get('hold_reason') in {'listener_answers','gag_ending','suspense'})
    if ending:
        duration=min(round(2.2*fps),length-round(.8*fps))
        return {'offset':length-duration,'duration':duration,'return_to_speaker':False} if duration>=minimum else None
    offset=math.ceil(1.5*fps)
    if event:
        anchor=find_anchor_end(source,decision.get('matched_start_frame',decision['start_frame']),decision.get('matched_end_frame',decision['end_frame']),event.get('anchor_text',''))
        if anchor is None:return None
        offset=max(round(.8*fps),anchor-decision['start_frame']+round(.08*fps))
    duration=min(round(2.2*fps),length-offset-math.ceil(1.5*fps))
    if duration<minimum:return None
    return {'offset':offset,'duration':duration,'return_to_speaker':True}

def valid_editorial(payload,beats):
    data=payload.get('editorial') or {};cast=(payload.get('prepared') or {}).get('cast',{});ids={b['beat_id'] for b in beats};result=[]
    for e in data.get('events',[]):
        if e.get('beat_id') not in ids or not isinstance(e.get('anchor_text'),str) or len(e['anchor_text'])>100:continue
        reactor=e.get('reactor')
        if reactor is not None and reactor not in cast:continue
        if not isinstance(e.get('return_to_speaker'),bool):continue
        result.append({**e,'reactor_character':cast.get(reactor)})
    return result

def offcamera_candidates(decision,units,labels,sources,profiles,similarities,index,beats,event):
    """Additional discarded-ASR candidates need context plus later inactive-face proof."""
    if not event or not event.get('reactor_character'):return []
    result=[];positions={b['beat_id']:i for i,b in enumerate(beats)};position=positions[decision['beat_id']]
    cues=re.compile(r'\b(stop|ciak|azione|rifai|rifacciamo|pronti|posizione|microfono|telecamera|regia|occhiali|acqua|guardami|girati)\b',re.I)
    for j,u in enumerate(units):
        source=sources[u['clip']];profile=profiles.get(source['media_id'])
        if not profile or profile['role']!=event['reactor_character'] or source['media_id']==decision['media_id'] or labels[u['id']]!='X' or cues.search(u['text']):continue
        similarity=float(similarities[index,j])
        a=set(normalize(u['text']).split());b=set(normalize(decision.get('matched_text','')).split())
        if similarity<.48 or len(a&b)<3:continue
        near=[v for v in units if v['clip']==u['clip'] and labels[v['id']]!='X' and min(abs(v['start']-u['end']),abs(u['start']-v['end']))<=10*float(source.get('fps') or 25)]
        def close(v):
            number=int(labels[v['id']].split('/')[0])-1
            return 0<=number<len(beats) and abs(number-position)<=3
        if not any(close(v) for v in near):continue
        result.append({'media_id':source['media_id'],'take_id':source['take_id'],'start_frame':u['start'],'end_frame':u['end'],'matched_end_frame':u['end'],'shot_size':source.get('_editorial_shot_size','unknown'),'semantic':similarity,'alignment_basis':'semantic_context_unclassified'})
    return result

def existing_listener(decision,event,profiles,fps):
    profile=profiles.get(decision.get('media_id'),{})
    length=sum(r['end_frame']-r['start_frame'] for r in decision.get('source_ranges',[decision]))
    return bool(event and event.get('reactor_character') and profile.get('role')==event['reactor_character'] and decision.get('speaker_coverage') in {'offscreen','absent'} and length>=math.ceil(1.5*fps))
