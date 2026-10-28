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

 def test_short_generic_reply_does_not_override_existing_scene_context(self):
  import numpy as np
  from scene_edit_jobs import route_scenes
  class Encoder:
   def encode(self,texts):return np.array([[1.,0.] if 'pomodoro' in t.lower() else [0.,1.] for t in texts])
  scenes=[{'scene_id':'a','beats':[{'beat_id':'ba','scene_id':'a','kind':'dialogue','text':'Pomodoro maturo.'}]},{'scene_id':'b','beats':[{'beat_id':'bb','scene_id':'b','kind':'dialogue','text':'Vieni qua.'}]}]
  words=[{'text':t,'start_frame':i*10,'end_frame':i*10+9} for i,t in enumerate(['Vieni','qua.','Vieni','qua.'])]
  source={'media_id':'m','take_id':'t','duration_frames':100,'catalog_context':{'media_id':'m','scene':{'scene_id':'a'}},'segments':[{'text':'Vieni qua.','start_frame':0,'end_frame':40,'words':words}]}
  out=route_scenes({'scenes':scenes,'sources':[source],'fps':25},Encoder())
  self.assertEqual(out['jobs'][1]['sources'],[])

 def test_missing_line_recovery_preserves_real_word_times_and_catalog_scope(self):
  import numpy as np
  from scene_edit_jobs import expand_missing
  class Encoder:
   def encode(self,texts):return np.ones((len(texts),1))
  words=[{'text':'Prima','start_frame':0,'end_frame':9},{'text':'frase.','start_frame':10,'end_frame':19},{'text':'Ultima','start_frame':100,'end_frame':109},{'text':'frase.','start_frame':110,'end_frame':119}]
  source={'media_id':'m','take_id':'t','duration_frames':200,'catalog_context':{'media_id':'m','scene':{'scene_id':'a'}},'segments':[{'text':'Prima frase.','start_frame':0,'end_frame':20,'words':words[:2]},{'text':'Ultima frase.','start_frame':100,'end_frame':120,'words':words[2:]}]}
  foreign={**source,'media_id':'foreign','take_id':'foreign','catalog_context':{'media_id':'foreign','scene':{'scene_id':'b'}}}
  scene={'scene_id':'a','beats':[{'beat_id':'one','kind':'dialogue','text':'Prima frase.'},{'beat_id':'last','kind':'dialogue','text':'Ultima frase.'}]}
  out=expand_missing({'scene':scene,'missing':['last'],'sources':[source,foreign],'selected_sources':[{**source,'segments':[source['segments'][0]]}],'fps':25},Encoder())
  self.assertEqual(out['expanded_media'],1);self.assertEqual([s['media_id'] for s in out['sources']],['m'])
  self.assertEqual({(w['start_frame'],w['end_frame']) for s in out['sources'] for seg in s['segments'] for w in seg['words']},{(w['start_frame'],w['end_frame']) for w in words})

class GenericContextRoutingTests(unittest.TestCase):
 def test_generic_movement_cue_inherits_nearby_content_without_catalog(self):
  import numpy as np
  from scene_edit_jobs import route_scenes
  class Encoder:
   def encode(self,texts):return np.array([[1.,0.] if 'pomodoro' in t.lower() else [0.,1.] for t in texts])
  scenes=[{'scene_id':'a','beats':[{'beat_id':'a1','scene_id':'a','kind':'dialogue','text':'Pomodoro maturo.'}]},{'scene_id':'b','beats':[{'beat_id':'b1','scene_id':'b','kind':'dialogue','text':'Vieni con me.'}]}]
  words=[{'text':t,'start_frame':i*10,'end_frame':i*10+9} for i,t in enumerate(['Pomodoro','maturo.','Vieni','con','me.'])]
  source={'media_id':'m','duration_frames':100,'segments':[{'words':words}]}
  out=route_scenes({'scenes':scenes,'sources':[source],'fps':25},Encoder())
  self.assertEqual(out['jobs'][1]['sources'],[])
  self.assertEqual(len(out['jobs'][0]['sources'][0]['segments']),2)
 def test_all_generic_scenes_remain_explicit_without_invented_coverage(self):
  from scene_edit_jobs import route_scenes
  class Encoder:
   def encode(self,texts):raise AssertionError('Generic phrases are not anchors')
  scenes=[{'scene_id':'a','beats':[{'beat_id':'a1','scene_id':'a','kind':'dialogue','text':'Vieni con me.'}]}]
  source={'media_id':'m','duration_frames':100,'segments':[{'words':[{'text':'Vieni','start_frame':0,'end_frame':9},{'text':'con','start_frame':10,'end_frame':19},{'text':'me.','start_frame':20,'end_frame':29}]}]}
  out=route_scenes({'scenes':scenes,'sources':[source],'fps':25},Encoder())
  self.assertEqual(out['jobs'][0]['status'],'no_coverage')

class AdjacentCatalogRecoveryTests(unittest.TestCase):
 def test_distinctive_missing_line_can_be_recovered_from_an_adjacent_scene_clip(self):
  import numpy as np
  from scene_edit_jobs import expand_missing
  class Encoder:
   def encode(self,texts):return np.ones((len(texts),1))
  scene={'scene_id':'a','beats':[{'beat_id':'ba','kind':'dialogue','text':'Pomodoro maturo basilico fresco profumo intenso.'}]};other={'scene_id':'b','beats':[]}
  words=[{'text':t,'start_frame':i*10,'end_frame':i*10+9} for i,t in enumerate(['Pomodoro','maturo','basilico','fresco','profumo','intenso.'])]
  source={'media_id':'m','take_id':'t','duration_frames':100,'catalog_context':{'media_id':'m','scene':{'scene_id':'b'}},'segments':[{'words':words}]}
  out=expand_missing({'scene':scene,'scenes':[scene,other],'missing':['ba'],'sources':[source],'selected_sources':[],'fps':25},Encoder())
  self.assertEqual([s['media_id'] for s in out['sources']],['m'])
  self.assertEqual(out['sources'][0]['segments'][0]['words'],words)
 def test_adjacent_scene_is_not_a_recovery_source_for_a_generic_invitation(self):
  from scene_edit_jobs import expand_missing
  class Encoder:
   def encode(self,texts):raise AssertionError('No distinctive missing content')
  scene={'scene_id':'a','beats':[{'beat_id':'ba','kind':'dialogue','text':'Vieni con me.'}]};other={'scene_id':'b','beats':[]}
  source={'media_id':'m','duration_frames':100,'catalog_context':{'media_id':'m','scene':{'scene_id':'b'}},'segments':[]}
  out=expand_missing({'scene':scene,'scenes':[scene,other],'missing':['ba'],'sources':[source],'selected_sources':[],'fps':25},Encoder())
  self.assertEqual(out['sources'],[])

 def test_adjacent_recovery_rejects_unrelated_text_despite_high_embedding_score(self):
  import numpy as np
  from scene_edit_jobs import expand_missing
  class Encoder:
   def encode(self,texts):return np.ones((len(texts),1))
  scene={'scene_id':'a','beats':[{'beat_id':'ba','kind':'dialogue','text':'Pomodoro maturo basilico fresco profumo intenso.'}]};other={'scene_id':'b','beats':[]}
  source={'media_id':'m','duration_frames':100,'catalog_context':{'media_id':'m','scene':{'scene_id':'b'}},'segments':[{'words':[{'text':'Treno','start_frame':0,'end_frame':9},{'text':'veloce.','start_frame':10,'end_frame':19}]}]}
  out=expand_missing({'scene':scene,'scenes':[scene,other],'missing':['ba'],'sources':[source],'selected_sources':[],'fps':25},Encoder())
  self.assertEqual(out['sources'],[])
