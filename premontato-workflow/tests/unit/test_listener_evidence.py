import unittest,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[2]/'worker'))
from active_speaker import verify_listener
class ListenerEvidenceTests(unittest.TestCase):
 def face(self,active,box=None):return {'mean':2 if active else -2,'positive':.9 if active else 0,'tracking':1,'height':.3,'box':box or [100,100,100,120]}
 def test_same_inactive_face_before_verified_answer_is_eligible(self):
  with patch('active_speaker.analyze_candidate',side_effect=[{'status':'visible','faces':[self.face(True)]},{'status':'absent','faces':[self.face(False)]}]):self.assertTrue(verify_listener({},10,60,63,120)['verified'])
 def test_another_person_at_another_position_is_not_the_listener(self):
  with patch('active_speaker.analyze_candidate',side_effect=[{'status':'visible','faces':[self.face(True)]},{'status':'absent','faces':[self.face(False,[500,100,100,120])]}]):self.assertFalse(verify_listener({},10,60,63,120)['verified'])
 def test_talking_preroll_is_not_used_as_a_silent_listening_cutaway(self):
  with patch('active_speaker.analyze_candidate',side_effect=[{'status':'visible','faces':[self.face(True)]},{'status':'visible','faces':[self.face(True)]}]):self.assertFalse(verify_listener({},10,60,63,120)['verified'])
