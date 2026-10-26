import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[2]/'worker'))
from runtime_trace import trace_pipeline,record_asd,record_rms,candidate_checked

class RuntimeTraceTests(unittest.TestCase):
 def test_current_work_is_grouped_by_phase_and_not_historical_cache_timings(self):
  @trace_pipeline
  def pipeline(payload,report):
   report({'phase':'speaker','current':0,'total':1})
   record_asd({'status':'visible','cache_hit':False,'sample_cache_hit':False,'work':{'decoded_samples':1,'inference_calls':3},'stage_seconds':{'decode':.1,'inference':.2}},.4)
   report({'phase':'listening','current':0,'total':1})
   record_asd({'status':'absent','cache_hit':True,'seconds':99,'stage_seconds':{'decode':99},'work':{}},.001)
   record_asd({'status':'absent','cache_hit':False,'sample_cache_hit':True,'work':{}},.002)
   candidate_checked(False);candidate_checked(False);candidate_checked(True)
   record_rms({'status':'ok','cache_hit':True,'timing':{'rms_seconds':99}},.003)
   return {'decisions':[]}
  p=pipeline({},lambda e:None)['performance'];a=p['asd']['initial'];b=p['asd']['listening']
  self.assertEqual(a['calls'],1);self.assertEqual(a['decoded_samples'],1);self.assertEqual(b['interval_cache_hits'],1);self.assertEqual(b['sample_cache_hits'],1);self.assertEqual(b['stage_seconds'],{});self.assertLess(b['elapsed_seconds'],.01);self.assertEqual(p['candidate_rows'],2);self.assertEqual(p['candidate_checks'],1);self.assertEqual(p['rms']['scan_seconds'],0)
 def test_trace_is_reset_after_failure_and_does_not_leak_between_plans(self):
  @trace_pipeline
  def broken(p,report):
   record_asd({'status':'visible'},1);raise ValueError('bad')
  @trace_pipeline
  def clean(p,report):return {}
  with self.assertRaises(ValueError):broken({},lambda e:None)
  self.assertEqual(clean({},lambda e:None)['performance']['asd'],{})

 def test_real_candidate_entrypoint_contributes_current_work_to_active_trace(self):
  from unittest.mock import patch
  from types import SimpleNamespace
  import active_speaker
  @trace_pipeline
  def pipeline(payload,report):
   report({'phase':'speaker'})
   active_speaker.analyze_candidate({},0,25)
   return {}
  fake=SimpleNamespace(analyze=lambda *args:{'status':'visible','cache_hit':True})
  with patch.object(active_speaker,'_ANALYZER',fake):result=pipeline({},lambda e:None)
  self.assertEqual(result['performance']['asd']['initial']['calls'],1)
  self.assertEqual(result['performance']['asd']['initial']['interval_cache_hits'],1)

 def test_semantic_encoder_reports_load_and_embeddings_without_text_payload(self):
  from runtime_trace import record_semantic
  @trace_pipeline
  def pipeline(payload,report):
   record_semantic('load',.1,created=1)
   record_semantic('encode',.2,requested=5,computed=2)
   return {}
  summary=pipeline({},lambda e:None)['performance']['semantic']
  self.assertEqual(summary['initializations'],1);self.assertEqual(summary['computed_texts'],2);self.assertEqual(summary['cached_texts'],3);self.assertEqual(summary['encode_calls'],1)
