import sys,unittest,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))
class FaceConsensusTests(unittest.TestCase):
 def test_two_independent_matches_use_actual_mean(self):
  from speaker_identity import match_role
  v=[.5,math.sqrt(.75)];g=[{'role':'a','media_id':'m1','vector':v},{'role':'a','media_id':'m2','vector':v}]
  self.assertEqual(match_role([1,0],g),'a')
 def test_same_file_cannot_supply_all_identity_evidence(self):
  from speaker_identity import match_role
  self.assertIsNone(match_role([1,0],[{'role':'a','media_id':'m','vector':[1,0]}]*4))
 def test_one_false_asd_vote_cannot_assign_face_to_two_voices(self):
  from speaker_identity import consensus_gallery
  rows=[{'role':'a','media_id':'m1','vector':[1,0],'quality':2.},{'role':'a','media_id':'m2','vector':[1,0],'quality':2.},{'role':'b','media_id':'m3','vector':[1,0],'quality':.6}]
  g=consensus_gallery(rows);self.assertEqual({r['role'] for r in g},{'a'})
 def test_conflicting_identity_votes_remain_unresolved(self):
  from speaker_identity import consensus_gallery
  rows=[{'role':v,'media_id':v+str(i),'vector':[1,0],'quality':1.} for v in ['a','b'] for i in range(2)]
  self.assertEqual(consensus_gallery(rows),[])
 def test_repeated_anchors_from_one_clip_do_not_outvote_independent_sources(self):
  from speaker_identity import consensus_gallery
  rows=[{'role':'a','media_id':'m','vector':[1,0],'quality':1.}]*100+[{'role':'b','media_id':'n'+str(i),'vector':[1,0],'quality':1.} for i in range(3)]
  self.assertEqual({r['role'] for r in consensus_gallery(rows)},{'b'})
class ActiveIdentitySelectionTests(unittest.TestCase):
 def test_stronger_active_face_wins_over_first_face_in_detection_order(self):
  from speaker_identity import identity_boxes
  weak={'box':[0,0,50,50],'tracking':1.,'mean':.6,'positive':.7};strong={'box':[100,0,50,50],'tracking':1.,'mean':3.,'positive':.9}
  self.assertEqual(identity_boxes({'faces':[weak,strong]},True),[strong['box']])
 def test_competing_active_faces_are_not_arbitrarily_assigned(self):
  from speaker_identity import identity_boxes
  rows=[{'box':[x,0,50,50],'tracking':1.,'mean':2.,'positive':.9} for x in [0,100]]
  self.assertEqual(identity_boxes({'faces':rows},True),[])
 def test_listener_does_not_choose_a_random_face_in_two_shot(self):
  from speaker_identity import identity_boxes
  rows=[{'box':[x,0,50,50],'tracking':1.,'mean':-2.,'positive':0.} for x in [0,100]]
  self.assertEqual(identity_boxes({'faces':rows},False),[])
