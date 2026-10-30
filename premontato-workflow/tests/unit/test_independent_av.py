import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))

class IndependentAVTests(unittest.TestCase):
 def test_long_spoken_shot_requests_visual_review_without_forcing_a_cut(self):
  from independent_av import compile_av_plan
  d=[{'media_id':'a','field':'a','voice':'a','speaker_visible':True,'start_frame':0,'end_frame':200,'record_frame':0,'ids':['u']}]
  p=compile_av_plan(d,[],25)
  self.assertEqual(len(p['visual_review_requests']),1)
  self.assertEqual(p['visual_review_requests'][0]['status'],'pending_model')
  self.assertEqual(p['visual_review_requests'][0]['allowed_outcomes'],['keep','suggest_existing_alternative','uncertain'])
  self.assertEqual(len(p['video_spine']),1)
 def test_seven_seconds_does_not_trigger_but_contiguous_segments_are_combined(self):
  from independent_av import compile_av_plan
  d=[{'media_id':'a','field':'a','voice':'a','speaker_visible':True,'start_frame':0,'end_frame':175,'record_frame':0,'ids':['u']}]
  self.assertFalse(compile_av_plan(d,[],25)['visual_review_requests'])
  d=[{**d[0],'end_frame':100},{**d[0],'start_frame':100,'end_frame':200,'record_frame':100,'ids':['v']}]
  self.assertEqual(len(compile_av_plan(d,[],25)['visual_review_requests']),1)
 def test_same_visual_hold_with_different_trim_does_not_hide_long_duration(self):
  from independent_av import compile_av_plan
  d=[{'media_id':'a','field':'a','voice':'a','speaker_visible':True,'start_frame':0,'end_frame':100,'record_frame':0,'ids':['u']}, {'media_id':'a','field':'a','voice':'b','speaker_visible':False,'start_frame':200,'end_frame':300,'record_frame':100,'ids':['v']}]
  self.assertEqual(len(compile_av_plan(d,[],25)['visual_review_requests']),1)
 def test_reaction_is_video_only_and_audio_performance_survives(self):
  from independent_av import compile_av_plan
  decisions=[{'media_id':'a','path':'a.mp4','field':'a:close','voice':'a','speaker_visible':True,'start_frame':100,'end_frame':250,'record_frame':0,'ids':['q']}]
  reaction={'media_id':'b','path':'b.mp4','start_frame':20,'end_frame':60,'record_frame':50,'verified_listener':True,'different_person':True,'visible_voice':'b','speaking_voice':'a'}
  p=compile_av_plan(decisions,[reaction],25)
  self.assertEqual(p['audio_spine'][0]['media_id'],'a')
  self.assertEqual(p['duration_frames'],150)
  self.assertEqual([x['media_id'] for x in p['video_spine']],['a','b','a'])
  self.assertEqual(p['video_spine'][1]['audio'],'muted')
 def test_ending_returns_to_speaker_without_discarding_words(self):
  from independent_av import compile_av_plan
  d=[{'media_id':'a','field':'a:close','voice':'a','speaker_visible':True,'start_frame':0,'end_frame':150,'record_frame':0,'ids':['u','v']}]
  c={'media_id':'b','start_frame':0,'end_frame':40,'record_frame':100,'verified_listener':True,'different_person':True,'visible_voice':'b','speaking_voice':'a'}
  p=compile_av_plan(d,[c],25)
  self.assertFalse(p['reactions']) # Only 10 frames return: reject this optional reaction.
  self.assertEqual(p['audio_spine'][0]['ids'],['u','v'])
 def test_wrong_listener_and_short_cover_are_rejected(self):
  from independent_av import compile_av_plan
  d=[{'media_id':'a','field':'a','voice':'a','speaker_visible':True,'start_frame':0,'end_frame':200,'record_frame':0,'ids':['u']}]
  for voice,length in [('a',40),('b',20)]:
   c={'media_id':'b','start_frame':0,'end_frame':length,'record_frame':50,'verified_listener':True,'different_person':True,'visible_voice':voice,'speaking_voice':'a'}
   self.assertFalse(compile_av_plan(d,[c],25)['reactions'])
 def test_unknown_coverage_is_a_check_request_not_an_editorial_pass(self):
  from independent_av import compile_av_plan
  d=[{'media_id':'a','field':'unknown','voice':None,'speaker_visible':False,'start_frame':0,'end_frame':200,'record_frame':0,'ids':['u']}]
  p=compile_av_plan(d,[],25)
  self.assertFalse(p['editorial_ready'])
  self.assertEqual(p['check_requests'][0]['ids'],['u'])
 def test_noncontiguous_audio_clock_is_rejected(self):
  from independent_av import compile_av_plan
  with self.assertRaises(ValueError):compile_av_plan([{'media_id':'a','start_frame':0,'end_frame':50,'record_frame':1}],[],25)
