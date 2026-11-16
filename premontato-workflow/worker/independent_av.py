"""Compile separate audio/video tracks without replacing speech with cover audio.

Input decisions retain the selected spoken performance. This compiler does not
certify that a semantically similar alternate take has the same visual action.
"""
import math
import hashlib
import json


def long_shot_reviews(video,audio,fps,threshold_seconds=7):
 """Queue local visual checks, never invent cuts or infer voices from stills.

 Adjacent segments of the same field count as one hold even after source trims.
 A model adapter must explicitly complete these requests; pending is not passed.
 """
 holds=[]
 for d in video:
  end=d['record_frame']+d['end_frame']-d['start_frame']
  if holds and holds[-1]['end']==d['record_frame'] and holds[-1]['media_id']==d['media_id'] and holds[-1]['field']==d.get('field'):
   holds[-1]['end']=end;holds[-1]['segments'].append(d)
  else:holds.append({'start':d['record_frame'],'end':end,'media_id':d['media_id'],'field':d.get('field'),'segments':[d]})
 result=[]
 for h in holds:
  if h['end']-h['start']<=threshold_seconds*fps:continue
  speech=[d for d in audio if d.get('ids') and d['record_frame']<h['end'] and d['record_frame']+d['end_frame']-d['start_frame']>h['start']]
  if not speech:continue
  sources=[{k:d[k] for k in ('media_id','start_frame','end_frame','record_frame')} for d in h['segments']]
  ids=[u for d in speech for u in d['ids']]
  fingerprint=hashlib.sha256(json.dumps({'policy':'spoken-hold-7s-v1','sources':sources,'ids':ids,'fps':fps},sort_keys=True).encode()).hexdigest()
  result.append({'kind':'long_spoken_shot','review_id':fingerprint,'status':'pending_model','requested_model_family':'local_vision_language','preferred_model':'qwen_vl','record_frame':h['start'],'duration_frames':h['end']-h['start'],'source_segments':sources,'ids':ids,'allowed_outcomes':['keep','suggest_existing_alternative','uncertain'],'questions':['Does the visible person change speaking/listening role?','Are there relevant verified reverse shots or object actions among the supplied alternatives?','Is keeping this long shot justified by continuous action?'],'constraints':['Use supplied candidate IDs and intervals only','Never identify the audible speaker from a still alone','No mandatory cut solely because the threshold was exceeded','Keep existing dialogue audio']})
 return result


def compile_av_plan(decisions, reactions, fps):
 if not isinstance(fps,(int,float)) or not math.isfinite(fps) or fps<=0:
  raise ValueError('FPS non validi')
 audio=[]; clock=0
 for d in decisions:
  start,end,at=(d.get(k) for k in ('start_frame','end_frame','record_frame'))
  if any(type(x) is not int for x in (start,end,at)) or start<0 or end<=start or at!=clock:
   raise ValueError('Base audio non contigua o intervallo non valido')
  audio.append({**d,'kind':'dialogue','audio':'selected_performance'})
  clock+=end-start
 accepted=[]; minimum=math.ceil(1.5*fps); margin=math.ceil(.5*fps)
 for c in sorted(reactions,key=lambda r:r.get('record_frame',-1)):
  start,end,at=(c.get(k) for k in ('start_frame','end_frame','record_frame'))
  if any(type(x) is not int for x in (start,end,at)) or start<0 or end-start<minimum:continue
  length=end-start
  owner=next((d for d in audio if d['record_frame']+margin<=at and at+length<=d['record_frame']+d['end_frame']-d['start_frame']-margin),None)
  if not owner or not owner.get('speaker_visible') or owner.get('voice') is None:continue
  if not c.get('verified_listener') or not c.get('different_person') or c.get('visible_voice') in (None,owner['voice']) or c.get('speaking_voice')!=owner['voice']:continue
  if accepted and at<accepted[-1]['record_frame']+accepted[-1]['end_frame']-accepted[-1]['start_frame']:continue
  accepted.append({**c,'kind':'reaction','audio':'muted'})
 video=[]
 for d in audio:
  at=d['record_frame'];stop=at+d['end_frame']-d['start_frame'];cursor=at
  for c in accepted:
   if not at<=c['record_frame']<stop:continue
   cut=c['record_frame']
   if cut>cursor:video.append({**d,'audio':'muted','start_frame':d['start_frame']+cursor-at,'end_frame':d['start_frame']+cut-at,'record_frame':cursor})
   video.append(c);cursor=cut+c['end_frame']-c['start_frame']
  if cursor<stop:video.append({**d,'audio':'muted','start_frame':d['start_frame']+cursor-at,'record_frame':cursor})
 checks=[{'kind':'speaker_view_unresolved','ids':d.get('ids',[]),'record_frame':d['record_frame'],'duration_frames':d['end_frame']-d['start_frame'],'allowed_evidence':['source_transcript','voice_identity','local_visual_samples'],'automatic_accept':False} for d in audio if not d.get('speaker_visible')]
 return {'engine':'independent-av-v1-experimental','audio_spine':audio,'video_spine':video,'reactions':accepted,'duration_frames':clock,'check_requests':checks,'visual_review_requests':long_shot_reviews(video,audio,fps),'speaker_coverage_verified':not checks,'editorial_ready':False,'content_equivalence_verified':False,'visual_actions_verified':False}
