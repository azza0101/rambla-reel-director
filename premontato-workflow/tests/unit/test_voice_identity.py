import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))
class VoiceIdentityTests(unittest.TestCase):
 def gallery(self):
  return [{'voice':'a','source_id':'s','start':i*100,'end':i*100+80,'vector':[1,.02*i]} for i in range(4)]+[{'voice':'b','source_id':'s','start':1000+i*100,'end':1080+i*100,'vector':[.02*i,1]} for i in range(4)]
 def test_clear_voice_is_resolved_without_names(self):
  from voice_identity import identify_embedding
  r=identify_embedding([1,0],self.gallery())
  self.assertEqual(r['voice'],'a');self.assertEqual(r['status'],'identified');self.assertGreater(r['margin'],.5)
 def test_ambiguous_voice_stays_unknown(self):
  from voice_identity import identify_embedding
  self.assertEqual(identify_embedding([1,1],self.gallery())['status'],'unknown')
 def test_query_cannot_identify_itself_via_overlapping_anchors(self):
  from voice_identity import identify_embedding
  g=[{'voice':'a','source_id':'same','start':0,'end':300,'vector':[1,0]} for _ in range(4)]+[{'voice':'b','source_id':'other','start':0,'end':100,'vector':[0,1]} for _ in range(3)]
  self.assertEqual(identify_embedding([1,0],g,{'source_id':'same','start':100,'end':200})['status'],'unknown')
 def test_single_anchor_cannot_certify_voice(self):
  from voice_identity import identify_embedding
  self.assertEqual(identify_embedding([1,0],self.gallery()[:1])['status'],'unknown')
 def test_zero_nonfinite_and_inconsistent_vectors_rejected(self):
  from voice_identity import identify_embedding
  for vector in [[0,0],[float('nan'),1],[1,2,3]]:
   with self.subTest(vector=vector):
    with self.assertRaises(ValueError):identify_embedding(vector,self.gallery())
 def test_low_similarity_does_not_force_a_name(self):
  from voice_identity import identify_embedding
  self.assertEqual(identify_embedding([-1,-1],self.gallery())['status'],'unknown')
class ProfileReconciliationTests(unittest.TestCase):
 def test_consistent_independent_profiles_map_without_matching_names(self):
  from voice_identity import reconcile_profiles
  ref=VoiceIdentityTests().gallery();local=[{'voice':'speaker_99','source_id':'other','start':i*100,'end':i*100+50,'vector':[1,.01*i]} for i in range(4)]
  self.assertEqual(reconcile_profiles(local,ref),{'speaker_99':'a'})
 def test_conflicting_voice_anchors_do_not_force_cross_clip_identity(self):
  from voice_identity import reconcile_profiles
  ref=VoiceIdentityTests().gallery();local=[{'voice':'x','source_id':'other','start':i*100,'end':i*100+50,'vector':v} for i,v in enumerate([[1,0],[1,0],[0,1],[0,1]])]
  self.assertEqual(reconcile_profiles(local,ref),{})
 def test_repeated_same_interval_is_not_independent_profile_evidence(self):
  from voice_identity import reconcile_profiles
  ref=VoiceIdentityTests().gallery();local=[{'voice':'x','source_id':'other','start':0,'end':100,'vector':[1,0]}]*4
  self.assertEqual(reconcile_profiles(local,ref),{})
