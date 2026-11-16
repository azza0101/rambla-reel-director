"""Optional coverage from acoustically verified simultaneous recordings.

Independent takes remain the normal fallback. No filename, timecode, cast name
or human reference cut determines a mapping or a camera choice.
"""
from independent_av import compile_av_plan
import math


def discover_sync(main,sources,start,end,report=None):
 import os
 import subprocess
 from pathlib import Path
 from local_audio import load_pcm16
 from cache import get_or_compute
 from acoustic_sync import estimate_sync
 def fingerprint(s):
  p=Path(s['path']);st=p.stat();return [str(p.resolve()),st.st_size,st.st_mtime_ns,s['fps'],s['duration_frames']]
 a,_=load_pcm16(main);result=[]
 for i,s in enumerate(sources):
  if s['media_id']==main['media_id']:continue
  if report:report({'phase':'acoustic_sync','current':i,'total':len(sources),'label':'Cerco esecuzioni simultanee con prove audio'})
  try:
   key=[fingerprint(main),fingerprint(s)];options={'start':start,'end':end,'fps':main['fps']}
   def compute():
    b,_=load_pcm16(s)
    return estimate_sync(a[::4],b[::4],4000,start/main['fps'],end/main['fps'])
   p,hit=get_or_compute(Path(os.environ.get('PREMONTATO_CACHE_DIR','.premontato-cache'))/'acoustic-sync',key,'multi-anchor-waveform-ncc-v2',options,compute)
   result.append({'source':s,**p,'cache_hit':hit})
  except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as e:result.append({'source':s,'status':'failed','reason':type(e).__name__})
 return result


def compile_sync_coverage(main,pairs,turns,fps,inspect):
 pairs=[p for p in pairs if p.get('status')=='verified' and p['source']['fps']==fps and main['fps']==fps]
 if not pairs:return None
 if not turns:return None
 decisions=[];proposals=[];origin=turns[0]['start_frame'];stop=turns[-1]['end_frame']
 def mapping(source,pair,lo,hi):
  if pair:
   if lo/fps<pair['reference_start_seconds'] or hi/fps>pair['reference_end_seconds']:return None
   offset=round(pair['offset_seconds']*fps)
  else:offset=0
  a,b=lo+offset,hi+offset
  if not 0<=a<b<=source['duration_frames']:return None
  return a,b
 for i,t in enumerate(turns):
  lo=t['start_frame'];hi=turns[i+1]['start_frame'] if i+1<len(turns) else stop
  choices=[]
  for s,pair in [(main,None),*[(p['source'],p) for p in pairs]]:
   interval=mapping(s,pair,lo,hi)
   if not interval:continue
   a,b=interval;proof=inspect(s,a,a+t['end_frame']-lo);visible=proof.get('visible_voice')
   verified=t['voice'] is not None and visible==t['voice']
   d={'media_id':s['media_id'],'path':s['path'],'start_frame':a,'end_frame':b,'record_frame':lo-origin,'field':str(visible)+':'+proof.get('shot_size','unknown'),'voice':t['voice'],'speaker_visible':verified,'ids':list(t['unit_ids']),'text':t['text'],'evidence':proof,'basis':'reference_performance' if pair is None else 'verified_local_acoustic_sync'}
   choices.append((d,s,pair))
  if not choices:raise ValueError('Intervallo della performance fuori dalla sorgente')
  chosen,s,pair=max(choices,key=lambda x:(x[0]['speaker_visible'],x[0]['field'].endswith(':close'),x[0]['media_id']==main['media_id']))
  decisions.append(chosen)
  # A listening insert must belong to the same local performance, leave a
  # return to the speaker, and use a positively identified other person.
  length=math.ceil(1.6*fps);margin=math.ceil(.5*fps)
  if chosen['speaker_visible'] and hi-lo>=length+2*margin:
   at=lo+margin
   for listener,source,other_pair in choices:
    if source['media_id']==s['media_id']:continue
    interval=mapping(source,other_pair,at,at+length)
    if not interval:continue
    a,b=interval;proof=inspect(source,a,b);visible=proof.get('visible_voice')
    if visible is not None and visible!=t['voice']:
     proposals.append({'media_id':source['media_id'],'path':source['path'],'start_frame':a,'end_frame':b,'record_frame':at-origin,'verified_listener':True,'different_person':True,'visible_voice':visible,'speaking_voice':t['voice'],'basis':'same_performance_voice_and_positive_face_identity'})
     break
 plan=compile_av_plan(decisions,proposals,fps)
 plan['audio_spine']=[{'media_id':main['media_id'],'path':main['path'],'start_frame':origin,'end_frame':stop,'record_frame':0,'ids':[u for t in turns for u in t['unit_ids']],'kind':'dialogue','audio':'continuous_reference_performance'}]
 plan['observed_turns']=turns;plan['basis']='verified_sync_coverage';plan['selected_turns']=decisions
 plan['same_performance_mapping_verified']=True
 return plan
