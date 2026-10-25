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
    if group and (word['start_frame']-group[-1]['end_frame']>10 or word['end_frame']-group[0]['start_frame']>8*float(payload['fps'])):flush();group=[]
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
   repeated=len(a)>=2 and ((len(b)>=len(a) and b[:2]==a[:2] and match.size>=min(3,len(a))) or (u['text'].strip().endswith(('...','…')) and len(set(a)&set(b))>=2))
   if repeated and (u['text'].strip().endswith(('...','…')) or match.size/len(a)>=.8):
    labels[u['id']]='X';changes.append({'unit':u['id'],'superseded_by':v['id']});break
 return labels,changes
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
def build_staged(payload,report=lambda e:None):
 from transcript_align import LocalSemanticEncoder
 from automatic_editor import narrative_roles
 from active_speaker import analyze_candidate
 from listening_reaction import listening_overlay
 prepared=payload.get('prepared') or prepare_dialogue(payload);values=reconcile_roles(prepared,validate_labels(prepared,payload['classifications']))
 beats=[{**b,'text':clean_text(b['text'])} for b in payload['beats']];fps=float(payload['fps']);beatmap={'B'+str(i+1):b['beat_id'] for i,b in enumerate(beats)}
 sources={};units=[];labels={};cleanup=[]
 ordered=sorted(payload['sources'],key=lambda s:(s['media_id'],s.get('take_id','')))
 for i,source in enumerate(ordered):
  cid='C'+str(i+1);sources[cid]=source;c=next(c for c in prepared['clips'] if c['key']==source.get('take_id',source['media_id']))
  cleaned,changes=clean_restarts(c['units'],values[c['key']]);cleanup.extend({'clip':cid,**x} for x in changes)
  for u in c['units']:
   uid=cid+u['id'];labels[uid]=cleaned[u['id']];units.append({**u,'id':uid,'clip':cid,'ASD':'unknown'})
 names=prepared['cast']
 def info(u):
  n,role=labels[u['id']].split('/');return 'B'+n,names[role]
 encoder=LocalSemanticEncoder();unit_vectors=encoder.encode([u['text'] for u in units]);labels,recovered=recover_cross_camera(units,labels,unit_vectors@unit_vectors.T,fps,excluded={x['clip']+x['unit'] for x in cleanup})
 kept=[u for u in units if labels[u['id']]!='X']
 def block(us):return {'clip_id':us[0]['clip'],'units':[u['id'] for u in us],'start':us[0]['start'],'end':us[-1]['end'],'text':' '.join(clean_text(u['text']) for u in us),'beat':info(us[0])[0],'role':info(us[0])[1]}
 shots=payload.get('shots',[]);data={'clips':[{'clip_id':cid,'shot_size':_size(s,shots)} for cid,s in sources.items()],'style':payload.get('directions',{})}
 masters=[c['clip_id'] for c in data['clips'] if c['shot_size']=='wide']
 if not masters:raise ValueError('Nessuna master affidabile individuata: verifica i campi nel controllo visivo')
 master=max(masters,key=lambda cid:sum(u['end']-u['start'] for u in kept if u['clip']==cid))
 # At most three balanced ASD samples per camera/role. Estimates never identify real people.
 tasks=[]
 for cid in sources:
  if cid in masters:
   for u in kept:
    if u['clip']==cid:u['ASD']='visible'
   continue
  for role in names.values():
   group=[u for u in kept if u['clip']==cid and info(u)[1]==role and u['end']-u['start']>=.8*fps]
   indices=sorted(set([0,len(group)//2,len(group)-1])) if group else []
   tasks.extend(group[j] for j in indices)
 for i,u in enumerate(tasks):
  report({'phase':'speaker','current':i,'total':len(tasks)})
  try:u['ASD']=analyze_candidate(sources[u['clip']],u['start'],u['end']).get('status','unknown')
  except Exception:u['ASD']='unknown'
 report({'phase':'speaker','current':len(tasks),'total':len(tasks)})

 canonical=[];group=[]
 for u in [u for u in kept if u['clip']==master]:
  if beats[int(info(u)[0][1:])-1]['kind']=='action':continue
  if group:
   prev=group[-1]
   if info(prev)[0]!=info(u)[0] or u['start']-prev['end']>1.5*fps or prev['end']-group[0]['start']>=3*fps:canonical.append(block(group));group=[]
  group.append(u)
 if group:canonical.append(block(group))
 canonical=[c for c in canonical if not(c['end']-c['start']<.8*fps and any(d['beat']==c['beat'] and d['start']>c['end'] and d['end']-d['start']>=fps for d in canonical))]
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
 coverage={}
 for cid in sources:
  for role in names.values():
   rows=[u for u in kept if u['clip']==cid and info(u)[1]==role and u['ASD'] in {'visible','absent'}];yes=sum(u['end']-u['start'] for u in rows if u['ASD']=='visible');no=sum(u['end']-u['start'] for u in rows if u['ASD']=='absent')
   coverage[(cid,role)]='visible' if yes and yes/(yes+no)>=.65 else 'absent' if no and yes/(yes+no)<=.35 else 'unknown'
 roles=narrative_roles(beats,data['style']);candidates=[]
 for ci,c in enumerate(canonical):
  rows=[];actual=beatmap[c['beat']];narrative=roles.get(actual,{}).get('role','free')
  for wi,w in enumerate(windows):
   if w['beat']!=c['beat'] or w['role']!=c['role']:continue
   cosine=float(similarities[ci,wi]);ratio=len(normalize(w['text']).split())/max(1,len(normalize(c['text']).split()))
   if w['clip_id']==master and w['units']!=c['units']:continue
   shared=len(set(core(w['text']))&set(core(c['text'])))
   if (cosine<.48 and shared<3) or not .30<=ratio<=2.0 or (ratio<.45 and cosine<.60):continue
   if w['text'].strip().endswith(('...','…')):continue
   size=_size(sources[w['clip_id']],shots,(w['start']+w['end'])//2);status=coverage[(w['clip_id'],c['role'])];start,end=safe_dialogue_handles({'start_frame':w['start'],'end_frame':w['end']},sources[w['clip_id']],fps)
   row={**w,'start_frame':start,'end_frame':end,'matched_start_frame':w['start'],'matched_end_frame':w['end'],'shot_size':size,'speaker_coverage':status,'semantic':cosine,'media_id':sources[w['clip_id']]['media_id'],'take_id':sources[w['clip_id']]['take_id'],'dialogue_character':c['role'],'narrative_role':narrative,'beat_id':actual,'moment_id':c['moment_id'],'decision_id':c['moment_id'],'matched_text':w['text'],'warnings':[],'confidence':min(1,max(0,cosine)),'coverage':1,'shot_confidence':.75,'speaker_coverage_source':'audio_visual','match_method':'groq_context','pacing':{'duration_frames':end-start}}
   score=(5 if size!='wide' and status=='visible' else 3 if size=='wide' else 2 if status=='unknown' else -1)+cosine+.0001*w['start']-.2*abs(__import__('math').log(ratio))
   if ci==0:
    if size!='wide':continue
    score+=3
   if narrative=='resolution':score+=5 if size=='wide' else 0
   row['score']=score;rows.append(row)
  if not rows:raise RuntimeError('No complete candidate: '+c['text'])
  candidates.append(rows)

 words={cid:[w for seg in s['segments'] for w in seg.get('words',[]) if w['end_frame']>w['start_frame']] for cid,s in sources.items()}
 def can_join(a,b):
  if b['matched_start_frame']<a['matched_end_frame']:return False
  between=[w for w in words[b['clip_id']] if w['start_frame']>=a['matched_end_frame'] and w['end_frame']<=b['matched_start_frame']]
  return b['matched_start_frame']-a['matched_end_frame']<=2.5*fps and not between
 states=[(0,[],{},0)]
 for ci,rows in enumerate(candidates):
  new=[]
  for score,path,last,run in states:
   for row in rows:
    cid=row['clip_id'];prior=path[-1] if path else None
    if row['matched_start_frame']<last.get(cid,-1):continue
    same=bool(prior and prior['clip_id']==cid)
    if same and not can_join(prior,row):continue
    if prior and not same and run<round(float(payload.get('settings',{}).get('minimum_shot_seconds',1.2))*fps):continue
    length=run+row['end_frame']-prior['end_frame'] if same else row['end_frame']-row['start_frame']
    penalty=max(0,length-15*fps)/fps*.1 if same and row['narrative_role']=='free' else 0
    new.append((score+row['score']-penalty,path+[copy.deepcopy(row)],{**last,cid:row['matched_end_frame']},length))
  if not new:raise RuntimeError('No continuous montage path at '+canonical[ci]['moment_id'])
  states=[]
  for camera in sources:states+=sorted([s for s in new if s[1][-1]['clip_id']==camera],key=lambda s:s[0],reverse=True)[:100]
 _,decisions,_,_=max((s for s in states if s[3]>=round(float(payload.get('settings',{}).get('minimum_shot_seconds',1.2))*fps)),key=lambda s:s[0])
 for left,right in zip(decisions,decisions[1:]):
  if left['clip_id']==right['clip_id']:left['end_frame']=right['start_frame'];left['pacing']['duration_frames']=left['end_frame']-left['start_frame']
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
 reactions=[]
 for i,d in enumerate(decisions):
  if i:
   overlay=listening_overlay(d,decisions[i-1],list(sources.values()),fps,round(float(payload.get('settings',{}).get('minimum_shot_seconds',1.2))*fps),decisions)
   if overlay:decisions[i-1]['reaction_overlay']=overlay;reactions.append(overlay)
 errors=[]
 for d in decisions:
  for u in units:
   if u['clip']==d['clip_id'] and labels[u['id']]=='X' and u['start']>=d['matched_start_frame'] and u['end']<=d['matched_end_frame']:errors.append('discarded segment inside '+d['moment_id']+': '+u['id'])
 covered={d['beat_id'] for d in decisions};missing=[b['beat_id'] for b in beats if b['kind']=='dialogue' and b['beat_id'] not in covered];assert not missing and not errors,(missing,errors)
 cursor=0
 for d in decisions:
  d['timeline_start_frame']=cursor;cursor+=d['end_frame']-d['start_frame']+sum(a['end_frame']-a['start_frame'] for a in d.get('action_after',[]))
 verification={'model_classification_only':True,'human_cut_plan_used':False,'hardcoded_source_ranges':False,'classified_segments':len(labels),'dialogue_moments':len(canonical),'dialogue_beats':len(covered),'missing_dialogue':missing,'actions':len(actions),'reactions':len(reactions),'cleanup':cleanup,'recovered_speech':recovered,'policy':'semantic alternatives + speaker evidence + constrained continuity search'}

 result={'engine':ENGINE,'plan_id':'groq-local','scene_id':payload.get('scene_id','scene'),'fps':fps,'decisions':decisions,'unmatched_beats':missing,'warnings':['Groq classifica il parlato; scelta camere e raccordi locali. Visibilità stimata, non identificazione personale.'],'planning_summary':{**verification,'classification':payload.get('classification_summary',{})},'visual_review_required':False}
 result['review_beats']=[{'beat_id':d['decision_id'],'kind':'dialogue','character':d['dialogue_character'],'text':canonical[i]['text'],'script_beat_id':d['beat_id']} for i,d in enumerate(decisions)]
 result['base_decisions']=copy.deepcopy(decisions)
 result['pacing_summary']={'measured_media':0,'removed_seconds':0,'protected_beats':0,'reaction_count':len(reactions),'action_count':len(actions),'short_shot_exceptions':0,'unavailable_media':[]}
 return result
