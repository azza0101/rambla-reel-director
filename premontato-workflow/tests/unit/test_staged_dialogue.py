import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))
class StagedDialogueTests(unittest.TestCase):
 def test_units_preserve_word_bounds_without_scene_specific_names(self):
  from staged_dialogue import prepare_dialogue
  p=prepare_dialogue({'beats':[{'beat_id':'b','kind':'dialogue','character':'ALICE','text':'Grazie davvero.'}],'sources':[{'media_id':'m','take_id':'t','duration_frames':100,'segments':[{'text':'Grazie davvero.','words':[{'text':'Grazie','start_frame':12,'end_frame':25},{'text':'davvero.','start_frame':26,'end_frame':45}]}]}],'fps':25})
  self.assertEqual(p['clips'][0]['units'][0]['start'],12);self.assertEqual(p['clips'][0]['units'][0]['end'],45)
  self.assertIn('ALICE',p['cast'].values());self.assertNotIn('FABRIZIO',p['cast'].values())
 def test_invalid_or_incomplete_labels_fail_closed(self):
  from staged_dialogue import prepare_dialogue,validate_labels
  p=prepare_dialogue({'beats':[{'beat_id':'x','kind':'dialogue','character':'X','text':'ciao'}],'sources':[{'media_id':'m','take_id':'t','duration_frames':20,'segments':[{'words':[{'text':'ciao','start_frame':1,'end_frame':12}]}]}],'fps':25})
  with self.assertRaises(ValueError):validate_labels(p,{'m':{}})
 def test_last_complete_restart_wins_without_literal_actor_or_frame_constants(self):
  from staged_dialogue import clean_restarts
  units=[{'id':'S0','text':'Guarda il tavolo...','start':10,'end':30},{'id':'S1','text':'Guarda il tavolo blu.','start':45,'end':85}]
  labels={'S0':'1/P1','S1':'1/P1'}
  cleaned,changes=clean_restarts(units,labels)
  self.assertEqual(cleaned['S0'],'X');self.assertEqual(cleaned['S1'],'1/P1')
if __name__=='__main__':unittest.main()

class SpeakerConsistencyTests(unittest.TestCase):
 def test_dialogue_uses_screenplay_role_but_actions_preserve_inferred_role(self):
  from staged_dialogue import reconcile_roles
  scene={'cast':{'P0':'UNKNOWN','P1':'ALICE','P2':'BOB'},'beats':[{'kind':'dialogue','character':'BOB'},{'kind':'action'}]}
  self.assertEqual(reconcile_roles(scene,{'clip':{'S0':'1/P1','S1':'2/P1','S2':'X'}}),{'clip':{'S0':'1/P2','S1':'2/P1','S2':'X'}})
