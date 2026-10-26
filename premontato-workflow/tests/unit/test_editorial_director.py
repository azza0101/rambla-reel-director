import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[2]/'worker'))
from editorial_director import listening_window,find_anchor_end,resolve_event
class EditorialTests(unittest.TestCase):
 def test_word_anchor_drives_internal_reaction_with_readable_return(self):
  source={'segments':[{'words':[{'text':'Carlo!','start_frame':104,'end_frame':115},{'text':'Vieni','start_frame':140,'end_frame':150}]}]}
  d={'beat_id':'b','start_frame':100,'end_frame':220,'matched_start_frame':104,'matched_end_frame':210}
  e={'beat_id':'b','anchor_text':'Carlo!','return_to_speaker':True,'priority':'high'}
  w=listening_window(d,e,source,25,38);self.assertGreaterEqual(w['offset'],15);self.assertGreaterEqual(w['duration'],38);self.assertGreaterEqual(120-w['offset']-w['duration'],38)
 def test_called_name_does_not_override_model_affected_listener(self):
  ds={'beat_id':'b','matched_text':'Carlo! Vieni qua'};events=[{'beat_id':'b','anchor_text':'Carlo!','reactor':'P2'}]
  self.assertEqual(resolve_event(ds,events)['reactor'],'P2')
 def test_short_line_skips_unreadable_a_b_a(self):
  d={'start_frame':0,'end_frame':60};self.assertIsNone(listening_window(d,None,{},25,38))
 def test_intentional_ending_exception_can_stay_on_listener(self):
  d={'start_frame':0,'end_frame':70,'matched_start_frame':0,'matched_end_frame':65};e={'return_to_speaker':False,'hold_reason':'suspense','anchor_text':''}
  w=listening_window(d,e,{},25,38);self.assertEqual(w['offset']+w['duration'],70)
 def test_unknown_anchor_never_guesses_timestamp(self):
  d={'start_frame':0,'end_frame':200};e={'anchor_text':'not spoken','return_to_speaker':True}
  self.assertIsNone(listening_window(d,e,{'segments':[]},25,38))
 def test_word_matching_handles_punctuation_without_scene_specific_names(self):
  s={'segments':[{'words':[{'text':' EH,','start_frame':1,'end_frame':4},{'text':'MARIA!!!','start_frame':4,'end_frame':18}]}]}
  self.assertEqual(find_anchor_end(s,0,30,'eh Maria'),18)

 def test_already_visible_listener_is_recognized_without_duplicate_overlay(self):
  from editorial_director import existing_listener
  d={'media_id':'mum','start_frame':100,'end_frame':150,'speaker_coverage':'offscreen'}
  event={'reactor_character':'MOTHER'}
  self.assertTrue(existing_listener(d,event,{'mum':{'role':'MOTHER'}},25))
  self.assertFalse(existing_listener({**d,'end_frame':125},event,{'mum':{'role':'MOTHER'}},25))

 def test_unclassified_coverage_requires_semantic_context_and_excludes_crew(self):
  from editorial_director import offcamera_candidates
  import numpy as np
  d={'beat_id':'b','media_id':'speaker','matched_text':'vieni qua non capisco quando parla'}
  units=[{'id':'x','clip':'c','start':10,'end':60,'text':'vieni qua non capisco quando parla'},{'id':'a','clip':'c','start':70,'end':100,'text':'risposta'}]
  args=[d,units,{'x':'X','a':'1/P2'},{'c':{'media_id':'listener','take_id':'t','fps':25,'_editorial_shot_size':'close'}},{'listener':{'role':'LISTENER'}},np.array([[.9,.5]]),0,[{'beat_id':'b'}],{'reactor_character':'LISTENER'}]
  self.assertEqual(len(offcamera_candidates(*args)),1)
  units[0]['text']='stop vieni qua non capisco quando parla'
  self.assertEqual(offcamera_candidates(*args),[])
  units[0]['text']='vieni qua non capisco quando parla';units[1]['start']=1000;units[1]['end']=1100
  self.assertEqual(offcamera_candidates(*args),[])
