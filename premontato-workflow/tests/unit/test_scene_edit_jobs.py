import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))
class SceneRoutingTests(unittest.TestCase):
 def test_mixed_clip_keeps_original_word_times_and_separate_scene_sources(self):
  import numpy as np
  from scene_edit_jobs import route_scenes
  class Encoder:
   def encode(self,texts):return np.array([[1.,0.] if 'pomodoro' in t.lower() else [0.,1.] for t in texts])
  scenes=[{'scene_id':'a','beats':[{'beat_id':'ba','scene_id':'a','kind':'dialogue','text':'Pomodoro maturo.'}]},{'scene_id':'b','beats':[{'beat_id':'bb','scene_id':'b','kind':'dialogue','text':'Treno veloce.'}]}]
  words=[{'text':text,'start_frame':i*10,'end_frame':i*10+9} for i,text in enumerate(['Pomodoro','maturo.','Pomodoro','maturo.','Treno','veloce.','Treno','veloce.'])]
  source={'media_id':'m','take_id':'t','duration_frames':100,'segments':[{'text':'test','start_frame':0,'end_frame':80,'words':words}]}
  out=route_scenes({'scenes':scenes,'sources':[source],'fps':25},Encoder())
  self.assertEqual(len(out['jobs']),2)
  self.assertEqual([s['start_frame'] for s in out['jobs'][0]['sources'][0]['segments']],[0,20])
  self.assertEqual([s['start_frame'] for s in out['jobs'][1]['sources'][0]['segments']],[40,60])
  self.assertEqual(source['segments'][0]['words'],words)
