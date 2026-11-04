"""Bounded local sequence search over already verified, whole-turn candidates.

This is an editorial constraint solver, not a speech/face model. It cannot
recover an absent candidate, certify visual actions or synchronize separate
performances. All intervals are half-open source frames.
"""
import math
import time


def contextual_question_match(reference,candidate,semantic,context):
 """Admit reordered short questions only with strong neighboring context.

 This supplements, rather than relaxes, voice/visual verification and monotone
 alignment. Generic answers and changes of negation are deliberately excluded.
 """
 from transcript_align import normalize
 a=normalize(reference).split();b=normalize(candidate).split()
 if not all(math.isfinite(x) for x in (semantic,context)) or semantic<.74 or context<.82:return False
 if '?' not in reference or '?' not in candidate or not 4<=len(a)<=8 or not 3<=len(b)<=10:return False
 if any(w in a for w in ('no','non'))!=any(w in b for w in ('no','non')):return False
 common=set(a)&set(b)
 return .65<=len(b)/len(a)<=1.6 and len(common)>=3 and len(common)/max(1,len(set(a)|set(b)))>=.85


def select_sequence(candidate_sets, performance_locks, fps, beam_width=64):
 started=time.perf_counter()
 if not isinstance(fps,(int,float)) or not math.isfinite(fps) or fps<=0 or type(beam_width) is not int or not 1<=beam_width<=256:
  raise ValueError('Configurazione sequenza non valida')
 seen=set()
 for choices in candidate_sets:
  if not choices or len(choices)>128:raise ValueError('Candidati assenti o oltre il limite')
  ids=choices[0].get('ids')
  if not isinstance(ids,list) or not ids or any(not isinstance(x,str) or not x for x in ids) or len(set(ids))!=len(ids) or seen.intersection(ids):raise ValueError('Eventi non validi')
  seen.update(ids)
  for c in choices:
   lo,hi=c.get('start_frame'),c.get('end_frame')
   if c.get('ids')!=ids or not isinstance(c.get('media_id'),str) or not c['media_id'] or not isinstance(c.get('field'),str) or not c['field'] or type(lo) is not int or type(hi) is not int or not 0<=lo<hi:
    raise ValueError('Candidato o corrispondenza eventi non validi')
   if not math.isfinite(c.get('similarity',1.)):raise ValueError('Similarita non valida')
 states=[((0,0,0,0.,0.,0),[],{})];expanded=0;pruned=False
 for choices in candidate_sets:
  next_states={}
  for cost,path,last_by_source in states:
   for raw in choices:
    expanded+=1;mid=raw['media_id'];lo,hi=raw['start_frame'],raw['end_frame']
    if lo<last_by_source.get(mid,0):continue
    c={**raw,'speaker_visible':bool(raw.get('speaker_visible') and raw.get('voice') is not None)}
    prev=path[-1] if path else None
    continuous=prev is not None and prev['media_id']==mid and prev['end_frame']==lo
    splice=bool(prev and prev['field']==c['field'] and not continuous)
    stale=bool(performance_locks.get(c['field']) and performance_locks[c['field']]!=mid)
    framing=c['field'].rsplit(':',1)[-1];size={'close':1.,'detail':1.,'medium':.5}.get(framing,0.)
    delta=(int(not c['speaker_visible']),int(splice),int(stale),1.-size,1.-max(0.,min(1.,c.get('similarity',1.))),int(prev is not None and not continuous))
    score=tuple(a+b for a,b in zip(cost,delta));positions={**last_by_source,mid:hi}
    key=(tuple(sorted(positions.items())),mid,hi,c['field'])
    if key not in next_states or score<next_states[key][0]:next_states[key]=(score,path+[c],positions)
  if not next_states:raise ValueError('Nessun percorso valido: eventi conservati, selezione da verificare')
  ranked=sorted(next_states.values(),key=lambda s:s[0]);pruned|=len(ranked)>beam_width;states=ranked[:beam_width]
 cost,selected,_=min(states,key=lambda s:s[0]);clock=0;splices=[];unresolved=[];decisions=[]
 for c in selected:
  if decisions:
   p=decisions[-1]
   if p['field']==c['field'] and not(p['media_id']==c['media_id'] and p['end_frame']==c['start_frame']):splices.append(clock)
  if not c['speaker_visible']:unresolved.extend(c['ids'])
  decisions.append({**c,'record_frame':clock});clock+=c['end_frame']-c['start_frame']
 return {'engine':'local-sequence-director-v1','decisions':decisions,'duration_frames':clock,'unresolved_ids':unresolved,'exposed_splice_positions':splices,'editorial_ready':False,'speaker_coverage_verified':not unresolved,'source_chronology_verified':True,'visual_actions_verified':False,'content_equivalence_verified':False,'score':list(cost),'expanded_states':expanded,'beam_width':beam_width,'search_pruned':pruned,'seconds':time.perf_counter()-started}
