import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))
from staged_dialogue import recover_single_camera_asides
class SingleCameraAsideTests(unittest.TestCase):
 def run_case(self,text='Una frase aggiunta coerente nel dialogo.',scores=None,status='visible',excluded=()):
  units=[{'id':'a','clip':'C1','start':0,'end':50,'text':'Prima battuta.'},{'id':'b','clip':'C1','start':60,'end':100,'text':text},{'id':'c','clip':'C1','start':110,'end':160,'text':'Risposta.'}]
  labels={'a':'1/P1','b':'X','c':'2/P2'};beats=[{'kind':'dialogue'},{'kind':'dialogue'}]
  matrix=scores or [[1,0],[.75,.4],[0,1]]
  return recover_single_camera_asides(units,labels,matrix,beats,25,lambda u:{'status':status},excluded)
 def test_only_anchored_semantic_aside_with_visible_speaker_is_recovered(self):
  labels,changes=self.run_case();self.assertEqual(labels['b'],'1/P1');self.assertEqual(changes[0]['evidence'],'single_camera_semantic_aside')
 def test_crew_cues_uncertain_meaning_offscreen_speech_and_restarts_are_not_recovered(self):
  for kwargs in [dict(text='Stop rifacciamo questa battuta da capo.'),dict(scores=[[1,0],[.7,.68],[0,1]]),dict(status='absent'),dict(excluded={'b'})]:
   labels,changes=self.run_case(**kwargs);self.assertEqual(labels['b'],'X');self.assertFalse(changes)
if __name__=='__main__':unittest.main()
