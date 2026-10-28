"""Optional, source-local voice identity. No names inferred from appearance/text.
WeSpeaker ResNet34 (VoxCeleb, CC-BY-4.0); Kaldi-native-fbank Apache-2.0.
Model inference stays local. Unknown/overlapping/weak evidence stays unknown.
"""
from pathlib import Path
import hashlib,os,sys,time
import numpy as np
MODEL_SHA256='5ef208a9da1453335308a6b6f4e6dfbd7e183a38b604de0a57664f45d257fe94'
VERSION='wespeaker-resnet34-hamming-cmn-v1'
_EXTRACTOR=None

def _normal(vector,dimension=None):
 v=np.asarray(vector,dtype=np.float32)
 if v.ndim!=1 or not len(v) or dimension is not None and len(v)!=dimension or not np.isfinite(v).all() or np.linalg.norm(v)<1e-8:raise ValueError('Embedding vocale non valido')
 return v/np.linalg.norm(v)

def identify_embedding(vector,gallery,exclude=None,min_score=.30,min_margin=.12,min_anchors=3):
 v=_normal(vector);by={}
 for a in gallery:
  e=_normal(a['vector'],len(v))
  if exclude and a.get('source_id')==exclude.get('source_id') and max(a['start'],exclude['start'])<min(a['end'],exclude['end']):continue
  by.setdefault(a['voice'],[]).append(float(v@e))
 scores={voice:float(np.mean(sorted(values,reverse=True)[:3])) for voice,values in by.items() if len(values)>=min_anchors}
 ranked=sorted(scores,key=scores.get,reverse=True)
 if len(ranked)==1 and len({a['voice'] for a in gallery})==1 and scores[ranked[0]]>=.70:
  return {'status':'identified','voice':ranked[0],'scores':scores,'margin':None,'score':scores[ranked[0]],'basis':'single_profile_high_absolute_similarity','open_set_threshold':.70}
 if len(ranked)<2:return {'status':'unknown','voice':None,'reason':'insufficient_independent_anchors','scores':scores,'margin':0.}
 best,second=ranked[:2];margin=scores[best]-scores[second]
 if scores[best]<min_score or margin<min_margin:return {'status':'unknown','voice':None,'reason':'weak_or_ambiguous_voice','scores':scores,'margin':margin}
 return {'status':'identified','voice':best,'scores':scores,'margin':margin,'score':scores[best],'basis':'source_local_voice_embedding'}

class VoiceExtractor:
 def __init__(self,model=None):
  import onnxruntime as ort
  import kaldi_native_fbank as knf
  roots=[Path(os.environ['PREMONTATO_VOICE_MODEL'])] if os.environ.get('PREMONTATO_VOICE_MODEL') else []
  roots.extend([Path(sys.executable).parent/'models/speaker/wespeaker.onnx',Path(__file__).resolve().parents[1]/'runtime/models/speaker/wespeaker.onnx'])
  self.path=Path(model) if model else next((p for p in roots if p.is_file()),None)
  if self.path is None or not self.path.is_file():raise RuntimeError('Modello voce locale non disponibile')
  if hashlib.sha256(self.path.read_bytes()).hexdigest()!=MODEL_SHA256:raise RuntimeError('Modello voce locale non valido')
  options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
  self.session=ort.InferenceSession(str(self.path),sess_options=options,providers=['CPUExecutionProvider']);self.knf=knf
 def extract(self,audio):
  audio=np.asarray(audio,dtype=np.float32)
  if audio.ndim!=1 or not np.isfinite(audio).all():raise ValueError('Audio voce non valido')
  if len(audio)<3200:return None
  if len(audio)>16000*12:audio=audio[(len(audio)-16000*12)//2:(len(audio)+16000*12)//2]
  opts=self.knf.FbankOptions();opts.frame_opts.dither=0;opts.frame_opts.samp_freq=16000;opts.frame_opts.window_type='hamming';opts.frame_opts.snip_edges=True;opts.mel_opts.num_bins=80
  bank=self.knf.OnlineFbank(opts);bank.accept_waveform(16000,audio.tolist());bank.input_finished()
  if bank.num_frames_ready<10:return None
  features=np.stack([bank.get_frame(i) for i in range(bank.num_frames_ready)]);features-=features.mean(0,keepdims=True)
  vector=self.session.run(None,{self.session.get_inputs()[0].name:features[None].astype(np.float32)})[0].reshape(-1)
  return _normal(vector,256).tolist()
 def embedding(self,source,start,end):
  from local_audio import load_pcm16
  from cache import get_or_compute
  count=source['duration_frames'];fps=float(source['fps']);clock=time.perf_counter()
  if not 0<=start<end<=count:raise ValueError('Intervallo voce non valido')
  path=Path(source['path']);stat=path.stat();fingerprint=[str(path.resolve()),stat.st_size,stat.st_mtime_ns]
  def compute():
   pcm,_=load_pcm16(source);return self.extract(pcm[round(start/fps*16000):round(end/fps*16000)])
  root=Path(os.environ.get('PREMONTATO_CACHE_DIR','.premontato-cache'))/'voice-identity'
  vector,hit=get_or_compute(root,fingerprint,VERSION,{'start':start,'end':end,'fps':fps,'model':MODEL_SHA256},compute)
  if vector is not None:vector=_normal(vector,256).tolist()
  return {'vector':vector,'cache_hit':hit,'elapsed_seconds':time.perf_counter()-clock}

def get_extractor():
 global _EXTRACTOR
 if _EXTRACTOR is None:_EXTRACTOR=VoiceExtractor()
 return _EXTRACTOR

def source_voices(source,units,report=None,extractor=None):
 """Identity labels are source-local. They are not actor names or truth labels."""
 from collections import Counter
 extractor=extractor or get_extractor();fps=float(source['fps']);gallery=[];telemetry={'cache_hits':0,'requests':0,'seconds':0.};vectors={}
 def get(u):
  if u['id'] not in vectors:
   result=extractor.embedding(source,u['start'],u['end']);vectors[u['id']]=result['vector'];telemetry['requests']+=1;telemetry['cache_hits']+=int(result['cache_hit']);telemetry['seconds']+=result['elapsed_seconds']
  return vectors[u['id']]
 anchors=[u for u in units if u.get('speaker_reliable') and u.get('speaker_name') and u['end']-u['start']>=fps]
 counts=Counter(u['speaker_name'] for u in anchors);voices={v for v,n in counts.items() if n>=4}
 for voice in sorted(voices):
  pool=[u for u in anchors if u['speaker_name']==voice]
  # Spread anchors over time; do not let a repeated pickup dominate a profile.
  indices=np.linspace(0,len(pool)-1,min(20,len(pool)),dtype=int)
  for i in indices:
   u=pool[i];vector=get(u)
   if vector:gallery.append({'voice':voice,'source_id':source['media_id'],'start':u['start'],'end':u['end'],'unit_id':u['id'],'vector':vector})
 evaluations=[]
 for a in gallery:
  result=identify_embedding(a['vector'],gallery,{'source_id':source['media_id'],'start':a['start'],'end':a['end']})
  evaluations.append({'unit_id':a['unit_id'],'expected':a['voice'],**result})
 predictions=[]
 for i,u in enumerate(units):
  if report and i%10==0:report({'phase':'voice','current':i,'total':len(units),'label':'Identifico le voci locali'})
  vector=get(u)
  result=identify_embedding(vector,gallery,{'source_id':source['media_id'],'start':u['start'],'end':u['end']}) if vector else {'voice':None,'status':'unknown','reason':'speech_too_short','margin':0.}
  predictions.append({**u,'voice':result['voice'],'voice_evidence':result,'voice_embedding':vector})
 return {'units':predictions,'gallery':gallery,'validation':evaluations,'telemetry':telemetry,'voices':sorted(voices),'model':VERSION}

def reconcile_profiles(local_gallery,reference_gallery):
 """Map source-local labels using three non-overlapping acoustic observations.
 A shared textual label supplies no evidence. At least 80% must agree.
 """
 from collections import Counter
 groups={}
 for a in sorted(local_gallery,key=lambda a:(a['source_id'],a['start'],a['end'])):
  group=groups.setdefault(a['voice'],[])
  if any(a['source_id']==b['source_id'] and max(a['start'],b['start'])<min(a['end'],b['end']) for b in group):continue
  group.append(a)
 mapping={}
 for voice,anchors in groups.items():
  votes=[]
  for a in anchors:
   r=identify_embedding(a['vector'],reference_gallery,{'source_id':a['source_id'],'start':a['start'],'end':a['end']})
   if r['voice'] is not None:votes.append(r['voice'])
  if not votes:continue
  winner,count=Counter(votes).most_common(1)[0]
  if count>=3 and count/max(1,len(anchors))>=.8:mapping[voice]=winner
 return mapping
