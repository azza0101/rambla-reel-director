import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))
class JumpCoverTests(unittest.TestCase):
 def test_cover_spans_the_join_and_preserves_base_audio(self):
  from performance_spine import jump_cover
  r=jump_cover(100,200,{'media_id':'listener','start_frame':500,'end_frame':540,'record_frame':90,'verified_listener':True,'different_person':True},25)
  self.assertEqual(r['audio'],'base_unchanged');self.assertLess(r['record_frame'],100);self.assertGreater(r['record_frame']+40,100)
 def test_short_or_unverified_reaction_cannot_hide_a_jump(self):
  from performance_spine import jump_cover
  r={'media_id':'other','start_frame':500,'end_frame':520,'record_frame':90,'verified_listener':True,'different_person':True}
  self.assertIsNone(jump_cover(100,200,r,25))
  r['end_frame']=540;r['verified_listener']=False
  self.assertIsNone(jump_cover(100,200,r,25))
 def test_reaction_after_the_join_does_not_cover_it(self):
  from performance_spine import jump_cover
  self.assertIsNone(jump_cover(100,200,{'media_id':'other','start_frame':0,'end_frame':40,'record_frame':110,'verified_listener':True,'different_person':True},25))
