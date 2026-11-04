import unittest,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))

class AcousticSyncTests(unittest.TestCase):
 def test_multiple_independent_anchors_recover_offset(self):
  from acoustic_sync import estimate_sync
  rng=np.random.default_rng(22);x=rng.normal(size=24000);y=np.r_[rng.normal(size=1250),x*.4]
  p=estimate_sync(x,y,1000,1,22)
  self.assertEqual(p['status'],'verified');self.assertAlmostEqual(p['offset_seconds'],1.25,places=3)
 def test_unrelated_performance_is_rejected(self):
  from acoustic_sync import estimate_sync
  r=np.random.default_rng(9)
  self.assertNotEqual(estimate_sync(r.normal(size=24000),r.normal(size=26000),1000,1,22)['status'],'verified')
 def test_silence_does_not_count_as_a_match(self):
  from acoustic_sync import estimate_sync
  self.assertNotEqual(estimate_sync(np.zeros(24000),np.zeros(26000),1000,1,22)['status'],'verified')
 def test_two_copies_of_same_audio_are_ambiguous(self):
  from acoustic_sync import estimate_sync
  x=np.random.default_rng(2).normal(size=24000)
  self.assertNotEqual(estimate_sync(x,np.r_[x,np.zeros(1000),x],1000,1,22)['status'],'verified')
 def test_one_matching_fragment_cannot_certify_whole_scene(self):
  from acoustic_sync import estimate_sync
  r=np.random.default_rng(2);x=r.normal(size=24000);y=r.normal(size=26000);y[2000:4000]=x[2000:4000]
  self.assertNotEqual(estimate_sync(x,y,1000,1,22)['status'],'verified')
 def test_internal_different_performance_invalidates_bracketing_matches(self):
  from acoustic_sync import estimate_sync
  r=np.random.default_rng(22);x=r.normal(size=24000);y=x.copy()
  y[10500:16000]=r.normal(size=5500)
  self.assertNotEqual(estimate_sync(x,y,1000,1,22)['status'],'verified')
 def test_drift_is_not_silently_reported_as_constant_offset(self):
  from acoustic_sync import estimate_sync
  r=np.random.default_rng(2);x=r.normal(size=24000);y=np.interp(np.arange(26000)/1.02,np.arange(len(x)),x)
  self.assertNotEqual(estimate_sync(x,y,1000,1,22)['status'],'verified')
