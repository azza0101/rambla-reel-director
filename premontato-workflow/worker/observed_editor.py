"""Experimental observed-performance camera test, independent of the screenplay.
Reference is an automatic routing/run result or an explicitly requested test range.
No production cut plan, actor name or clip-specific exception belongs here.
"""
import time,math
import numpy as np
from collections import Counter
from voice_identity import source_voices,identify_embedding,reconcile_profiles
from performance_spine import group_voice_turns,jump_cover
from observed_camera import verified_alignment,lock_performances,audit_edit,listener_evidence

def prepare_voice_data(payload,report=None,voice_data=None):
 mode=payload.get('voice_mode','wespeaker')
 if mode not in ('wespeaker','hybrid'):raise ValueError('Modalita vocale non valida')
 sources={s['media_id']:s for s in payload['sources']};main=sources[payload['reference']['media_id']]
 data={}
 for i,(mid,s) in enumerate(sources.items()):
  if report:report({'phase':'voice','current':i,'total':len(sources),'label':'Profili vocali e turni osservati'})
  data[mid]=(voice_data or {}).get(mid) or source_voices(s,payload['units'][mid],report)
 gallery=data[main['media_id']]['gallery']
 for mid,d in data.items():
  rows=[];profile_map=reconcile_profiles(d['gallery'],gallery)
  for u in d['units']:
   result=identify_embedding(u['voice_embedding'],gallery,{'source_id':mid,'start':u['start'],'end':u['end']}) if u.get('voice_embedding') else {'voice':None,'status':'unknown'}
   mapped=profile_map.get(u.get('voice'))
   if result.get('voice') is None and mapped:result={**result,'voice':mapped,'status':'identified','basis':'cross_source_profile_consensus'}
   elif mapped and result.get('voice')!=mapped:result={**result,'voice':None,'status':'unknown','reason':'conflicting_profile_identity'}
   rows.append({**u,'voice':result['voice'],'voice_evidence':result})
  d={**d,'units':rows};data[mid]=d
 if mode=='hybrid':
  from voice_fusion import enhance_source_voices
  data={mid:enhance_source_voices(sources[mid],d,report) for mid,d in data.items()}
 return data


def build_observed_excerpt(payload,report=None,voice_data=None):
 from transcript_align import get_semantic_encoder,normalize
 from staged_dialogue import content_equivalent
 from active_speaker import analyze_candidate
 from speaker_identity import face_vector,match_role,consensus_gallery
 from voice_fusion import eligible_for_face_enrollment
 fps=payload['fps'];reference=payload['reference'];sources={s['media_id']:s for s in payload['sources']};main=sources[reference['media_id']];started=time.perf_counter()
 editorial_mode=payload.get('editorial_mode','legacy')
 if editorial_mode not in ('legacy','independent_av'):raise ValueError('Modalita editoriale non valida')
 if not 0<=reference['start_frame']<reference['end_frame']<=main['duration_frames']:raise ValueError('Intervallo osservato non valido')
 data=prepare_voice_data(payload,report,voice_data)
 observed=[u for u in data[main['media_id']]['units'] if reference['start_frame']<=u['start'] and u['end']<=reference['end_frame']]
 if not observed:raise ValueError('Nessun parlato osservato')
 turns=group_voice_turns(observed,{u['id']:u['voice'] for u in observed},fps)
 # Enroll a face only under an independently identified voice with positive ASD.
 faces=[];field_voice={};turns_by_source={}
 for index,(mid,d) in enumerate(data.items()):
  if report:report({'phase':'face_enrollment','current':index,'total':len(data),'label':'Associo volti e voci con prove indipendenti'})
  s=sources[mid];votes=[]
  for voice in sorted({u['voice'] for u in d['units'] if u['voice'] is not None}):
   pool=sorted([u for u in d['units'] if u['voice']==voice and (payload.get('voice_mode')!='hybrid' or eligible_for_face_enrollment(u)) and u['end']-u['start']>=fps and len(u['text'].split())>=6],key=lambda u:len(u['text'].split()),reverse=True)
   for u in pool[:2]:
    proof=analyze_candidate(s,u['start'],u['end'])
    if proof.get('status')!='visible':continue
    vector=face_vector(s,u['start'],u['end'],proof)
    if vector:faces.append({'role':voice,'media_id':mid,'vector':vector,'quality':max((f.get('mean',0)*f.get('positive',0) for f in proof.get('faces',[])),default=0),'unit_id':u['id']});votes.append(voice);break
  if votes:field_voice[mid]=votes[0] if len(set(votes))==1 else None
  windows=[]
  for index,u in enumerate(d['units']):
   if u['voice'] is None:continue
   for count in range(1,6):
    group=d['units'][index:index+count]
    if len(group)!=count or any(v['voice']!=u['voice'] for v in group) or group[-1]['end']-u['start']>20*fps:break
    if any(b['start']-a['end']>2*fps for a,b in zip(group,group[1:])):break
    windows.append({'voice':u['voice'],'start_frame':u['start'],'end_frame':group[-1]['end'],'text':' '.join(v['text'] for v in group),'unit_ids':[v['id'] for v in group],'context':' '.join(v['text'] for v in d['units'][max(0,index-1):index+count+1])})
  turns_by_source[mid]=windows
 raw_face_count=len(faces);faces=consensus_gallery(faces)
 enc=get_semantic_encoder();queries=enc.encode([t['text'] for t in turns]);context=enc.encode([' '.join(t['text'] for t in turns[max(0,i-1):i+2]) for i in range(len(turns))]);matches={};records=[]
 def size(mid,start,end):
  rows=[s for s in payload.get('shots',[]) if s['media_id']==mid and max(s['start_frame'],start)<min(s['end_frame'],end)]
  return max(rows,key=lambda s:min(s['end_frame'],end)-max(s['start_frame'],start)).get('shot_size','unknown') if rows else 'unknown'
 for index,(mid,ts) in enumerate(turns_by_source.items()):
  if report:report({'phase':'camera_alignment','current':index,'total':len(turns_by_source),'label':'Allineo turni completi e verifico i campi'})
  if mid==main['media_id']:continue
  ts=[t for t in ts if t['voice'] is not None and t['end_frame']-t['start_frame']<=20*fps]
  if not ts:continue
  vectors=enc.encode([t['text'] for t in ts]);contexts=enc.encode([t['context'] for t in ts]);direct=queries@vectors.T;scores=.75*direct+.25*(context@contexts.T)
  for i,t in enumerate(turns):
   for j,c in enumerate(ts):
    a,b=normalize(t['text']).split(),normalize(c['text']).split();ratio=len(b)/max(1,len(a))
    # Preserve semantic negatives and reject half answers. Repeated short answers
    # are disambiguated by monotonic order plus neighboring observed turns.
    if not .55<=ratio<=1.8 or direct[i,j]<(.70 if len(a)>=5 else .82) or ('non' in a)!=('non' in b) or not content_equivalent(t['text'],c['text'],float(direct[i,j])):scores[i,j]=-1
  proofs={}
  def verify(j):
   c=ts[j];s=sources[mid];proof=analyze_candidate(s,c['start_frame'],c['end_frame'])
   vector=face_vector(s,c['start_frame'],c['end_frame'],proof,active_only=False)
   if not vector and proof.get('status')=='visible':vector=face_vector(s,c['start_frame'],c['end_frame'],proof)
   proofs[j]=proof
   return bool(vector and match_role(vector,faces)==c['voice'])
  mapping=verified_alignment(turns,ts,scores.tolist(),verify,minimum=.70,max_rounds=3)
  accepted=[]
  for i,j in enumerate(mapping):
   if j is None:continue
   c=ts[j];s=sources[mid];c={**c,'guard_end':min([u['start'] for u in data[mid]['units'] if u['start']>=c['end_frame']] or [s['duration_frames']])}
   field=str(turns[i]['voice'])+':'+size(mid,c['start_frame'],c['end_frame']);row={**c,'media_id':mid,'field':field,'proof':proofs[j],'similarity':float(direct[i,j])};matches[mid,i]=row;accepted.append(i)
  for field in {matches[mid,i]['field'] for i in accepted}:
   covered=[i for i in accepted if matches[mid,i]['field']==field];duration=sum(turns[i]['end_frame']-turns[i]['start_frame'] for i in covered);total=sum(t['end_frame']-t['start_frame'] for t in turns if str(t['voice'])==field.split(':')[0]);records.append({'id':mid,'field':field,'order':(sources[mid].get('start_tc',''),sources[mid]['name']),'coverage':duration/max(1,total),'usable':True})
 locks=lock_performances(records);decisions=[];warnings=[]
 for i,t in enumerate(turns):
  lo=t['start_frame'];hi=turns[i+1]['start_frame'] if i+1<len(turns) else min(main['duration_frames'],t['end_frame']+round(.32*fps))
  proof=analyze_candidate(main,lo,t['end_frame']);vector=face_vector(main,lo,t['end_frame'],proof,active_only=False)
  if not vector and proof.get('status')=='visible':vector=face_vector(main,lo,t['end_frame'],proof)
  visible=match_role(vector,faces) if vector else None
  chosen={'media_id':main['media_id'],'start_frame':lo,'end_frame':hi,'field':str(field_voice.get(main['media_id']))+':'+size(main['media_id'],lo,hi),'text':t['text'],'ids':list(t['unit_ids']),'base_start':lo,'base_end':hi,'speaker_visible':visible is not None and visible==t['voice'],'voice':t['voice'],'evidence':proof}
  candidates=[v for (mid,k),v in matches.items() if k==i]
  if not chosen['speaker_visible'] and candidates:
   c=max(candidates,key=lambda c:(locks.get(c['field'])==c['media_id'],c['similarity']))
   chosen={**chosen,'media_id':c['media_id'],'start_frame':c['start_frame'],'end_frame':min(c['guard_end'],sources[c['media_id']]['duration_frames'],c['end_frame']+min(round(.32*fps),max(0,hi-t['end_frame']))),'field':c['field'],'text':c['text'],'speaker_visible':True,'evidence':c['proof'],'equivalence':'semantic_candidate_unverified_visual_actions'}
   if locks.get(c['field'])!=c['media_id']:warnings.append({'kind':'older_whole_turn_fallback','ids':t['unit_ids']})
  if not chosen['speaker_visible']:warnings.append({'kind':'speaker_view_unresolved','ids':t['unit_ids']})
  if decisions and decisions[-1]['media_id']==chosen['media_id'] and decisions[-1]['end_frame']==chosen['start_frame']:
   d=decisions[-1];d['end_frame']=chosen['end_frame'];d['base_end']=hi;d['ids']+=chosen['ids'];d['text']+=' '+chosen['text'];d['speaker_visible']=d['speaker_visible'] and chosen['speaker_visible']
  else:decisions.append(chosen)
 clock=0
 for d in decisions:d['record_frame']=clock;d['path']=sources[d['media_id']]['path'];clock+=d['end_frame']-d['start_frame']
 covers=[]
 for a,b in zip(decisions,decisions[1:]):
  if a['field']!=b['field'] or a['media_id']==b['media_id'] and a['end_frame']==b['start_frame']:continue
  join=b['record_frame'];length=math.ceil(1.6*fps);lo=max(0,b['base_start']-round(.4*fps));hi=min(main['duration_frames'],lo+length);at=join-round(.4*fps)
  proof=analyze_candidate(main,lo,hi);vector=face_vector(main,lo,hi,proof,active_only=False);visible=match_role(vector,faces) if vector else None
  voices=[u['voice'] for u in observed if max(u['start'],lo)<min(u['end'],hi)];evidence=listener_evidence(visible,voices)
  c={'media_id':main['media_id'],'path':main['path'],'start_frame':lo,'end_frame':hi,'record_frame':at,**evidence}
  cover=jump_cover(join,clock,c,fps)
  if cover:covers.append(cover)
 audit=audit_edit(decisions,covers,[u['id'] for u in observed],fps)
 result={'engine':'observed-voice-turns-v4-hybrid-experimental' if payload.get('voice_mode')=='hybrid' else 'observed-voice-turns-v3-experimental','voice_mode':payload.get('voice_mode','wespeaker'),'voice_diagnostics':{mid:d.get('diarization',{'status':'not_requested'}) for mid,d in data.items()},'fps':fps,'editorial_status':'diagnostic_only','release_ready':False,'can_create_diagnostic_timeline':audit['ready'],'excerpt':True,'human_cut_plan':False,'script_filters_applied':False,'multicam_assumed':False,'source_event_count':len(observed),'voice_turns':len(turns),'decisions':decisions,'covers':covers,'warnings':warnings,'audit':audit,'duration_frames':clock,'seconds':time.perf_counter()-started,'positive_face_anchors':len(faces),'face_observations':raw_face_count,'face_consensus_roles':sorted({r['role'] for r in faces}),'performance_locks':locks,'face_provenance':[{k:r[k] for k in ['role','media_id','unit_id','quality']} for r in faces]}
 if editorial_mode=='independent_av':
  from independent_av import compile_av_plan
  proposals=[]
  for index,d in enumerate(decisions):
   if report:report({'phase':'listener_coverage','current':index,'total':len(decisions),'label':'Verifico ascolti sopra la performance audio'})
   length=math.ceil(1.6*fps);margin=math.ceil(.5*fps)
   if not d['speaker_visible'] or d['voice'] is None or d['end_frame']-d['start_frame']<length+2*margin:continue
   lo=d['base_start']+margin;hi=lo+length
   if hi>d['base_end']:continue
   proof=analyze_candidate(main,lo,hi);vector=face_vector(main,lo,hi,proof,active_only=False);visible=match_role(vector,faces) if vector else None
   voices=[u['voice'] for u in observed if max(u['start'],lo)<min(u['end'],hi)]
   evidence=listener_evidence(visible,voices)
   if evidence['verified_listener']:proposals.append({'media_id':main['media_id'],'path':main['path'],'start_frame':lo,'end_frame':hi,'record_frame':d['record_frame']+margin,**evidence})
  result['av_plan']=compile_av_plan(decisions,proposals,fps)
  # Preserve unresolved turn boundaries even where contiguous source video is merged.
  result['av_plan']['observed_turns']=[dict(t) for t in turns]
  result['av_plan']['turn_checks']=[{'ids':t['unit_ids'],'voice':t['voice'],'text':t['text'],'start_frame':t['start_frame'],'end_frame':t['end_frame'],'verified_alternatives':sum(k==i for mid,k in matches)} for i,t in enumerate(turns)]
  for request in result['av_plan']['visual_review_requests']:
   ids=set(request['ids'])
   request['turns']=[t for t in result['av_plan']['turn_checks'] if ids.intersection(t['ids'])]
   request['alternatives']=[{'candidate_id':f'{mid}:{c["start_frame"]}:{c["end_frame"]}','media_id':mid,'start_frame':c['start_frame'],'end_frame':c['end_frame'],'text':c['text'],'voice':c['voice'],'field':c['field'],'similarity':c['similarity']} for (mid,i),c in matches.items() if ids.intersection(turns[i]['unit_ids'])]
  result['av_plan']['jump_covers']=covers
  result['editorial_mode']=editorial_mode
  result['seconds']=time.perf_counter()-started
 return result
