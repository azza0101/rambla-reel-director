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

class CrossCameraTests(unittest.TestCase):
 def test_recovers_only_anchored_complete_cross_camera_speech(self):
  import numpy as np
  from staged_dialogue import recover_cross_camera
  units=[
   {'id':'a','clip':'A','start':0,'end':30,'text':'Prima frase completa.'},
   {'id':'b','clip':'A','start':32,'end':60,'text':'Una continuazione unica del dialogo.'},
   {'id':'c','clip':'A','start':62,'end':90,'text':'La risposta seguente.'},
   {'id':'d','clip':'B','start':0,'end':30,'text':'La stessa continuazione del dialogo.'},
   {'id':'e','clip':'A','start':200,'end':230,'text':'Una indicazione della troupe fuori scena.'}]
  labels={'a':'1/P1','b':'X','c':'2/P2','d':'1/P1','e':'X'}
  sims=np.eye(5);sims[1,3]=sims[4,3]=.9
  out,recovered=recover_cross_camera(units,labels,sims,25)
  self.assertEqual(out['b'],'1/P1');self.assertEqual(out['e'],'X')
  self.assertEqual(len(recovered),1)
  out,_=recover_cross_camera(units,labels,sims,25,excluded={'b'})
  self.assertEqual(out['b'],'X')

class RestartPreferenceTests(unittest.TestCase):
 def test_latest_complete_delivery_supersedes_repeats_but_not_unique_information(self):
  from staged_dialogue import clean_restarts
  units=[{"id":"a","text":"Porta pacco fragile domani mattina presto.","start":0,"end":20},{"id":"b","text":"Porta pacco fragile domani mattina presto.","start":30,"end":50},{"id":"c","text":"Porta il pacco...","start":60,"end":70}]
  labels,changes=clean_restarts(units,{u["id"]:"1/P1" for u in units})
  self.assertEqual(labels["a"],"X");self.assertEqual(labels["b"],"1/P1");self.assertNotEqual(labels["b"],"X");self.assertEqual(labels["c"],"X")
  units[1]["text"]="Porta pacco fragile domani mattina tardi."
  labels,_=clean_restarts(units,{u["id"]:"1/P1" for u in units})
  self.assertEqual(labels["a"],"1/P1")
