"""Observed-turn planning primitives. Script text never deletes an observed event.
All frame intervals are half-open. No simultaneous-camera assumption is made.
"""
import math
from collections import Counter

def lock_performances(rows,completeness=.90):
 """Choose a whole last usable performance within 90% of best coverage per field.
 Coverage must be measured against the observed story, not literal script text.
 """
 result={}
 for field in dict.fromkeys(r['field'] for r in rows):
  eligible=[r for r in rows if r['field']==field and r.get('usable') and math.isfinite(r['coverage']) and 0<r['coverage']<=1]
  if not eligible:continue
  best=max(r['coverage'] for r in eligible)
  result[field]=max((r for r in eligible if r['coverage']>=best*completeness),key=lambda r:r['order'])['id']
 return result

def align_turns(turns,candidates,similarities,minimum=.65):
 """Weighted monotone, one-to-one turn alignment for ONE source performance.
 Voice labels must already be reconciled using acoustic evidence across sources.
 Unknown voices are not guessed. Omission is explicit, never a backwards seek.
 """
 n,m=len(turns),len(candidates)
 if len(similarities)!=n or any(len(r)!=m for r in similarities):raise ValueError('Matrice di allineamento non valida')
 if any(c['start_frame']>=c['end_frame'] or i and c['start_frame']<candidates[i-1]['end_frame'] for i,c in enumerate(candidates)):raise ValueError('Turni candidati sovrapposti o fuori ordine')
 scores=[[0.]*(m+1) for _ in range(n+1)];steps={}
 for i in range(1,n+1):
  for j in range(1,m+1):
   opts=[(scores[i-1][j],0),(scores[i][j-1],1)]
   sim=float(similarities[i-1][j-1]);voice=turns[i-1].get('voice')
   if math.isfinite(sim) and sim>=minimum and voice is not None and voice==candidates[j-1].get('voice'):opts.append((scores[i-1][j-1]+sim,2))
   scores[i][j],steps[i,j]=max(opts,key=lambda p:(p[0],p[1]==2))
 result=[None]*n;i,j=n,m
 while i and j:
  step=steps[i,j]
  if step==2:result[i-1]=j-1;i-=1;j-=1
  elif step==0:i-=1
  else:j-=1
 return result

def audit_edit(decisions,covers,event_ids,fps):
 """Audit interval integrity separately from editorial/visual correctness.
 An interval pass is never evidence that acting, objects or eye-lines are right.
 """
 from performance_spine import jump_cover
 expected=Counter(event_ids);actual=Counter(u for d in decisions for u in d.get('ids',[]));joins=[];invalid=[];clock=0
 for i,d in enumerate(decisions):
  if type(d.get('start_frame')) is not int or type(d.get('end_frame')) is not int or d['start_frame']<0 or d['start_frame']>=d['end_frame'] or d.get('record_frame')!=clock:invalid.append(i)
  clock+=d['end_frame']-d['start_frame']
  if i:
   a=decisions[i-1]
   if a['field']==d['field'] and not(a['media_id']==d['media_id'] and a['end_frame']==d['start_frame']):joins.append(d['record_frame'])
 uncovered=[join for join in joins if not any(jump_cover(join,clock,c,fps) and c.get('audio')=='base_unchanged' for c in covers)]
 short_covers=[i for i,c in enumerate(covers) if c.get('end_frame',0)-c.get('start_frame',0)<math.ceil(1.5*fps)]
 # Turn boundaries are metadata. Contiguous source video is a single physical
 # hold even if the voice changes or a short interjection starts a new turn.
 holds=[]
 for i,d in enumerate(decisions):
  previous=decisions[i-1] if i else None
  continuous=previous and previous['media_id']==d['media_id'] and previous['field']==d['field'] and previous['end_frame']==d['start_frame'] and previous['record_frame']+previous['end_frame']-previous['start_frame']==d['record_frame']
  length=d['end_frame']-d['start_frame']
  if continuous:holds[-1][1]+=length
  else:holds.append([i,length])
 short_shots=[i for i,length in holds if length<math.ceil(1.5*fps)]
 overlaps=[(i,j) for i,a in enumerate(decisions) for j,b in enumerate(decisions[i+1:],i+1) if a['media_id']==b['media_id'] and max(a['start_frame'],b['start_frame'])<min(a['end_frame'],b['end_frame'])]
 missing=sorted((expected-actual).elements());duplicate=sorted(k for k,n in actual.items() if n>expected[k]);unexpected=sorted(set(actual)-set(expected))
 return {'ready':not any([invalid,uncovered,short_covers,short_shots,overlaps,missing,duplicate,unexpected]),'missing_events':missing,'duplicate_events':duplicate,'unexpected_events':unexpected,'exposed_same_field_joins':uncovered,'invalid_intervals':invalid,'short_reactions':short_covers,'short_shots':short_shots,'reused_source_intervals':overlaps,'duration_frames':clock,'visual_actions_verified':False,'content_equivalence_verified':False}

def listener_evidence(visible_voice,audio_voices):
 """A known face of B under consistently identified voice A is listening evidence.
 Callers must obtain visible_voice from positive face enrollment, not ASD absence.
 """
 known=[v for v in audio_voices if v is not None];counts=Counter(known)
 voice,count=counts.most_common(1)[0] if counts else (None,0)
 verified=visible_voice is not None and voice is not None and voice!=visible_voice and len(known)/max(1,len(audio_voices))>=.6 and count/len(known)>=.85
 return {'verified_listener':verified,'different_person':verified,'visible_voice':visible_voice,'speaking_voice':voice,'audio':'base_unchanged','basis':'positive_face_identity_and_independent_voice'}

def align_windows(turns,candidates,similarities,minimum=.65):
 """Monotone weighted interval matching; alternative windows may overlap.
 Selected windows cannot overlap, even when identical text occurs several times.
 """
 from bisect import bisect_right
 if len(similarities)!=len(turns) or any(len(r)!=len(candidates) for r in similarities):raise ValueError('Matrice non valida')
 if any(type(c['start_frame']) is not int or type(c['end_frame']) is not int or not 0<=c['start_frame']<c['end_frame'] for c in candidates):raise ValueError('Intervallo non valido')
 states={-1:(0.,[])}
 for i,t in enumerate(turns):
  keys=sorted(states);prefix=[];best=(-1e30,[])
  for k in keys:
   if states[k][0]>best[0]:best=states[k]
   prefix.append(best)
  new={end:(score,path+[None]) for end,(score,path) in states.items()}
  for j,c in enumerate(candidates):
   score=float(similarities[i][j]);voice=t.get('voice')
   if voice is None or voice!=c.get('voice') or not math.isfinite(score) or score<minimum:continue
   at=bisect_right(keys,c['start_frame'])-1
   if at<0:continue
   previous,path=prefix[at];total=previous+score;end=c['end_frame']
   if end not in new or total>new[end][0]:new[end]=(total,path+[j])
  states=new
 return max(states.values(),key=lambda p:p[0])[1]

def verified_alignment(turns,candidates,similarities,verify,minimum=.65,max_rounds=3):
 """Lazy constrained search: failed visual evidence triggers another alignment.
 No candidate is returned merely because the retry budget was exhausted.
 """
 scores=[list(row) for row in similarities];checked={}
 for _ in range(max_rounds):
  mapping=align_windows(turns,candidates,scores,minimum);rejected=False
  for i,j in enumerate(mapping):
   if j is None:continue
   if j not in checked:checked[j]=bool(verify(j))
   if not checked[j]:
    # Verification is source-window evidence, independent of the query turn.
    # Do not spend another search round proposing the same rejected window
    # for a different occurrence of a repeated question or gag answer.
    for row in scores:row[j]=-1.
    rejected=True
  if not rejected:return mapping
 mapping=align_windows(turns,candidates,scores,minimum)
 return [j if j is not None and checked.get(j) else None for j in mapping]


def verified_alignment_options(turns,candidates,similarities,verifiers,minimum=.65,max_rounds=3):
 """Keep positively verified paths until the global sequence search.

 A source file can contain multiple performances. A new visible candidate in
 one performance must not erase a previously verified option in another.
 These are alternatives, not an instruction to concatenate the local paths.
 """
 options=[[] for _ in turns]
 for verify in verifiers:
  for i,j in enumerate(verified_alignment(turns,candidates,similarities,verify,minimum,max_rounds)):
   if j is not None and j not in options[i]:options[i].append(j)
 return options
