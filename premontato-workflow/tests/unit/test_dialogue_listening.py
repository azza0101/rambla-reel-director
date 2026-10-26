import unittest,sys,copy
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[2]/'worker'))
from listening_reaction import add_dialogue_listening,add_scripted_breaths
class DialogueListening(unittest.TestCase):
 def fixture(self):
  d={'media_id':'speaker','take_id':'speaker','beat_id':'b1','dialogue_character':'SON','shot_size':'close','start_frame':100,'end_frame':250,'matched_start_frame':100,'matched_end_frame':245,'source_ranges':[{'start_frame':100,'end_frame':250}]}
  s=[{'media_id':m,'take_id':m,'start_frame':0,'end_frame':1000,'duration_frames':1000,'segments':[]} for m in ['speaker','mum','other']]
  beats=[{'beat_id':'b1','scene_id':'room','kind':'dialogue','character':'SON'},{'beat_id':'a','scene_id':'room','kind':'action','text':'Silenzio tensivo'},{'beat_id':'b2','scene_id':'room','kind':'dialogue','character':'MUM'},{'beat_id':'b3','scene_id':'elsewhere','kind':'dialogue','character':'OTHER'}]
  profiles={'mum':{'role':'MUM','start':500,'end':550},'other':{'role':'OTHER','start':500,'end':550}}
  candidates=[[{'media_id':m,'take_id':m,'start_frame':150,'end_frame':290,'shot_size':'close','semantic':.8} for m in ['other','mum']]]
  return [d],candidates,s,beats,profiles
 def test_normal_dialogue_has_verified_listener_over_original_audio(self):
  ds,cs,s,b,p=self.fixture()
  with patch('active_speaker.verify_listener',return_value={'verified':True}):add_dialogue_listening(ds,cs,s,b,p,25,30)
  o=ds[0].get('reaction_overlay');self.assertIsNotNone(o);self.assertEqual(o['media_id'],'mum');self.assertEqual(ds[0]['media_id'],'speaker');self.assertGreaterEqual(150-o['offset_frames']-o['end_frame']+o['start_frame'],38)
 def test_uncertain_listener_abstains(self):
  ds,cs,s,b,p=self.fixture()
  with patch('active_speaker.verify_listener',return_value={'verified':False}):add_dialogue_listening(ds,cs,s,b,p,25,30)
  self.assertNotIn('reaction_overlay',ds[0])
 def test_internal_reaction_returns_to_speaker_before_next_angle(self):
  ds,cs,s,b,p=self.fixture();ds.append({'media_id':'mum','take_id':'mum','beat_id':'b2','dialogue_character':'MUM','start_frame':300,'end_frame':350,'shot_size':'close'});cs.append([])
  with patch('active_speaker.verify_listener',return_value={'verified':True}):add_dialogue_listening(ds,cs,s,b,p,25,30)
  self.assertTrue(ds[0]['reaction_overlay']['return_to_speaker']);self.assertGreaterEqual(150-ds[0]['reaction_overlay']['offset_frames']-ds[0]['reaction_overlay']['end_frame']+ds[0]['reaction_overlay']['start_frame'],38)
 def test_script_breath_uses_only_verified_silence_and_is_repeatable(self):
  ds,cs,s,b,p=self.fixture();p['speaker']={'role':'SON','start':100,'end':245}
  audio={'speaker':{'status':'ok','silences':[{'start_frame':248,'end_frame':285}]}}
  with patch('active_speaker.verify_listener',return_value={'verified':True}):
   add_scripted_breaths(ds,s,b,p,25,audio);add_scripted_breaths(ds,s,b,p,25,audio)
  self.assertEqual(len(ds[0]['action_after']),1);self.assertEqual(ds[0]['action_after'][0]['start_frame'],250);self.assertLessEqual(ds[0]['action_after'][0]['end_frame'],285)
 def test_no_breath_over_unmeasured_sound(self):
  ds,cs,s,b,p=self.fixture()
  with patch('active_speaker.verify_listener',return_value={'verified':True}):add_scripted_breaths(ds,s,b,p,25,{})
  self.assertFalse(ds[0].get('action_after'))

class ContinuationLabels(unittest.TestCase):
 def test_pagination_continued_maps_back_to_its_dialogue_not_an_action(self):
  from staged_dialogue import reconcile_roles
  prepared={'cast':{'P0':'UNKNOWN','P1':'SON'},'beats':[{'kind':'dialogue','character':'SON','scene_id':'s'},{'kind':'parenthetical','character':'SON','scene_id':'s','text':'CONTINUED'}]}
  self.assertEqual(reconcile_roles(prepared,{'clip':{'u':'2/P1'}})['clip']['u'],'1/P1')

class MinimumReaction(unittest.TestCase):
 fixture=DialogueListening.fixture
 def test_short_reply_may_use_only_measured_roomtone_to_reach_minimum(self):
  ds,cs,s,b,p=self.fixture();ds[0].update(end_frame=150,source_ranges=[{'start_frame':100,'end_frame':150}])
  with patch('active_speaker.verify_listener',return_value={'verified':True}),patch('edit_selector.analyze_audio',return_value={'status':'ok','silences':[{'start_frame':150,'end_frame':170}]}):add_dialogue_listening(ds,cs,s,b,p,25,30,[{'beat_id':'b1','anchor_text':'','return_to_speaker':False,'hold_reason':'suspense','reactor_character':'MUM'}])
  self.assertGreaterEqual(ds[0]['reaction_overlay']['end_frame']-ds[0]['reaction_overlay']['start_frame'],38);self.assertEqual(ds[0]['end_frame'],158)
 def test_short_reply_without_clean_roomtone_has_no_flash_reaction(self):
  ds,cs,s,b,p=self.fixture();ds[0].update(end_frame=150,source_ranges=[{'start_frame':100,'end_frame':150}])
  with patch('active_speaker.verify_listener',return_value={'verified':True}),patch('edit_selector.analyze_audio',return_value={'status':'ok','silences':[]}):add_dialogue_listening(ds,cs,s,b,p,25,30)
  self.assertNotIn('reaction_overlay',ds[0]);self.assertEqual(ds[0]['end_frame'],150)
