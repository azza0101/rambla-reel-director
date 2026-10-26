"""Conservative scene memberships. Source-relative half-open intervals; no editing."""
import hashlib,re
from transcript_align import normalize, get_semantic_encoder

VERSION='scene-catalog-v1'
STOP=set('ciao si sì no non il lo la gli le un una uno di da del della nel nella a e è che per con mi ti si ci vi io tu lui lei noi voi azione stop buona cut'.split())
def tokens(text):return set(w for w in normalize(text).split() if len(w)>2 and w not in STOP)
def stable(*values):return hashlib.sha256('|'.join(map(str,values)).encode()).hexdigest()[:24]

def speech_units(segment,fps):
    words=segment.get('words') or []
    if not words:return [segment]
    units=[];group=[];flags=set()
    def flush():
        if group:
            start=min(w['start_frame'] for w in group);end=max(w['end_frame'] for w in group)
            if end>start:units.append({'text':' '.join(w['text'].strip() for w in group),'start_frame':start,'end_frame':end,'words':list(group),'timing_warnings':sorted(flags)})
            group.clear()
            flags.clear()
    previous=segment['start_frame']
    for word in words:
        if not isinstance(word.get('start_frame'),int) or not isinstance(word.get('end_frame'),int) or word['start_frame']<segment['start_frame'] or word['end_frame']<word['start_frame'] or word['end_frame']>segment['end_frame']:
            raise ValueError('INVALID_WORD_TIMING')
        overlap=word['start_frame']<previous
        previous=max(previous,word['end_frame'])
        if not normalize(word.get('text','')):
            flush();continue
        if group and word['start_frame']-group[-1]['end_frame']>round(.8*fps):flush()
        flags.update(word.get('timing_warnings',[]))
        if word['start_frame']==word['end_frame']:flags.add('RESOLVE_POINT_WORD')
        if overlap:flags.add('ASR_WORD_OVERLAP')
        group.append(word)
        if re.search(r'[.!?]$',word['text'].strip()) or len(group)>=24:flush()
    flush();return units

def catalog_scenes(payload,on_progress=None,encoder=None):
    scenes=payload.get('scenes',[]);sources=payload.get('sources',[])
    lines=[(s['scene_id'],i,b) for s in scenes for i,b in enumerate(s.get('beats',[])) if b.get('kind')=='dialogue' and tokens(b.get('text',''))]
    memberships=[];unassigned=[];warnings=[];statuses={}
    semantic=payload.get('settings',{}).get('semantic',True)
    vectors=None
    if semantic and lines:
        try:
            encoder=encoder or get_semantic_encoder();vectors=encoder.encode([b['text'] for _,_,b in lines])
        except Exception:
            warnings.append({'code':'SEMANTIC_UNAVAILABLE','message':'Encoder non disponibile: solo ancore lessicali, verificare le proposte'})
    for source in sources:
        warnings.extend(source.get('transcript_warnings',[]))
        media=source['media_id'];fps=float(source['fps']);limit=source['duration_frames'];rows=[]
        for segment in source.get('segments',[]):
            start=segment.get('start_frame');end=segment.get('end_frame')
            if not isinstance(start,int) or not isinstance(end,int) or start<0 or end<=start or end>limit:
                warnings.append({'code':'INVALID_RANGE','media_id':media});continue
            # Never infer a timing for a sentence. A segment without word timing stays reviewable.
            try:rows.extend(speech_units(segment,fps))
            except ValueError:warnings.append({'code':'INVALID_WORD_TIMING','media_id':media})
        rows.sort(key=lambda r:r['start_frame'])
        clean=[]
        for row in rows:
            if clean and row['start_frame']<clean[-1]['end_frame']:
                warnings.append({'code':'OVERLAPPING_TRANSCRIPT','media_id':media});continue
            clean.append(row)
        rows=clean;statuses[media]='ok' if rows else 'missing'
        observed=encoder.encode([r['text'] for r in rows]) if vectors is not None and rows else None
        classified=[]
        for index,row in enumerate(rows):
            content=tokens(row['text']);rank=[]
            for j,(sid,order,beat) in enumerate(lines):
                target=tokens(beat['text']);overlap=len(content&target);lex=2*overlap/max(1,len(content)+len(target));sem=float(observed[index]@vectors[j]) if observed is not None else 0
                score=max(lex,.82*sem+.18*lex) if len(content)>=3 else 0
                if overlap<2 and sem<.82:score=0
                rank.append((score,sid,order,beat.get('beat_id'),overlap,sem))
            byscene={}
            for candidate in rank:
                if candidate[1] not in byscene or candidate[0]>byscene[candidate[1]][0]:byscene[candidate[1]]=candidate
            ranked=sorted(byscene.values(),reverse=True);best=ranked[0] if ranked else (0,None,0,None,0,0);margin=best[0]-(ranked[1][0] if len(ranked)>1 else 0)
            if best[0]<.57 or len(content)<3:
                classified.append(None);continue
            confident=best[0]>=.78 and margin>=.14 and len(content)>=4 and (best[4]>=3 or best[5]>=.88) and not row.get('timing_warnings')
            classified.append({'scene_id':best[1],'order':best[2],'confidence':round(best[0],4),'runner_up_margin':round(margin,4),'status':'auto_ready' if confident else 'review','evidence':[{'beat_id':best[3],'score':round(best[0],4),'lexical_anchors':best[4],'semantic_score':round(best[5],4),'text':row['text']}],'candidates':[{'scene_id':r[1],'score':round(r[0],4),'line_order':r[2],'beat_id':r[3],'lexical_anchors':r[4],'semantic_score':round(r[5],4)} for r in ranked[:3]],'timing_precision':'word_points' if row.get('timing_warnings') else 'words' if row.get('words') else 'segment','timing_warnings':row.get('timing_warnings',[])})
        # Shared lines may inherit a scene only from two independent adjacent anchors.
        # Keep the low margin visible and require review instead of fabricating certainty.
        for i in range(1,len(classified)-1):
            match=classified[i];left=classified[i-1];right=classified[i+1]
            if not match or match['status']!='review' or not left or not right:continue
            if left['status']!='auto_ready' or right['status']!='auto_ready' or left['scene_id']!=right['scene_id']:continue
            candidate=next((c for c in match['candidates'] if c['scene_id']==left['scene_id'] and c['score']>=match['confidence']-.08 and left['order']<c['line_order']<right['order']),None)
            if candidate and rows[i]['start_frame']-rows[i-1]['end_frame']<=2*fps and rows[i+1]['start_frame']-rows[i]['end_frame']<=2*fps:
                match['scene_id']=candidate['scene_id'];match['order']=candidate['line_order'];match['confidence']=candidate['score'];match['evidence'][0].update({k:candidate[k] for k in ('beat_id','score','lexical_anchors','semantic_score')});match['evidence'].append({'code':'TWO_NEIGHBOR_ANCHORS','scene_id':candidate['scene_id']})
        previous=None
        for i,(row,match) in enumerate(zip(rows,classified)):
            if not match:previous=None;continue
            # Only merge adjacent evidence; resets delimit repeated takes, unknown speech blocks merging.
            merge=previous is not None and previous['scene_id']==match['scene_id'] and match['order']>previous['_last_order'] and row['start_frame']>=previous['source_end_frame'] and row['start_frame']-previous['source_end_frame']<=round(1.2*fps)
            if merge:
                previous['source_end_frame']=row['end_frame'];previous['evidence']+=match['evidence'];previous['_last_order']=match['order'];previous['confidence']=min(previous['confidence'],match['confidence']);previous['runner_up_margin']=min(previous['runner_up_margin'],match['runner_up_margin'])
                if match['status']=='review':previous['status']='review'
            else:
                previous={**{k:v for k,v in match.items() if k!='order'},'media_id':media,'source_start_frame':row['start_frame'],'source_end_frame':row['end_frame'],'_last_order':match['order']};memberships.append(previous)
        current=[m for m in memberships if m['media_id']==media]
        for m in current:
            m.pop('_last_order',None);m['membership_id']=stable(VERSION,media,m['scene_id'],m['source_start_frame'],m['source_end_frame']);m['source_take_hint']=sum(x['source_start_frame']<=m['source_start_frame'] for x in current if x['scene_id']==m['scene_id'])
        cursor=0
        for m in current:
            if m['source_start_frame']>cursor:unassigned.append({'media_id':media,'source_start_frame':cursor,'source_end_frame':m['source_start_frame'],'reason':'NO_RELIABLE_DIALOGUE'})
            cursor=max(cursor,m['source_end_frame'])
        if cursor<limit:unassigned.append({'media_id':media,'source_start_frame':cursor,'source_end_frame':limit,'reason':'NO_RELIABLE_DIALOGUE'})
        if on_progress:on_progress({'media_id':media,'memberships':len(current)})
    return {'algorithm_version':VERSION,'memberships':memberships,'unassigned':unassigned,'source_status':statuses,'warnings':warnings,'scene_summary':[{'scene_id':s['scene_id'],'count':sum(m['scene_id']==s['scene_id'] for m in memberships)} for s in scenes]}
