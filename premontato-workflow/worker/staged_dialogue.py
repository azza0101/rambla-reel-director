"""Grounded dialogue classification and deterministic local editing; no scene-specific ranges."""
import re,copy,hashlib
from difflib import SequenceMatcher
from transcript_align import normalize,_STOPWORDS,_stem_token,safe_dialogue_handles
ENGINE='groq_staged_v1'
def clean_text(s):
 for _ in range(3):
  if not any(x in s for x in ['Ã','Â','â€']):break
  try:s=s.encode('cp1252').decode('utf8')
  except UnicodeError:
   try:s=s.encode('latin1').decode('utf8')
   except UnicodeError:break
 return s
def core(s):return [_stem_token(w) for w in normalize(clean_text(s)).split() if w not in _STOPWORDS]
def prepare_dialogue(payload):
 beats=[{**b,'id':b['beat_id'],'number':i+1,'text':clean_text(b.get('text',''))} for i,b in enumerate(payload['beats'])]
 cast={'P0':'UNKNOWN'}
 for b in beats:
  if b.get('character') and b['character'] not in cast.values():cast['P'+str(len(cast))]=b['character']
 clips=[]
 for source in sorted(payload['sources'],key=lambda s:(s['media_id'],s.get('take_id',''))):
  us=[];lo=source.get('start_frame',0);hi=source.get('end_frame',source['duration_frames'])
  for segment in source.get('segments',[]):
   group=[]
   def flush():
    if group:us.append({'id':'S'+str(len(us)),'start':group[0]['start_frame'],'end':group[-1]['end_frame'],'text':' '.join(clean_text(w['text'].strip()) for w in group),'word_indices':[w['_word_index'] for w in group]})
   for wi,word in enumerate(segment.get('words',[])):
    if word['end_frame']<=word['start_frame'] or word['start_frame']<lo or word['end_frame']>hi or not re.search(r'\w',word.get('text','')):continue
    if group and (word['start_frame']-group[-1]['end_frame']>float(payload['fps']) or word['end_frame']-group[0]['start_frame']>8*float(payload['fps'])):flush();group=[]
    group.append({**word,'_word_index':str(source['segments'].index(segment))+':'+str(wi)})
    if re.search(r'[.!?]$',word['text'].strip()):flush();group=[]
   flush()
  if not us:raise ValueError('Trascrizione temporizzata mancante per '+source.get('name','clip')+': trascrivi nuovamente in Resolve')
  clips.append({'key':source.get('take_id',source['media_id']),'media_id':source['media_id'],'units':us})
 return {'beats':beats,'cast':cast,'clips':clips,'fps':float(payload['fps'])}
def validate_labels(prepared,values):
 if set(values)!={c['key'] for c in prepared['clips']}:raise ValueError('Classificazioni delle riprese incomplete')
 for c in prepared['clips']:
  labels=values[c['key']]
  if not isinstance(labels,dict) or set(labels)!={u['id'] for u in c['units']}:raise ValueError('Identificatori di segmento mancanti o inventati')
  for v in labels.values():
   if v=='X':continue
   match=re.fullmatch(r'(\d+)/(P\d+)',v)
   if not match or not 1<=int(match[1])<=len(prepared['beats']) or match[2] not in prepared['cast']:raise ValueError('Battuta o personaggio non valido nella classificazione')
 return values
def reconcile_roles(prepared,values):
 """A screenplay dialogue beat is authoritative for its speaking role."""
 result=copy.deepcopy(values);role_ids={name:key for key,name in prepared['cast'].items()}
 for labels in result.values():
  for uid,label in labels.items():
   if label=='X':continue
   number,_=label.split('/');beat=prepared['beats'][int(number)-1]
   if beat['kind']=='parenthetical' and re.fullmatch(r"\s*\(?CONTINUED\)?\s*",beat.get('text',''),re.I):
    preceding=[(i,b) for i,b in enumerate(prepared['beats'][:int(number)-1]) if b.get('scene_id')==beat.get('scene_id') and b.get('kind')=='dialogue' and b.get('character')==beat.get('character')]
    if preceding:
     i,beat=preceding[-1];number=str(i+1)
   if beat['kind']=='dialogue' and beat.get('character') in role_ids:labels[uid]=number+'/'+role_ids[beat['character']]
 return result
def clean_restarts(units,values):
 labels=dict(values);changes=[]
 for u in units:
  label=labels[u['id']]
  if label=='X':continue
  a=core(u['text'])
  for v in units:
   if v['start']<=u['end'] or labels[v['id']]!=label or v['text'].strip().endswith(('...','…')):continue
   b=core(v['text']);match=SequenceMatcher(None,a,b,autojunk=False).find_longest_match()
   repeated=(len(a)>=2 or len(a)==1 and len(a[0])>=5 and len(normalize(u['text']).split())>=2) and ((len(b)>=len(a) and b[:2]==a[:2] and match.size>=min(3,len(a))) or (u['text'].strip().endswith(('...','…')) and len(set(a)&set(b))>=2))
   if repeated and (u['text'].strip().endswith(('...','…')) or match.size==len(a)):
    labels[u['id']]='X';changes.append({'unit':u['id'],'superseded_by':v['id']});break
 # A trailing aborted repeat must not replace an earlier complete delivery.
 for u in units:
  label=labels[u['id']];a=core(u['text'])
  if label=='X' or len(a)<2 or not u['text'].strip().endswith(('...','…')):continue
  prior=[v for v in units if v['end']<u['start'] and labels[v['id']]==label and not v['text'].strip().endswith(('...','…')) and core(v['text'])[:len(a)]==a]
  if prior:
   good=max(prior,key=lambda v:v['end']);labels[u['id']]='X';changes.append({'unit':u['id'],'superseded_by':good['id']})
 return labels,changes
def latest_complete_run(rows,all_rows,labels,beat,fps,encode=None):
 if not rows:return []
 if len(rows)==1:return rows
 groups=[];group=[];target=set(core(beat['text']))
 # Lexically different restarts can express the same line. Reuse the local
 # encoder to separate repeated starts and collapse equivalent performances.
 row_sims=None
 if encode is not None:
  vectors=encode([u['text'] for u in rows]);row_sims=vectors@vectors.T
 indices={u['id']:i for i,u in enumerate(rows)}
 for u in rows:
  previous=group[-1] if group else None
  repeated=False
  if previous and row_sims is not None:
   head=group[0]
   ratio=len(normalize(u['text']).split())/max(1,len(normalize(head['text']).split()))
   repeated=(not head['text'].strip().endswith(('...','…')) and .5<=ratio<=2 and float(row_sims[indices[head['id']],indices[u['id']]])>=.82)
  if previous and (repeated or u['start']-previous['end']>6*fps or any(previous['end']<=v['start']<u['start'] and labels.get(v['id'])!=labels.get(u['id']) for v in all_rows)):
   groups.append(group);group=[]
  group.append(u)
 if group:groups.append(group)
 def rank(g):
  observed=set(core(' '.join(u['text'] for u in g)))
  return len(target&observed)/max(1,len(target)),len(observed)
 complete=[g for g in groups if not g[-1]['text'].strip().endswith(('...','…'))]
 if encode is not None and len(complete)>1:
  texts=[' '.join(u['text'] for u in g) for g in complete]
  vectors=encode(texts+[beat['text']]);sims=vectors[:-1]@vectors[:-1].T;relevance=vectors[:-1]@vectors[-1]
  # Only equivalent deliveries compete. Complementary continuations/asides
  # remain distinct; an interrupted final attempt never replaces a good one.
  components=[]
  for i,g in enumerate(complete):
   matches=[c for c in components if any(float(sims[i,j])>=.78 for j in c)]
   if matches:
    merged=[i]+[j for c in matches for j in c];components=[c for c in components if c not in matches]+[merged]
   else:components.append([i])
  chosen=[]
  for component in components:
   length=max(rank(complete[i])[1] for i in component)
   complete_pool=[i for i in component if rank(complete[i])[1]>=length*.6]
   best=max(float(relevance[i]) for i in complete_pool)
   eligible=[i for i in complete_pool if float(relevance[i])>=best-.10]
   at=max(eligible,key=lambda i:complete[i][-1]['end']);chosen.extend(complete[at])
  return sorted(chosen,key=lambda u:u['start'])
 def distinct(a,b):
  x=set(core(' '.join(u['text'] for u in a)));y=set(core(' '.join(u['text'] for u in b)))
  return len(x&y)/max(1,len(x|y))<.65
 if len(complete)>1 and all(distinct(a,b) for i,a in enumerate(complete) for b in complete[i+1:]):return [u for g in complete for u in g]
 best=max((rank(g) for g in groups))
 if rank(rows)[0]>best[0]+.15:return rows
 eligible=[g for g in groups if not g[-1]['text'].strip().endswith(('...','…')) and rank(g)[0]>=best[0]-.08 and rank(g)[1]>=best[1]*.6]
 return max(eligible,key=lambda g:g[-1]['end']) if eligible else max(groups,key=rank)

def select_dialogue_reference(choices,beat,coverage,sources,encode,master=None):
 """Choose what was said before choosing which camera should show it."""
 keys=list(choices);texts=[' '.join(u['text'] for u in choices[cid]) for cid in keys]
 vectors=encode(texts+[beat['text']]);similarities=vectors[:-1]@vectors[-1];target=set(core(beat['text']));scores={}
 for i,cid in enumerate(keys):
  observed=set(core(texts[i]));overlap=len(target&observed)
  precision=overlap/max(1,len(observed));recall=overlap/max(1,len(target))
  f1=2*precision*recall/max(precision+recall,1e-9)
  scores[cid]=.65*float(similarities[i])+.35*f1
 best=max(scores.values());eligible=[cid for cid in keys if scores[cid]>=best-.025]
 if master in eligible:return master
 return max(eligible,key=lambda cid:(sources[cid].get('take_index',0),sources[cid].get('name',''),max(u['end'] for u in choices[cid]),coverage.get((cid,beat.get('character')))=='visible',cid))

def camera_style_score(size,status,semantic,start,fps,opening=False,release=False):
 # Source position is a bounded tie-break, never a reason to choose a worse field.
 if status=='visible':base={'close':12,'medium':9,'wide':5,'detail':3,'unknown':3}.get(size,3)
 elif status=='absent':base=-8
 else:base={'wide':4,'medium':2,'close':2,'detail':0,'unknown':1}.get(size,1)
 if size=='wide' and opening:base+=14
 elif size=='wide' and release:base+=10
 return base+max(0,min(1,float(semantic)))+min(.12,max(0,start)/max(1,fps*360000))

def verify_camera_candidates(rows,sources,analyze,fps,opening=False,release=False,limit=3):
 # The camera/role profile is a shortlist hint, not proof for a particular line.
 ordered=sorted(rows,key=lambda r:((0 if r['shot_size']=='wide' else 1) if opening or release else {'close':0,'medium':1,'wide':2,'unknown':3,'detail':4}.get(r['shot_size'],3),-r['score']))
 checked={};seen=set()
 for row in ordered:
  cid=row['clip_id']
  if cid in seen:continue
  seen.add(cid)
  try:evidence=analyze(sources[cid],row['matched_start_frame'],row['matched_end_frame'])
  except Exception as error:evidence={'status':'unknown','reason':str(error)}
  checked[id(row)]=evidence
  if evidence.get('status')=='visible' or len(seen)>=limit:break
 for row in rows:
  evidence=checked.get(id(row));row['speaker_coverage']=evidence.get('status','unknown') if evidence else 'unknown'
  row['speaker_coverage_source']='audio_visual_interval' if evidence else 'unverified_candidate'
  if evidence:row['active_speaker']=evidence
  row['score']=camera_style_score(row['shot_size'],row['speaker_coverage'],row['semantic'],row['matched_start_frame'],fps,opening,release)
 return rows

def _size(source,shots,at=None):
 rows=[s for s in shots if s['media_id']==source['media_id'] and s.get('confidence',0)>=.5 and s.get('shot_size') in {'wide','medium','close','detail'}]
 if at is not None:
  row=next((s for s in rows if s['start_frame']<=at<s['end_frame']),None)
  if row:return row['shot_size']
 if not rows:return 'unknown'
 totals={size:sum(s['end_frame']-s['start_frame'] for s in rows if s['shot_size']==size) for size in ['wide','medium','close','detail']}
 return max(totals,key=totals.get)
def recover_cross_camera(units,labels,similarities,fps,threshold=.68,excluded=()):
 """Restore unique complete speech only with cross-camera consensus and two nearby anchors."""
 result=dict(labels);recovered=[]
 for i,u in enumerate(units):
  if u['id'] in excluded or labels[u['id']]!='X' or len(normalize(u['text']).split())<4 or u['text'].strip().endswith(('...','…')):continue
  rows=[v for v in units if v['clip']==u['clip'] and labels[v['id']]!='X']
  before=[v for v in rows if 0<=u['start']-v['end']<=2*fps]
  after=[v for v in rows if 0<=v['start']-u['end']<=2*fps]
  if not before or not after:continue
  allowed={labels[max(before,key=lambda v:v['end'])['id']],labels[min(after,key=lambda v:v['start'])['id']]}
  evidence={}
  for j,v in enumerate(units):
   label=labels[v['id']]
   if v['clip']==u['clip'] or label=='X':continue
   evidence[label]=max(evidence.get(label,-1),float(similarities[i,j]))
  ranked=sorted(evidence.items(),key=lambda x:x[1],reverse=True)
  if not ranked:continue
  label,score=ranked[0];runner=ranked[1][1] if len(ranked)>1 else -1
  if label in allowed and score>=threshold and score-runner>=.08:
   result[u['id']]=label;recovered.append({'unit':u['id'],'label':label,'evidence':'cross_camera_semantic_consensus','score':score})
 return result,recovered
def recover_single_camera_asides(units,labels,scores,beats,fps,verify,excluded=()):
 """Recover only complete local asides between dialogue anchors, never crew or restart text."""
 result=dict(labels);changes=[]
 cues=re.compile(r"\b(stop|ciak|azione|rifacciamo|rifai|riparti|ripartiamo|ricominciamo|microfono|telecamera|regia|battuta|scusami|scusate|aspetta|riprese)\b",re.I)
 dialogue=[i for i,b in enumerate(beats) if b.get('kind')=='dialogue']
 for i,u in enumerate(units):
  if u['id'] in excluded or labels[u['id']]!='X' or len(normalize(u['text']).split())<4 or u['text'].strip().endswith(('...','…')) or cues.search(normalize(u['text'])) or u['end']-u['start']>8*fps:continue
  before=[v for v in units if labels[v['id']]!='X' and 0<=u['start']-v['end']<=2.5*fps]
  after=[v for v in units if labels[v['id']]!='X' and 0<=v['start']-u['end']<=2.5*fps]
  if not before or not after:continue
  anchors=[max(before,key=lambda v:v['end']),min(after,key=lambda v:v['start'])]
  ranking=sorted(((float(scores[i][j]),j) for j in dialogue),reverse=True)
  if not ranking:continue
  score,j=ranking[0];runner=ranking[1][0] if len(ranking)>1 else -1
  label=next((labels[v['id']] for v in anchors if int(labels[v['id']].split('/')[0])==j+1),None)
  if label is None or score<.58 or score-runner<.06:continue
  try:visible=verify(u).get('status')=='visible'
  except Exception:visible=False
  if not visible:continue
  result[u['id']]=label;changes.append({'unit':u['id'],'label':label,'evidence':'single_camera_semantic_aside','score':score})
 return result,changes

from runtime_trace import trace_pipeline

@trace_pipeline
def build_staged(payload,report=lambda e:None):
 from transcript_align import get_semantic_encoder
 from automatic_editor import narrative_roles
 from active_speaker import analyze_candidate
 from listening_reaction import listening_overlay
 prepared=payload.get('prepared') or prepare_dialogue(payload);values=reconcile_roles(prepared,validate_labels(prepared,payload['classifications']))
 beats=[{**b,'text':clean_text(b['text'])} for b in payload['beats']];fps=float(payload['fps']);beatmap={'B'+str(i+1):b['beat_id'] for i,b in enumerate(beats)}
 sources={};units=[];labels={};cleanup=[]
 ordered=sorted(payload['sources'],key=lambda s:(s['media_id'],s.get('take_id','')))
 for i,source in enumerate(ordered):
  cid='C'+str(i+1);sources[cid]=dict(source);c=next(c for c in prepared['clips'] if c['key']==source.get('take_id',source['media_id']))
  cleaned,changes=clean_restarts(c['units'],values[c['key']]);cleanup.extend({'clip':cid,**x} for x in changes)
  for u in c['units']:
   uid=cid+u['id'];labels[uid]=cleaned[u['id']];units.append({**u,'id':uid,'clip':cid,'ASD':'unknown'})
 from editorial_director import valid_editorial,resolve_event,offcamera_candidates
 editorial_events=valid_editorial({**payload,'prepared':prepared},beats)
 directed=(payload.get('editorial') or {}).get('summary',{}).get('status')=='ready'
 names=prepared['cast']
 def info(u):
  n,role=labels[u['id']].split('/');return 'B'+n,names[role]
 encoder=get_semantic_encoder();unit_vectors=encoder.encode([u['text'] for u in units]);labels,recovered=recover_cross_camera(units,labels,unit_vectors@unit_vectors.T,fps,excluded={x['clip']+x['unit'] for x in cleanup})
 if len(sources)==1:
  beat_vectors=encoder.encode([b['text'] for b in beats])
  labels,asides=recover_single_camera_asides(units,labels,unit_vectors@beat_vectors.T,beats,fps,lambda u:analyze_candidate(sources[u['clip']],u['start'],u['end']),excluded={x['clip']+x['unit'] for x in cleanup})
  recovered.extend(asides)
 kept=[u for u in units if labels[u['id']]!='X']
 def block(us):return {'clip_id':us[0]['clip'],'units':[u['id'] for u in us],'start':us[0]['start'],'end':us[-1]['end'],'text':' '.join(clean_text(u['text']) for u in us),'beat':info(us[0])[0],'role':info(us[0])[1]}
 shots=payload.get('shots',[]);data={'clips':[{'clip_id':cid,'shot_size':_size(s,shots)} for cid,s in sources.items()],'style':payload.get('directions',{})}
 masters=[c['clip_id'] for c in data['clips'] if c['shot_size']=='wide']
 master=max(masters,key=lambda cid:sum(u['end']-u['start'] for u in kept if u['clip']==cid)) if masters else None
 if not kept:raise ValueError('Nessun dialogo valido trovato nelle riprese per le scene selezionate')
 # At most three balanced ASD samples per camera/role. Estimates never identify real people.
 tasks=[]
 for cid in sources:
  if cid in masters:
   for u in kept:
    if u['clip']==cid:u['ASD']='visible'
   continue
  for role in names.values():
   group=[u for u in kept if u['clip']==cid and info(u)[1]==role and u['end']-u['start']>=.3*fps]
   indices=list(dict.fromkeys([len(group)//2,0,len(group)-1])) if group else []
   tasks.extend(group[j] for j in indices)
 checked_roles=set()
 for i,u in enumerate(tasks):
  role_key=(u['clip'],info(u)[1])
  if role_key in checked_roles:continue
  report({'phase':'speaker','current':i,'total':len(tasks)})
  try:u['ASD']=analyze_candidate(sources[u['clip']],u['start'],u['end']).get('status','unknown')
  except Exception:u['ASD']='unknown'
  if u['ASD'] in {'visible','absent'}:checked_roles.add(role_key)
 report({'phase':'speaker','current':len(tasks),'total':len(tasks)})

 coverage={}
 for cid in sources:
  for role in names.values():
   rows=[u for u in kept if u['clip']==cid and info(u)[1]==role and u['ASD'] in {'visible','absent'}];yes=sum(u['end']-u['start'] for u in rows if u['ASD']=='visible');no=sum(u['end']-u['start'] for u in rows if u['ASD']=='absent')
   coverage[(cid,role)]='visible' if yes and yes/(yes+no)>=.65 else 'absent' if no and yes/(yes+no)<=.35 else 'unknown'
 canonical=[]
 for bi,beat in enumerate(beats):
  if beat['kind']!='dialogue':continue
  bid='B'+str(bi+1);choices={}
  for u in kept:
   if info(u)[0]==bid:choices.setdefault(u['clip'],[]).append(u)
  if not choices:continue
  choices={cid:latest_complete_run(rows,[u for u in units if u['clip']==cid],labels,beat,fps,encoder.encode) for cid,rows in choices.items()}
  reference=select_dialogue_reference(choices,beat,coverage,sources,encoder.encode,master)
  group=[]
  for u in choices[reference]:
   if group:
    prev=group[-1]
    if u['start']-prev['end']>1.5*fps or prev['end']-group[0]['start']>=3*fps:
     canonical.append(block(group));group=[]
   group.append(u)
  if group:canonical.append(block(group))
 if len(sources)==1:
  selected_ids={uid for c in canonical for uid in c['units']};canonical=[];group=[]
  for u in kept:
   if u['id'] not in selected_ids:continue
   if group and (info(group[-1])[0]!=info(u)[0] or u['start']-group[-1]['end']>1.5*fps or group[-1]['end']-group[0]['start']>=3*fps):
    canonical.append(block(group));group=[]
   group.append(u)
  if group:canonical.append(block(group))
 if len(sources)>1:canonical=[c for c in canonical if not(c['end']-c['start']<.8*fps and any(d['beat']==c['beat'] and d['start']>c['end'] and d['end']-d['start']>=fps for d in canonical))]
 for i,c in enumerate(canonical):c['moment_id']='moment-%02d'%i
 windows=[]
 for cid in sources:
  rows=[u for u in units if u['clip']==cid]
  for i,u in enumerate(rows):
   if labels[u['id']]=='X':continue
   group=[]
   for v in rows[i:i+8]:
    if labels[v['id']]=='X' or info(v)[0]!=info(u)[0] or (group and v['start']-group[-1]['end']>2.5*fps):break
    if info(v)[1]!=info(u)[1] and len(normalize(beats[int(info(u)[0][1:])-1]['text']).split())>5:break
    group.append(v);windows.append(block(group))
 report({'phase':'align','current':0,'total':1});vectors=encoder.encode([c['text'] for c in canonical]+[w['text'] for w in windows]);similarities=vectors[:len(canonical)]@vectors[len(canonical):].T
 effective_style=copy.deepcopy(data['style'])
 for event in editorial_events:
  if event.get('kind')=='release' and not effective_style.get('markers',{}).get(event['beat_id']):effective_style.setdefault('markers',{})[event['beat_id']]='resolution'
 roles=narrative_roles(beats,effective_style);candidates=[];listening_candidates=[];grounded_canonical=[];grounded_indices=[];discarded_moments=[];original_canonical_count=len(canonical)
 for ci,c in enumerate(canonical):
  rows=[];listener_rows=[];actual=beatmap[c['beat']];narrative=roles.get(actual,{}).get('role','free')
  for wi,w in enumerate(windows):
   if w['beat']!=c['beat'] or w['role']!=c['role']:continue
   cosine=float(similarities[ci,wi]);ratio=len(normalize(w['text']).split())/max(1,len(normalize(c['text']).split()))
   if w['clip_id']==c['clip_id'] and w['units']!=c['units']:continue
   shared=len(set(core(w['text']))&set(core(c['text'])))
   if w['clip_id']!=c['clip_id'] and (cosine>=.48 or shared>=3):
    listener_rows.append({**w,'media_id':sources[w['clip_id']]['media_id'],'take_id':sources[w['clip_id']]['take_id'],'start_frame':w['start'],'end_frame':w['end'],'matched_end_frame':w['end'],'shot_size':_size(sources[w['clip_id']],shots,(w['start']+w['end'])//2),'semantic':cosine})
   if (cosine<.48 and shared<3) or not .30<=ratio<=2.0 or (ratio<.45 and cosine<.60):continue
   if w['text'].strip().endswith(('...','…')) and not beats[int(c['beat'][1:])-1]['text'].strip().endswith(('...','…')):continue
   size=_size(sources[w['clip_id']],shots,(w['start']+w['end'])//2);status=coverage[(w['clip_id'],c['role'])];start,end=safe_dialogue_handles({'start_frame':w['start'],'end_frame':w['end']},sources[w['clip_id']],fps)
   row={**w,'start_frame':start,'end_frame':end,'matched_start_frame':w['start'],'matched_end_frame':w['end'],'shot_size':size,'speaker_coverage':status,'semantic':cosine,'media_id':sources[w['clip_id']]['media_id'],'take_id':sources[w['clip_id']]['take_id'],'dialogue_character':c['role'],'narrative_role':narrative,'beat_id':actual,'moment_id':c['moment_id'],'decision_id':c['moment_id'],'matched_text':w['text'],'warnings':[],'confidence':min(1,max(0,cosine)),'coverage':1,'shot_confidence':.75,'speaker_coverage_source':'audio_visual','match_method':'groq_context','pacing':{'duration_frames':end-start}}
   score=camera_style_score(size,status,cosine,w['start'],fps,opening=ci==0 and bool(masters),release=narrative=='resolution')-.2*abs(__import__('math').log(ratio))
   if ci==0 and masters:
    if size!='wide':continue
   row['score']=score;rows.append(row)
  report({'phase':'speaker-final','current':ci,'total':len(canonical)})
  if rows:rows=verify_camera_candidates(rows,sources,analyze_candidate,fps,opening=ci==0 and bool(masters),release=narrative=='resolution')
  if not rows:
   discarded_moments.append({'beat_id':actual,'text':c['text'],'reason':'NO_COMPLETE_GROUNDED_CANDIDATE'});continue
  grounded_canonical.append(c);grounded_indices.append(ci);candidates.append(rows);listening_candidates.append(listener_rows)
 canonical=grounded_canonical
 if not candidates:raise RuntimeError('Nessuna battuta completa verificabile nella scena')

 words={cid:[w for seg in s['segments'] for w in seg.get('words',[]) if w['end_frame']>w['start_frame']] for cid,s in sources.items()}
 positions={b['beat_id']:i for i,b in enumerate(beats)}
 def continuous_action(a,b):
  return len(sources)==1 and 0<b['matched_start_frame']-a['matched_end_frame']<=30*fps and any(beat['kind']=='action' and not re.fullmatch(r'\s*(pausa|silenzio|attesa)\s*',beat['text'],re.I) for beat in beats[positions[a['beat_id']]+1:positions[b['beat_id']]])
 def can_join(a,b):
  if b['matched_start_frame']<a['matched_end_frame']:return False
  between=[w for w in words[b['clip_id']] if w['start_frame']>=a['matched_end_frame'] and w['end_frame']<=b['matched_start_frame']]
  return not between or continuous_action(a,b)
 minimum_shot=round(float(payload.get('settings',{}).get('minimum_shot_seconds',1.2))*fps)
 def short_reply(row):return (not masters or len(sources)==1) and len(normalize(row['text']).split())<=6 and row['matched_end_frame']-row['matched_start_frame']<minimum_shot
 states=[(0,[],{},0)]
 for ci,rows in enumerate(candidates):
  new=[]
  for score,path,last,run in states:
   for row in rows:
    cid=row['clip_id'];prior=path[-1] if path else None
    if masters and row['matched_start_frame']<last.get(cid,-1):continue
    if not masters and any(prior_row['clip_id']==cid and max(prior_row['matched_start_frame'],row['matched_start_frame'])<min(prior_row['matched_end_frame'],row['matched_end_frame']) for prior_row in path):continue
    same=bool(prior and prior['clip_id']==cid)
    if same and not can_join(prior,row):continue
    if prior and not same and run<minimum_shot and not short_reply(prior):continue
    length=run+row['end_frame']-prior['end_frame'] if same else row['end_frame']-row['start_frame']
    penalty=max(0,length-15*fps)/fps*.1 if same and row['narrative_role']=='free' else 0
    context_bonus=0
    if row['shot_size']=='wide' and prior and prior['beat_id']!=row['beat_id'] and row['narrative_role']!='tension':
     since_wide=0
     for previous in reversed(path):
      if previous['shot_size']=='wide':break
      since_wide+=previous['end_frame']-previous['start_frame']
     if since_wide>=25*fps:context_bonus=10
    if prior and prior['shot_size']=='wide' and row['shot_size']=='wide' and ci>0 and row['narrative_role']!='resolution':context_bonus-=6
    new.append((score+row['score']+context_bonus-penalty,path+[copy.deepcopy(row)],{**last,cid:row['matched_end_frame']},length))
  if not new:raise RuntimeError('No continuous montage path at '+canonical[ci]['moment_id'])
  states=[]
  for camera in sources:states+=sorted([s for s in new if s[1][-1]['clip_id']==camera],key=lambda s:s[0],reverse=True)[:100]
 _,decisions,_,_=max((s for s in states if s[3]>=minimum_shot or short_reply(s[1][-1])),key=lambda s:s[0])
 short_exceptions=0;run_start=0
 for i,d in enumerate(decisions):
  if i==len(decisions)-1 or decisions[i+1]['clip_id']!=d['clip_id']:
   if d['end_frame']-decisions[run_start]['start_frame']<minimum_shot:
    d['warnings'].append('Risposta breve conservata: inquadratura sotto la durata minima obiettivo.');short_exceptions+=1
   run_start=i+1
 for left,right in zip(decisions,decisions[1:]):
  if left['clip_id']==right['clip_id']:
   if continuous_action(left,right):left['warnings'].append('Raccordo di azione continuo: comprende anche parlato non classificato fra le battute; verifica il piano sequenza.')
   left['end_frame']=right['start_frame'];left['pacing']['duration_frames']=left['end_frame']-left['start_frame']
 for i,d in enumerate(decisions):
  d['alternatives']=[copy.deepcopy(r) for r in candidates[i] if r['clip_id']!=d['clip_id'] or r['units']!=d['units']];d['source_ranges']=[{'start_frame':d['start_frame'],'end_frame':d['end_frame']}]
 positions={b['beat_id']:i for i,b in enumerate(beats)};actions=[]
 for i,d in enumerate(decisions):
  right=decisions[i+1] if i+1<len(decisions) else None
  movement=[b for b in beats[positions[d['beat_id']]+1:positions[right['beat_id']] if right else len(beats)] if b['kind']=='action' and not re.fullmatch(r'\s*(pausa|silenzio|attesa)\s*',b['text'],re.I)]
  if not movement:continue
  lo=[r for r in [d,*d['alternatives']] if r['clip_id']==master];hi=[r for r in [right,*right['alternatives']] if r['clip_id']==master] if right else [None]
  if lo and hi:
   a=max(lo,key=lambda r:r['semantic']);b=max(hi,key=lambda r:r['semantic']) if right else None;start=a['end_frame'];end=b['start_frame'] if b else sources[master]['duration_frames']
   if b is None:
    tail=sorted([w for w in words[master] if w['start_frame']>=start],key=lambda w:w['start_frame'])
    for x,y in zip(tail,tail[1:]):
     if x['end_frame']-start>=4*fps and y['start_frame']-x['end_frame']>=2.5*fps:
      end=min(end,x['end_frame']+round(.4*fps));break
   if 0<end-start<=30*fps:
    action={'kind':'action','beat_id':movement[0]['beat_id'],'action_beats':[m['beat_id'] for m in movement],'media_id':sources[master]['media_id'],'take_id':sources[master]['take_id'],'start_frame':start,'end_frame':end,'shot_size':'wide','basis':'script_between_anchors' if right else 'script_take_tail'}
    d['action_after']=[action];actions.append(action)
 report({'phase':'listening','current':0,'total':len(decisions)})
 reactions=[]
 for i,d in enumerate(decisions):
  if i and not directed:
   overlay=listening_overlay(d,decisions[i-1],list(sources.values()),fps,round(float(payload.get('settings',{}).get('minimum_shot_seconds',1.2))*fps),decisions)
   if overlay:decisions[i-1]['reaction_overlay']=overlay;reactions.append(overlay)
 profiles={}
 for cid,source in sources.items():
  visible=[u for u in kept if u['clip']==cid and u['ASD']=='visible']
  distinct={info(u)[1] for u in visible}
  if len(distinct)==1:
   anchor=max(visible,key=lambda u:u['end']-u['start']);profiles[source['media_id']]={'role':info(anchor)[1],'start':anchor['start'],'end':anchor['end']}
 from listening_reaction import add_dialogue_listening,add_scripted_breaths
 for cid,source in sources.items():source['_editorial_shot_size']=_size(source,shots)
 if directed:
  context_similarities=(vectors[:original_canonical_count]@unit_vectors.T)[grounded_indices]
  for i,d in enumerate(decisions):
   event=resolve_event(d,editorial_events)
   listening_candidates[i].extend(offcamera_candidates(d,units,labels,sources,profiles,context_similarities,i,beats,event))
 report({'phase':'listening','current':0,'total':len(decisions)})
 reactions.extend(add_dialogue_listening(decisions,listening_candidates,list(sources.values()),beats,profiles,fps,minimum_shot,editorial_events if directed else None,report=report))
 actions.extend(add_scripted_breaths(decisions,list(sources.values()),beats,profiles,fps,report=report))
 report({'phase':'listening','current':len(decisions),'total':len(decisions)})
 errors=[]
 for d in decisions:
  for u in units:
   if u['clip']==d['clip_id'] and labels[u['id']]=='X' and u['start']>=d['matched_start_frame'] and u['end']<=d['matched_end_frame']:errors.append('discarded segment inside '+d['moment_id']+': '+u['id'])
 covered={d['beat_id'] for d in decisions};missing=[b['beat_id'] for b in beats if b['kind']=='dialogue' and b['beat_id'] not in covered];assert not errors,errors
 cursor=0
 for d in decisions:
  d['timeline_start_frame']=cursor;cursor+=d['end_frame']-d['start_frame']+sum(a['end_frame']-a['start_frame'] for a in d.get('action_after',[]))
 verification={'model_classification_only':not directed,'human_cut_plan_used':False,'hardcoded_source_ranges':False,'classified_segments':len(labels),'dialogue_moments':len(canonical),'master_available':bool(masters),'reference_mode':'single_camera_continuous' if len(sources)==1 else 'master_with_coverage_recovery' if masters else 'per_beat','dialogue_beats':len(covered),'missing_dialogue':missing,'actions':len(actions),'reactions':len(reactions),'cleanup':cleanup,'discarded_unverified_moments':discarded_moments,'recovered_speech':recovered,'policy':'close-first-v1 + final interval speaker evidence + constrained continuity search'}

 result={'engine':ENGINE,'plan_id':'groq-local','scene_id':payload.get('scene_id','scene'),'fps':fps,'decisions':decisions,'unmatched_beats':missing,'warnings':['Groq classifica il parlato; scelta camere e raccordi locali. Visibilità stimata, non identificazione personale.'],'planning_summary':{**verification,'classification':payload.get('classification_summary',{})},'visual_review_required':False}
 if not masters:result['warnings'].append('Nessuna master disponibile: montaggio dai campi presenti, senza larghe inventate o alternanze obbligatorie.')
 uncertain=[d for d in decisions if d['speaker_coverage']!='visible']
 result['planning_summary']['speaker_uncertain_moments']=len(uncertain)
 result['editorial']={'events':editorial_events,'summary':(payload.get('editorial') or {}).get('summary',{'status':'not_available'})}
 result['warnings'].extend((payload.get('editorial') or {}).get('warnings',[]))
 result['planning_summary']['editorial_events']=len(editorial_events)
 result['planning_summary']['editorial_covered_by_base']=sum(d.get('editorial_event',{}).get('status')=='covered_by_base' for d in decisions)
 if directed:result['warnings'][0]='Groq classifica il parlato e propone intenzioni narrative; scelta delle riprese e tempi verificati localmente. Espressioni ed emozioni non sono identificate.'
 result['planning_summary']['editorial_insertions']=sum(d.get('editorial_event',{}).get('status')=='inserted' for d in decisions)
 if uncertain:result['warnings'].append(str(len(uncertain))+' momenti con parlante fuori campo o non verificato: controlla le alternative in revisione.')
 if missing:result['warnings'].append(str(len(missing))+' dialoghi del copione senza copertura nelle riprese: visibili in revisione e omessi dalla timeline.')
 result['review_beats']=[{'beat_id':d['decision_id'],'kind':'dialogue','character':d['dialogue_character'],'text':canonical[i]['text'],'script_beat_id':d['beat_id']} for i,d in enumerate(decisions)]
 result['review_beats'].extend(copy.deepcopy(beat) for beat in beats if beat['beat_id'] in missing)
 result['base_decisions']=copy.deepcopy(decisions)
 result['pacing_summary']={'measured_media':0,'removed_seconds':0,'protected_beats':0,'reaction_count':len(reactions),'action_count':len(actions),'short_shot_exceptions':short_exceptions,'unavailable_media':[]}
 return result
