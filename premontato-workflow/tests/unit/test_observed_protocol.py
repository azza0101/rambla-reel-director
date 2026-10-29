import sys,unittest,json,io
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))
class ObservedProtocolTests(unittest.TestCase):
 def test_interval_audit_available_without_voice_model(self):
  from protocol import dispatch
  payload={'decisions':[{'media_id':'m','field':'x','start_frame':0,'end_frame':50,'record_frame':0,'ids':['u']}],'covers':[],'event_ids':['u'],'fps':25}
  result=dispatch({'protocol':1,'request_id':'audit','action':'audit_observed_edit','payload':payload})
  self.assertTrue(result['result']['ready'])
 def test_experimental_plan_is_explicit_and_forwards_progress(self):
  from protocol import dispatch
  def fake(p,report):report({'phase':'voice','current':1,'total':2});return {'engine':'experimental'}
  output=io.StringIO()
  with patch('observed_editor.build_observed_excerpt',side_effect=fake),redirect_stdout(output):
   result=dispatch({'protocol':1,'request_id':'x','action':'build_observed_excerpt','payload':{'test':True}})
  self.assertEqual(result['result']['engine'],'experimental');self.assertEqual(json.loads(output.getvalue())['status'],'progress')

class VoiceEvidenceProtocolTests(unittest.TestCase):
 def test_voice_action_is_local_and_forwards_progress(self):
  from protocol import dispatch
  def fake(payload,report):
   report({'phase':'voice_diarization','current':1,'total':1})
   return {'engine':'local_voice_evidence_v1','voice_mode':'hybrid'}
  output=io.StringIO()
  with patch('voice_fusion.analyze_voice_evidence',side_effect=fake),redirect_stdout(output):
   result=dispatch({'protocol':1,'request_id':'voice','action':'analyze_voice_evidence','payload':{'source':{},'units':[]}})
  self.assertEqual(result['result']['voice_mode'],'hybrid')
  self.assertEqual(json.loads(output.getvalue())['result']['phase'],'voice_diarization')
 def test_invalid_voice_mode_is_rejected_before_model_load(self):
  from voice_fusion import analyze_voice_evidence
  with patch('voice_identity.source_voices') as primary:
   with self.assertRaises(ValueError):analyze_voice_evidence({'voice_mode':'online','source':{},'units':[]})
  primary.assert_not_called()
 def test_primary_mode_does_not_load_secondary(self):
  from voice_fusion import analyze_voice_evidence
  with patch('voice_identity.source_voices',return_value={'units':[]}),patch('voice_fusion.enhance_source_voices') as secondary:
   result=analyze_voice_evidence({'voice_mode':'wespeaker','source':{},'units':[]})
  self.assertEqual(result['voice_mode'],'wespeaker');secondary.assert_not_called()

class ObservedHybridOrderTests(unittest.TestCase):
 def test_secondary_is_calibrated_after_source_profile_reconciliation(self):
  from observed_editor import prepare_voice_data
  sources=[{'media_id':'main'},{'media_id':'other'}]
  payload={'voice_mode':'hybrid','reference':{'media_id':'main'},'sources':sources,'units':{}}
  data={s['media_id']:{'gallery':[],'units':[{'id':'u','start':0,'end':50,'voice':'local-label','voice_embedding':[1,0]}]} for s in sources}
  seen=[]
  def enhance(source,rows,report=None):
   seen.append(rows['units'][0]['voice']);return {**rows,'diarization':{'status':'ready'}}
  with patch('observed_editor.identify_embedding',return_value={'voice':'canonical','status':'identified','basis':'source_local_voice_embedding'}),patch('observed_editor.reconcile_profiles',return_value={}),patch('voice_fusion.enhance_source_voices',side_effect=enhance):
   result=prepare_voice_data(payload,voice_data=data)
  self.assertEqual(seen,['canonical','canonical']);self.assertEqual(result['other']['diarization']['status'],'ready')
 def test_existing_observed_mode_does_not_invoke_native_runtime(self):
  from observed_editor import prepare_voice_data
  payload={'reference':{'media_id':'main'},'sources':[{'media_id':'main'}],'units':{}}
  data={'main':{'gallery':[],'units':[]}}
  with patch('voice_fusion.enhance_source_voices') as enhance:prepare_voice_data(payload,voice_data=data)
  enhance.assert_not_called()
