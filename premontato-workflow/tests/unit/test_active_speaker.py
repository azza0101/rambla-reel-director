import unittest,sys,hashlib
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).parents[2]/'worker'))
from active_speaker import classify_evidence,MODEL_SHA256
from asd_features import mfcc
class ActiveSpeakerTests(unittest.TestCase):
 def test_short_or_untracked_faces_are_unknown(self):
  face={'mean':3,'positive':1,'height':.2,'tracking':1}
  self.assertEqual(classify_evidence([face],8),'unknown');self.assertEqual(classify_evidence([{**face,'tracking':.2}],50),'unknown')
 def test_negative_tiny_faces_do_not_prove_offscreen(self):
  face={'mean':-2,'positive':0,'height':.08,'tracking':1}
  self.assertEqual(classify_evidence([face],50),'unknown');self.assertEqual(classify_evidence([{**face,'height':.2}],50),'absent')
 def test_visible_evidence_requires_positive_score_and_temporal_support(self):
  face={'mean':.7,'positive':1,'height':.2,'tracking':1}
  self.assertEqual(classify_evidence([face],50),'visible');self.assertEqual(classify_evidence([{**face,'positive':.1}],50),'unknown')
 def test_silence_features_are_finite_without_scipy_or_torch(self):
  for audio in [np.zeros(0,dtype=np.int16),np.zeros(16000,dtype=np.int16)]:
   features=mfcc(audio);self.assertEqual(features.shape[1],13);self.assertTrue(np.isfinite(features).all())
 def test_bundled_model_matches_pinned_hash(self):
  model=Path(__file__).parents[2]/'runtime/models/active-speaker/model.onnx'
  self.assertEqual(hashlib.sha256(model.read_bytes()).hexdigest(),MODEL_SHA256)
if __name__=='__main__':unittest.main()
