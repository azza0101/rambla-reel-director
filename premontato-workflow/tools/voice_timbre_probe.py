"""Experimental source-local voice consistency benchmark, not a production diarizer.
Usage: bundled-python tools/voice_timbre_probe.py input.json output.json
Input contains source, timed units, and focus_units. Never sends network requests.
LOO agreement is measured against Resolve labels, not human-verified identities.
"""
import sys,json
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
from asd_features import mfcc
from local_audio import load_pcm16

def probe(source,units,focus_units):
 from performance_spine import _units
 _units(units,source['duration_frames']);_units(focus_units,source['duration_frames'])
 pcm,_=load_pcm16(source);us=units;fps=float(source['fps'])
 def feature(u):
  audio=np.asarray(pcm[round(u['start']/fps*16000):round(u['end']/fps*16000)],dtype=np.float32)
  if len(audio)<2000:return None
  m=mfcc(audio);valid=m[:,0]>np.quantile(m[:,0],.25);z=m[valid,1:];stats=np.r_[z.mean(0),z.std(0)]
  # Harmonic evidence is advisory; neither gender nor names are inferred.
  frames=np.lib.stride_tricks.sliding_window_view(audio,640)[::320].copy();frames-=frames.mean(1,keepdims=True);frames*=np.hanning(640);acf=np.fft.irfft(abs(np.fft.rfft(frames,2048))**2,2048,axis=1)[:,:640];acf/=np.maximum(acf[:,:1],1e-12);sub=acf[:,40:250];peaks=(sub[:,1:-1]>sub[:,:-2])&(sub[:,1:-1]>=sub[:,2:]);scores=np.where(peaks,sub[:,1:-1],-1);idx=scores.argmax(1)+41;good=scores.max(1)>.35;pitch=16000/idx[good];pitchstat=np.log(np.quantile(pitch,[.25,.5,.75])) if len(pitch) else np.zeros(3)
  return np.r_[stats,pitchstat]
 from collections import Counter
 counts=Counter(u.get('speaker_name') for u in us if u.get('speaker_reliable') and u.get('speaker_name') and u['end']-u['start']>=25);classes={name for name,count in counts.most_common(2) if count>=3}
 if len(classes)<2:raise RuntimeError('Ancore acustiche insufficienti')
 train=[]
 for u in us:
  if u.get('speaker_reliable') and u.get('speaker_name') in classes and u['end']-u['start']>=25:
   f=feature(u)
   if f is not None:train.append((u,f))
 x=np.array([f for u,f in train]);labels=[u['speaker_name'] for u,f in train];scale=np.maximum(x.std(0),.1);x=x/scale;correct=0;errors=[]
 for i,(u,f) in enumerate(train):
  dist=((x-x[i])**2).mean(1);dist[i]=np.inf;ix=np.argsort(dist)[:3];vote={c:sum(1/(dist[j]+.1) for j in ix if labels[j]==c) for c in set(labels)};pred=max(vote,key=vote.get);correct+=pred==labels[i]
  if pred!=labels[i]:errors.append({'id':u['id'],'expected':labels[i],'predicted':pred,'text':u['text']})
 result=[]
 for u in focus_units:
  f=feature(u)
  if f is None:result.append({**u,'voice_predicted':None});continue
  dist=((x-f/scale)**2).mean(1);self_index=next((i for i,(t,_) in enumerate(train) if t['id']==u['id']),None);
  if self_index is not None:dist[self_index]=np.inf
  ix=np.argsort(dist)[:3];votes={c:sum(1/(dist[j]+.1) for j in ix if labels[j]==c) for c in set(labels)};pred=max(votes,key=votes.get);confidence=votes[pred]/sum(votes.values());result.append({**u,'voice_predicted':pred,'voice_vote':confidence})
 out={'source':source['media_id'],'training_count':len(train),'loo_correct':correct,'loo_total':len(train),'errors':errors,'units':result}
 return out
if __name__=='__main__':
 data=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
 result=probe(data['source'],data['units'],data['focus_units'])
 Path(sys.argv[2]).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:v for k,v in result.items() if k not in ['units','errors']}))
