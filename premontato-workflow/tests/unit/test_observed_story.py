import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))
class ObservedStoryTests(unittest.TestCase):
 def test_identical_answers_in_different_exchanges_are_story_not_restarts(self):
  from performance_spine import observed_story
  texts=['Questo che cosa e?','Un prosciutto.','E questo?','Un prosciutto.','No, questo e un culatello.','E questo?','Un prosciutto.']
  units=[{'id':str(i),'start':i*50,'end':i*50+40,'text':t} for i,t in enumerate(texts)]
  story=observed_story(units,0,400)
  self.assertEqual([e['text'] for e in story['events']],texts)
  self.assertEqual(sum(e['text']=='Un prosciutto.' for e in story['events']),3)
 def test_missing_screenplay_label_cannot_remove_improvised_line(self):
  from performance_spine import observed_story
  units=[{'id':'a','start':10,'end':100,'text':'Questo non e un prosciutto, e un culatello.','script_label':'X'}]
  self.assertEqual(len(observed_story(units,0,150)['events']),1)
 def test_cannot_omit_without_grounded_reason(self):
  from performance_spine import observed_story
  with self.assertRaises(ValueError):observed_story([{'id':'a','start':0,'end':50,'text':'Battuta.'}],0,60,[{'id':'a','reason':'not_in_script'}])
 def test_scene_boundary_never_splits_a_spoken_unit(self):
  from performance_spine import observed_story
  with self.assertRaises(ValueError):observed_story([{'id':'a','start':0,'end':50,'text':'Battuta.'}],10,60)
