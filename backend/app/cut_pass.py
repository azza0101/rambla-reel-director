"""Non-destructive CUT plan with one frame-based source/edited time map."""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
import math
import re
from difflib import SequenceMatcher


def words_of(transcript):
    words = [dict(w) for s in transcript.get('segments', []) for w in s.get('words', [])]
    previous = -1.
    for index, w in enumerate(words):
        w['text'] = str(w.get('text') or w.get('word') or '').strip()
        start, end = float(w['start']), float(w['end'])
        if not w['text'] or not math.isfinite(start+end) or start < 0 or end <= start or start < previous:
            raise ValueError('Timestamp parola non validi')
        w.update(index=index, start=start, end=end)
        previous = start
    if not words:
        raise ValueError('Trascrizione senza parole')
    return words


def prepare_suggestions(suggestion):
    """Take decisions own their words; discard suggestions never override them."""
    groups=sorted(suggestion.get('groups',[]),key=lambda g:g['takes'][0][0])
    occupied=set()
    for g in groups:
        for a,b in g['takes']:occupied.update(range(a,b+1))
    discards=[];warnings=[]
    for d in suggestion.get('discards',[]):
        a,b=d['range']
        if type(a) is not int or type(b) is not int or a<0 or b<a:
            raise ValueError('Intervallo scarto non valido')
        pending=[i for i in range(a,b+1) if i not in occupied]
        if len(pending)!=b-a+1:
            warnings.append('Uno scarto sovrapposto è stato limitato alle parole esterne alle take.')
        blocks=[]
        for i in pending:
            if blocks and i==blocks[-1][1]+1:blocks[-1][1]=i
            else:blocks.append([i,i])
        for pair in blocks:
            discards.append({**d,'range':pair})
            occupied.update(range(pair[0],pair[1]+1))
    return groups,discards,warnings


def build_cut_plan(transcript, *, duration, fps, signature, groups, discards=(), pause_threshold=1.2, breathing=.18, excluded_word_indices=(), tight_pauses=False, pause_mode="soft", silence_intervals=(), end_margin_ms=0):
    if transcript.get('timing_basis') != 'cloud_asr_word_timestamps':
        raise ValueError('CUT richiede timestamp misurati per parola')
    rate = Fraction(str(fps)).limit_denominator(100000)
    if rate <= 0 or not math.isfinite(float(duration)) or duration <= 0:
        raise ValueError('Durata/FPS non validi')
    words = words_of(transcript)
    total = math.ceil(float(duration)*rate)
    if words[-1]['end'] > duration + .25:
        raise ValueError('Parole oltre la durata della sorgente')
    if not .05 <= breathing <= .5 or not .5 <= pause_threshold <= 5:
        raise ValueError('Parametri pause non validi')
    if type(tight_pauses) is not bool:raise ValueError('Scelta pause non valida')
    normal_pause_threshold,normal_breathing=pause_threshold,breathing
    if pause_mode not in {'soft','medium','strong'}:raise ValueError('Modalità pause non valida')
    if tight_pauses:pause_threshold,breathing={'soft':(.45,.10),'medium':(.30,.08),'strong':(.18,.06)}[pause_mode]
    removed, occupied, normalized, alternatives = set(), set(), [], []
    protected=[]
    for group in groups:
        takes = group.get('takes', [])
        if len(takes) < 2:
            raise ValueError('Un gruppo richiede almeno due take')
        indexes = []
        previous_end = -1
        for take in takes:
            if len(take) != 2 or any(type(x) is not int for x in take):
                raise ValueError('Indici take non validi')
            a,b = take
            if not 0 <= a <= b < len(words) or a <= previous_end:
                raise ValueError('Take sovrapposte o fuori trascrizione')
            previous_end = b
            indexes.extend(range(a,b+1))
        if occupied.intersection(indexes):
            raise ValueError('Gruppi sovrapposti')
        occupied.update(indexes)
        selected = group.get('selected_take',len(takes)-1)
        if type(selected) is not int or not -2 <= selected < len(takes):
            raise ValueError('Take selezionata non valida')
        confidence = float(group.get('confidence',0))
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError('Confidenza non valida')
        # Ambiguous suggestions retain every word until explicitly reviewed.
        if confidence < .85 and 'selected_take' not in group:
            selected = -1
        for i,(a,b) in enumerate(takes):
            if selected != -1 and i != selected:
                removed.update(range(a,b+1))
        # A rejected take may accidentally include a new, independent passage.
        # Preserve long unmatched continuations instead of silently deleting them.
        protected.extend(group.get('separated_passages',[]))
        if selected >= 0 and not group.get('boundaries_reviewed'):
            token=lambda w: re.sub(r'[^\w]', '', w['text'].casefold())
            for ti,(a,b) in enumerate(takes):
                if ti==selected: continue
                candidate=[token(w) for w in words[a:b+1]]
                matched_end=0; matched_count=0
                for oi,(oa,ob) in enumerate(takes):
                    if oi==ti: continue
                    blocks=[x for x in SequenceMatcher(None,candidate,[token(w) for w in words[oa:ob+1]],autojunk=False).get_matching_blocks() if x.size>=3]
                    if blocks:
                        matched_end=max(matched_end,max(x.a+x.size for x in blocks))
                        matched_count=max(matched_count,sum(x.size for x in blocks))
                if matched_count>=6 and len(candidate)-matched_end>=8:
                    tail=list(range(a+matched_end,b+1))
                    removed.difference_update(tail)
                    protected.append({'range':[tail[0],tail[-1]],'reason':'Continuazione distinta dalla frase ripetuta: conservata per verifica.'})
        row = {**group,'selected_take':selected,'takes':takes}
        row['texts'] = [' '.join(w['text'] for w in words[a:b+1]) for a,b in takes]
        row['source_ranges'] = [{'start':words[a]['start'],'end':words[b]['end'],
            'in_frame':math.floor(words[a]['start']*rate),'out_frame':math.ceil(words[b]['end']*rate)} for a,b in takes]
        normalized.append(row)
        if selected >= 0:
            alt_index = selected-1 if selected>0 else 1
            a,b = takes[alt_index]
            alternatives.append({'group_index':len(normalized)-1,'take_index':alt_index,
                'text':row['texts'][alt_index], 'source_in_frame':max(0,math.floor(words[a]['start']*rate)),
                'source_out_frame':min(total,math.ceil(words[b]['end']*rate)),
                'anchor_word_index':takes[selected][0], 'enabled':False})
    normalized_discards=[]
    for discard in discards:
        a,b=discard['range']
        if type(a) is not int or type(b) is not int or not 0<=a<=b<len(words):
            raise ValueError('Intervallo scarto non valido')
        indexes=set(range(a,b+1))
        if occupied.intersection(indexes): raise ValueError('Scarto sovrapposto a una take')
        occupied.update(indexes)
        confidence=float(discard.get('confidence',0))
        if not math.isfinite(confidence) or not 0<=confidence<=1: raise ValueError('Confidenza non valida')
        keep=discard.get('keep',confidence<.85)
        if type(keep) is not bool: raise ValueError('Scelta scarto non valida')
        if not keep: removed.update(indexes)
        normalized_discards.append({**discard,'keep':keep,'text':' '.join(w['text'] for w in words[a:b+1])})
    automatic_removed=sorted(removed)
    excluded=set(excluded_word_indices)
    if any(type(i) is not int or not 0<=i<len(words) for i in excluded):
        raise ValueError('Parole escluse non valide')
    removed.update(excluded)
    if not isinstance(end_margin_ms, (int,float)) or not 0 <= end_margin_ms <= 400:
        raise ValueError('Margine finale non valido')
    kept = [w for w in words if w['index'] not in removed]
    if not kept:
        raise ValueError('Il montaggio deve conservare almeno una parola')
    ranges = []
    for w in kept:
        a = max(0,math.floor((w['start']-breathing)*rate))
        b = min(total,math.ceil((w['end']+max(breathing,end_margin_ms/1000))*rate))
        if ranges and (a <= ranges[-1][1] or (w['index']==ranges[-1][2]+1 and (a-ranges[-1][1])/float(rate) <= pause_threshold-2*breathing)):
            ranges[-1][1] = max(ranges[-1][1],b)
            ranges[-1][2] = w['index']
        else:
            ranges.append([a,b,w['index']])
    # Never include neighbouring discarded speech through breathing handles.
    for dropped in (w for w in words if w['index'] in removed):
        da,db=round(dropped['start']*rate),round(dropped['end']*rate)
        for r in ranges:
            if da <= r[0] < db: r[0]=db
            if da < r[1] <= db: r[1]=da
    if tight_pauses and silence_intervals:
        from .cut_silence import trim_silence_ranges
        ranges=trim_silence_ranges(ranges,silence_intervals,float(rate),pause_mode,kept,end_margin_ms=end_margin_ms)
    segments=[]; cursor=0
    for a,b,_ in ranges:
        if b<=a: continue
        segments.append({'source_in_frame':a,'source_out_frame':b,'edited_in_frame':cursor,'edited_out_frame':cursor+b-a})
        cursor+=b-a
    plan={'schema_version':'rmbl-cut-1','render_version':2,'source_signature':signature,'fps':str(rate),
          'source_duration_frames':total,'duration_frames':cursor,'duration_seconds':cursor/float(rate),
          'segments':segments,'groups':normalized,'discards':normalized_discards,'alternatives':alternatives,
          'excluded_word_indices':sorted(excluded),'automatic_removed_word_indices':automatic_removed,'protected_passages':protected,'removed_word_indices':sorted(removed),'pause_threshold':normal_pause_threshold,'breathing':normal_breathing,'tight_pauses':tight_pauses,'pause_mode':pause_mode,'pause_algorithm_version':3,'end_margin_ms':end_margin_ms,'silence_intervals':list(silence_intervals),'status':'draft'}
    for alt in alternatives:
        word=words[alt.pop('anchor_word_index')]
        anchor=word['start']*rate
        seg=next((s for s in segments if anchor<s['source_out_frame'] and word['end']*rate>s['source_in_frame']),None)
        if seg is None: seg=min(segments,key=lambda s:abs(s['source_in_frame']-anchor))
        alt['edited_in_frame']=seg['edited_in_frame']+min(seg['edited_out_frame']-seg['edited_in_frame'],max(0,round(anchor-seg['source_in_frame'])))
    if tight_pauses:
        normal=build_cut_plan(transcript,duration=duration,fps=fps,signature=signature,groups=groups,discards=discards,pause_threshold=normal_pause_threshold,breathing=normal_breathing,end_margin_ms=end_margin_ms,excluded_word_indices=excluded_word_indices)
        plan['pause_seconds_removed']=max(0,normal['duration_seconds']-plan['duration_seconds'])
    else:plan['pause_seconds_removed']=0
    plan['revision']=hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest()[:24]
    return plan


def clean_transcript(transcript,plan):
    rate=float(Fraction(plan['fps'])); removed=set(plan['removed_word_indices']); result=[]
    buckets=[[] for _ in plan['segments']];previous_segment=0
    for w in words_of(transcript):
        if w['index'] in removed:continue
        start,end=w['start']*rate,w['end']*rate
        scores=[max(0,min(end,s['source_out_frame'])-max(start,s['source_in_frame'])) for s in plan['segments']]
        best=max(range(previous_segment,len(scores)),key=lambda i:scores[i])
        if scores[best]<=0:
            best=min(range(previous_segment,len(scores)),key=lambda i:abs(plan['segments'][i]['source_in_frame']-start))
        previous_segment=best;s=plan['segments'][best]
        a=min(s['edited_out_frame']-1,s['edited_in_frame']+max(0,start-s['source_in_frame']))
        b=max(a+1,min(s['edited_out_frame'],s['edited_in_frame']+end-s['source_in_frame']))
        buckets[best].append({**w,'source_start':w['start'],'source_end':w['end'],'start':a/rate,'end':b/rate})
    for selected in buckets:
        if selected:result.append({'start':selected[0]['start'],'end':selected[-1]['end'],
            'text':' '.join(w['text'] for w in selected),'words':selected})
    return {**transcript,'segments':result,'text':' '.join(s['text'] for s in result),
            'source_duration_seconds':plan['duration_seconds'],'cut_revision':plan['revision'],
            'timing_basis':'cloud_asr_word_timestamps','timeline_fps':rate}


def review_words(transcript,plan):
    """Visible narrative includes manual exclusions, so every edit is reversible."""
    removed=set(plan.get('automatic_removed_word_indices',plan['removed_word_indices']))
    excluded=set(plan.get('excluded_word_indices',[]))
    result=[]
    for word in words_of(transcript):
        if word['index'] in removed: continue
        group=next((i for i,g in enumerate(plan['groups']) if any(a<=word['index']<=b for a,b in g['takes'])),None)
        result.append({**word,'excluded':word['index'] in excluded,'group_index':group})
    return result
