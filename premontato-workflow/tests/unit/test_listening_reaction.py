import unittest,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[2]/'worker'))
from edit_selector import pace_plan

class ListeningTests(unittest.TestCase):
 def fixture(self):
  sources=[{'media_id':m,'take_id':m,'duration_frames':700,'start_frame':0,'end_frame':700,'segments':[]} for m in ['girl','master','listener']]
  previous={'beat_id':'invite','take_id':'girl','media_id':'girl','shot_size':'close','start_frame':0,'end_frame':200,'narrative_role':'tension','alternatives':[]}
  answer={'beat_id':'refusal','take_id':'master','media_id':'master','shot_size':'wide','start_frame':300,'end_frame':380,'narrative_role':'resolution','alternatives':[{'take_id':'listener','media_id':'listener','shot_size':'close','start_frame':400,'end_frame':480,'speaker_coverage':'unknown'}]}
  beats=[{'beat_id':'invite','kind':'dialogue','character':'GIRL'},{'beat_id':'refusal','kind':'dialogue','character':'BOY'}]
  return {'decisions':[previous,answer]},sources,beats
 def test_automatic_listening_video_is_overlaid_without_changing_dialogue_audio_duration(self):
  p,s,b=self.fixture()
  with patch('active_speaker.verify_listener',return_value={'verified':True,'method':'test-inference'},create=True):out=pace_plan(p,s,{},b,25,{})
  overlay=out['decisions'][0].get('reaction_overlay');self.assertIsNotNone(overlay);self.assertEqual(overlay['media_id'],'listener');self.assertEqual(out['pacing_summary']['duration_frames'],280);self.assertEqual(out['decisions'][0]['media_id'],'girl')
  self.assertEqual(out['decisions'][1]['shot_size'],'wide');self.assertEqual(overlay['offset_frames']+overlay['end_frame']-overlay['start_frame'],200)
 def test_uncertain_listener_never_becomes_an_automatic_reaction(self):
  p,s,b=self.fixture()
  with patch('active_speaker.verify_listener',return_value={'verified':False},create=True):out=pace_plan(p,s,{},b,25,{})
  self.assertIsNone(out['decisions'][0].get('reaction_overlay'))
 def test_explicitly_disabled_reaction_stays_disabled(self):
  p,s,b=self.fixture();p['decisions'][1]['reaction_enabled']=False
  with patch('active_speaker.verify_listener',return_value={'verified':True},create=True):out=pace_plan(p,s,{},b,25,{})
  self.assertIsNone(out['decisions'][0].get('reaction_overlay'))

 def test_same_angle_listening_preroll_is_not_inserted_as_a_jump_cut(self):
  p,s,b=self.fixture();p['decisions'][0].update(media_id='listener',take_id='listener')
  with patch('active_speaker.verify_listener',return_value={'verified':True},create=True):out=pace_plan(p,s,{},b,25,{})
  self.assertIsNone(out['decisions'][0].get('reaction_overlay'))
