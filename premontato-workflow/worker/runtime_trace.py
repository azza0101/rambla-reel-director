"""Per-plan local work counters; no paths, transcript or historical cache costs."""
from contextvars import ContextVar
from functools import wraps
from time import perf_counter
_ACTIVE=ContextVar('premontato_trace',default=None)

def _bucket():
 return dict(calls=0,interval_cache_hits=0,sample_cache_hits=0,decoded_samples=0,detected_frames=0,tracked_faces=0,inference_calls=0,elapsed_seconds=0.,stage_seconds={},errors=0)

class PipelineTrace:
 def __init__(self):
  self.phase='recovery';self.asd={};self.semantic=dict(initializations=0,load_seconds=0.,encode_calls=0,computed_texts=0,cached_texts=0,encode_seconds=0.);self.rms=dict(calls=0,cache_hits=0,elapsed_seconds=0.,scan_seconds=0.,pcm_seconds=0.);self.candidate_rows=0;self.candidate_checks=0
 def report(self,event):
  phase=event.get('phase')
  if phase=='speaker':self.phase='initial'
  elif phase=='listening':self.phase='listening'
  elif phase=='align':self.phase='selection'
 def result(self,elapsed):
  return {'wall_seconds':round(elapsed,6),'semantic':self.semantic,'asd':self.asd,'rms':self.rms,'candidate_rows':self.candidate_rows,'candidate_checks':self.candidate_checks,'asd_provider':'CPUExecutionProvider','asd_intra_op_threads':2}

def record_asd(result,elapsed,error=False):
 trace=_ACTIVE.get()
 if trace is None:return
 b=trace.asd.setdefault(trace.phase,_bucket());b['calls']+=1;b['elapsed_seconds']+=elapsed;b['errors']+=int(error)
 b['interval_cache_hits']+=int(bool(result.get('cache_hit')));b['sample_cache_hits']+=int(bool(result.get('sample_cache_hit')) and not result.get('cache_hit'))
 if not result.get('cache_hit'):
  for key in ('decoded_samples','detected_frames','tracked_faces','inference_calls'):b[key]+=result.get('work',{}).get(key,0)
  for key,value in result.get('stage_seconds',{}).items():b['stage_seconds'][key]=b['stage_seconds'].get(key,0.)+value

def record_rms(result,elapsed):
 trace=_ACTIVE.get()
 if trace is None:return
 b=trace.rms;b['calls']+=1;b['cache_hits']+=int(bool(result.get('cache_hit')));b['elapsed_seconds']+=elapsed
 if not result.get('cache_hit'):
  b['scan_seconds']+=result.get('timing',{}).get('rms_seconds',0.)
  b['pcm_seconds']+=result.get('timing',{}).get('pcm_seconds',0.)

def candidate_checked(proof=False):
 trace=_ACTIVE.get()
 if trace is not None:
  trace.candidate_rows+=int(not proof);trace.candidate_checks+=int(proof)

def trace_pipeline(function):
 @wraps(function)
 def wrapped(payload,report=lambda event:None):
  trace=PipelineTrace();token=_ACTIVE.set(trace);start=perf_counter()
  def progress(event):trace.report(event);report(event)
  try:
   result=function(payload,progress);result['performance']=trace.result(perf_counter()-start);return result
  finally:_ACTIVE.reset(token)
 return wrapped

def trace_rms(function):
 @wraps(function)
 def wrapped(source):
  start=perf_counter();result=function(source);record_rms(result,perf_counter()-start);return result
 return wrapped

def record_semantic(kind,elapsed,created=0,requested=0,computed=0):
 trace=_ACTIVE.get()
 if trace is None:return
 b=trace.semantic
 if kind=='load':b['initializations']+=created;b['load_seconds']+=elapsed
 else:
  b['encode_calls']+=1;b['computed_texts']+=computed;b['cached_texts']+=requested-computed;b['encode_seconds']+=elapsed
