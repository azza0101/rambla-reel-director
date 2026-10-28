import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))
class VoiceTurnTests(unittest.TestCase):
 def test_turns_preserve_repeated_answers_and_source_order(self):
  from performance_spine import group_voice_turns
  us=[{'id':str(i),'start':i*50,'end':i*50+40,'text':t} for i,t in enumerate(['Domanda.','Ancora domanda.','Risposta.','Domanda.','Risposta.'])]
  out=group_voice_turns(us,{'0':'a','1':'a','2':'b','3':'a','4':'b'},25)
  self.assertEqual([r['unit_ids'] for r in out],[['0','1'],['2'],['3'],['4']]);self.assertEqual(sum(r['text']=='Risposta.' for r in out),2)
 def test_unknown_voice_is_not_merged_into_a_known_speaker(self):
  from performance_spine import group_voice_turns
  us=[{'id':str(i),'start':i*50,'end':i*50+40,'text':'Frase.'} for i in range(3)]
  self.assertEqual(len(group_voice_turns(us,{'0':'a','1':None,'2':'a'},25)),3)
 def test_long_gap_stays_a_separate_turn(self):
  from performance_spine import group_voice_turns
  us=[{'id':'a','start':0,'end':40,'text':'A.'},{'id':'b','start':200,'end':240,'text':'B.'}]
  self.assertEqual(len(group_voice_turns(us,{'a':'v','b':'v'},25)),2)
