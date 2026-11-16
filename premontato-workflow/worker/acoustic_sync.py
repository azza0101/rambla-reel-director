"""Local optional same-performance evidence, never assumed from file metadata.

Waveform NCC is deliberately conservative: microphones may differ enough to
make a real pair fail. Failure preserves independent-take processing.
"""
import time
import numpy as np


def estimate_sync(reference,target,sample_rate,start_seconds,end_seconds):
 clock=time.perf_counter();a=np.asarray(reference,dtype=float);b=np.asarray(target,dtype=float)
 if a.ndim!=1 or b.ndim!=1 or not np.isfinite(a).all() or not np.isfinite(b).all() or not isinstance(sample_rate,int) or sample_rate<=0:
  raise ValueError('Audio non valido')
 if not 0<=start_seconds<end_seconds<=len(a)/sample_rate:raise ValueError('Intervallo audio non valido')
 window=2*sample_rate
 def result(status,**extra):return {'status':status,'method':'multi-anchor-waveform-ncc-v2','seconds':time.perf_counter()-clock,**extra}
 if end_seconds-start_seconds<10 or len(b)<window:return result('unavailable',reason='insufficient_anchor_span')
 positions=np.rint(np.linspace(start_seconds*sample_rate,end_seconds*sample_rate-window,7)).astype(int)
 fft_length=1<<(len(b)+window-1).bit_length();spectrum=np.fft.rfft(b,fft_length)
 sums=np.r_[0.,np.cumsum(b)];squares=np.r_[0.,np.cumsum(b*b)]
 energy=np.maximum(0,squares[window:]-squares[:-window]-(sums[window:]-sums[:-window])**2/window)
 peaks=[]
 for start in positions:
  q=a[start:start+window];q=q-q.mean();qenergy=float(q@q)
  if qenergy<1e-10:continue
  corr=np.fft.irfft(spectrum*np.fft.rfft(q[::-1],fft_length),fft_length)[window-1:len(b)]
  scores=corr/np.sqrt(np.maximum(1e-20,energy*qenergy));at=int(np.argmax(scores));score=float(scores[at])
  other=scores.copy();other[max(0,at-sample_rate//4):min(len(other),at+sample_rate//4+1)]=-1
  margin=score-float(np.max(other))
  peaks.append({'reference_seconds':start/sample_rate,'target_seconds':at/sample_rate,'offset_seconds':(at-start)/sample_rate,'ncc':score,'prominence':margin})
 strong=[p for p in peaks if p['ncc']>=.25 and p['prominence']>=.025]
 if len(strong)<5:return result('unverified',reason='weak_or_ambiguous_anchors',anchors=peaks)
 group=max(([p for p in strong if abs(p['offset_seconds']-c['offset_seconds'])<=.02] for c in strong),key=len)
 if len(group)<5 or max(p['reference_seconds'] for p in group)-min(p['reference_seconds'] for p in group)<6:
  return result('unverified',reason='inconsistent_offsets',anchors=peaks)
 # Certify only the requested local span, bounded by anchors at both ends.
 if min(p['reference_seconds'] for p in group)>start_seconds+2 or max(p['reference_seconds'] for p in group)+2<end_seconds-2:
  return result('unverified',reason='unbracketed_interval',anchors=peaks)
 x=np.array([p['reference_seconds'] for p in group]);y=np.array([p['offset_seconds'] for p in group]);slope=float(np.polyfit(x,y,1)[0])
 if abs(slope)*(end_seconds-start_seconds)>.02:return result('unverified',reason='clock_drift',anchors=peaks)
 offset=int(round(float(np.median(y))*sample_rate))
 # A majority of matching anchors cannot certify an intervening edit or a
 # different take. Check overlapping windows across the entire mapped span.
 lo=int(round(start_seconds*sample_rate));hi=int(round(end_seconds*sample_rate))
 if lo+offset<0 or hi+offset>len(b):return result('unverified',reason='mapped_span_out_of_bounds',anchors=peaks)
 checks=[]
 for start in sorted(set([*range(lo,hi-window+1,sample_rate),hi-window])):
  q=a[start:start+window];q=q-q.mean();qe=float(q@q)
  if qe<1e-10:continue
  v=b[start+offset:start+offset+window];v=v-v.mean();ve=float(v@v)
  score=float(q@v)/max(1e-20,float(np.sqrt(qe*ve)))
  checks.append(score)
  if score<.25:return result('unverified',reason='conflicting_internal_audio',anchors=peaks,local_min_ncc=min(checks))
 if not checks:return result('unverified',reason='no_informative_local_audio',anchors=peaks)
 return result('verified',offset_seconds=offset/sample_rate,reference_start_seconds=start_seconds,reference_end_seconds=end_seconds,anchor_count=len(group),anchors=peaks,max_offset_error_seconds=float(np.max(np.abs(y-np.median(y)))),local_min_ncc=min(checks),local_window_count=len(checks))
