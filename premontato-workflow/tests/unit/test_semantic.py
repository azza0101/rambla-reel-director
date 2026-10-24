import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[2]/'worker'))
from transcript_align import semantic_windows, contextual_path

class SemanticTests(unittest.TestCase):
 def test_windows_keep_word_times_and_do_not_join_silences(self):
  source={'media_id':'m','segments':[{'words':[{'text':'Puoi','start_frame':0,'end_frame':8},{'text':'restare.','start_frame':9,'end_frame':20},{'text':'Buonanotte.','start_frame':200,'end_frame':230}]}]}
  rows=semantic_windows(source,25)
  self.assertTrue(rows)
  self.assertFalse(any(r['start_frame']==0 and r['end_frame']==230 for r in rows))
 def test_context_prevents_wrong_late_short_response(self):
  rows=[[{'start_frame':10,'end_frame':20,'score':.8}], [{'start_frame':80,'end_frame':90,'score':.95},{'start_frame':21,'end_frame':29,'score':.7}], [{'start_frame':30,'end_frame':60,'score':.9}]]
  path=contextual_path(rows)
  self.assertEqual([p['start_frame'] for p in path],[10,21,30])
 def test_unrelated_dialogue_can_remain_unmatched(self):
  self.assertEqual(contextual_path([[],[]]),[None,None])
