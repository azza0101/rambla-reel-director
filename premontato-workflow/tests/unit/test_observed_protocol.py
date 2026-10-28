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
