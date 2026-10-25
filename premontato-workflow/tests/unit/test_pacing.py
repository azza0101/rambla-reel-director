import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[2]/'worker'))
from edit_selector import rms_silences, pace_plan

class PacingTests(unittest.TestCase):
 def fixture(self):
  source={'media_id':'m','take_id':'t','duration_frames':500,'segments':[{'words':[{'text':'prima','start_frame':0,'end_frame':50},{'text':'dopo','start_frame':100,'end_frame':150}]}]}
  plan={'decisions':[{'beat_id':'a','take_id':'t','media_id':'m','start_frame':0,'end_frame':150,'matched_start_frame':0,'matched_end_frame':150,'warnings':[],'alternatives':[]}], 'warnings':[]}
  audio={'m':{'status':'ok','silences':[{'start_frame':50,'end_frame':100}]}}
  return source,plan,audio
 def test_rms_detects_quiet_interval(self):
  import numpy as np
  samples=np.concatenate([np.ones(16000,dtype='float32')*.1,np.zeros(32000,dtype='float32'),np.ones(16000,dtype='float32')*.1])
  result=rms_silences(samples,16000,25)
  self.assertTrue(any(s['start_frame']<=26 and s['end_frame']>=74 for s in result['silences']))
 def test_shortens_internal_silence_and_preserves_every_word(self):
  source,plan,audio=self.fixture()
  out=pace_plan(plan,[source],audio,[],25,{'max_pause_seconds':.4,'minimum_shot_seconds':1.2})
  ranges=out['decisions'][0]['source_ranges']
  self.assertEqual(sum(r['end_frame']-r['start_frame'] for r in ranges),110)
  for word in source['segments'][0]['words']:
   self.assertTrue(any(r['start_frame']<=word['start_frame'] and r['end_frame']>=word['end_frame'] for r in ranges))
 def test_script_pause_is_preserved(self):
  source,plan,audio=self.fixture()
  beats=[{'beat_id':'a','kind':'dialogue','text':'prima dopo'}, {'beat_id':'pause','kind':'action','text':'Pausa'}]
  out=pace_plan(plan,[source],audio,beats,25,{})
  self.assertEqual(out['pacing_summary']['removed_frames'],0)
  self.assertTrue(out['decisions'][0]['pacing']['protected_pause'])
 def test_missing_audio_does_not_remove_pause(self):
  source,plan,audio=self.fixture()
  out=pace_plan(plan,[source],{},[],25,{})
  self.assertEqual(out['pacing_summary']['removed_frames'],0)
  self.assertEqual(out['pacing_summary']['unavailable_media'],['m'])
 def test_quiet_speech_with_word_timestamps_is_not_deleted(self):
  source,plan,audio=self.fixture();source['segments'][0]['words'].append({'text':'sussurro','start_frame':60,'end_frame':95})
  out=pace_plan(plan,[source],audio,[],25,{})
  self.assertTrue(any(r['start_frame']<=60 and r['end_frame']>=95 for r in out['decisions'][0]['source_ranges']))
 def test_short_reply_uses_same_coverage_when_equivalent_alternative_exists(self):
  source,plan,audio=self.fixture()
  plan['decisions'].append({'beat_id':'b','take_id':'other','media_id':'other','start_frame':20,'end_frame':30,'score':.9,'alternatives':[{'take_id':'t','media_id':'m','start_frame':160,'end_frame':175,'score':.9}]})
  other={'media_id':'other','take_id':'other','duration_frames':500,'segments':[]}
  out=pace_plan(plan,[source,other],{},[],25,{})
  self.assertEqual(out['decisions'][1]['media_id'],'m')
 def test_short_reply_without_safe_alternative_is_reported(self):
  source,plan,audio=self.fixture();plan['decisions'][0]['end_frame']=15
  out=pace_plan(plan,[source],{},[],25,{})
  self.assertEqual(out['pacing_summary']['short_shot_exceptions'],1)
 def test_invalid_options_rejected(self):
  source,plan,audio=self.fixture()
  with self.assertRaises(ValueError):pace_plan(plan,[source],audio,[],25,{'max_pause_seconds':-1})

 def test_trims_only_confirmed_quiet_handles(self):
  source,plan,audio=self.fixture()
  source['segments'][0]['words']=[{'text':'battuta','start_frame':50,'end_frame':150}]
  plan['decisions'][0]['end_frame']=200
  audio['m']['silences']=[{'start_frame':0,'end_frame':50},{'start_frame':150,'end_frame':200}]
  out=pace_plan(plan,[source],audio,[],25,{})
  self.assertEqual(out['decisions'][0]['start_frame'],47)
  self.assertEqual(out['decisions'][0]['end_frame'],156)

 def test_script_pause_can_be_overridden_per_beat(self):
  source,plan,audio=self.fixture();plan['decisions'][0]['preserve_pause']=False
  out=pace_plan(plan,[source],audio,[{'beat_id':'a','kind':'dialogue'},{'kind':'action','text':'Pausa'}],25,{})
  self.assertGreater(out['pacing_summary']['removed_frames'],0)
 def test_same_view_across_two_short_beats_is_one_sufficiently_long_shot(self):
  source,plan,audio=self.fixture();plan['decisions'][0].update({'end_frame':20,'shot_size':'wide'})
  plan['decisions'].append({'beat_id':'b','take_id':'t','media_id':'m','start_frame':21,'end_frame':41,'shot_size':'wide'})
  out=pace_plan(plan,[source],{},[],25,{})
  self.assertEqual(out['pacing_summary']['short_shot_exceptions'],0)

 def test_reapplying_settings_is_idempotent_and_disabling_restores_original(self):
  source,plan,audio=self.fixture()
  first=pace_plan(plan,[source],audio,[],25,{})
  second=pace_plan(first,[source],audio,[],25,{})
  self.assertEqual(first['decisions'][0]['source_ranges'],second['decisions'][0]['source_ranges'])
  restored=pace_plan(second,[source],audio,[],25,{'enabled':False})
  self.assertEqual(restored['decisions'][0]['source_ranges'],[{'start_frame':0,'end_frame':150}])
 def test_minimum_does_not_force_an_inferior_alternative(self):
  source,plan,audio=self.fixture()
  plan['decisions'].append({'beat_id':'b','take_id':'other','media_id':'other','start_frame':20,'end_frame':30,'score':.9,'alternatives':[{'take_id':'t','media_id':'m','start_frame':160,'end_frame':175,'score':.4}]})
  out=pace_plan(plan,[source,{'media_id':'other','duration_frames':500}],{},[],25,{})
  self.assertEqual(out['decisions'][1]['media_id'],'other')

 def test_protected_hold_never_replays_next_beats_source_handles(self):
  source={'media_id':'m','take_id':'t','duration_frames':300,'segments':[{'words':[{'text':'uno','start_frame':20,'end_frame':50},{'text':'due','start_frame':100,'end_frame':130}]}]}
  plan={'decisions':[{'beat_id':'a','media_id':'m','take_id':'t','start_frame':17,'end_frame':60,'matched_end_frame':50,'preserve_pause':True},{'beat_id':'b','media_id':'m','take_id':'t','start_frame':90,'end_frame':140,'matched_start_frame':100,'matched_end_frame':130}]}
  audio={'m':{'status':'ok','silences':[{'start_frame':50,'end_frame':100}]}}
  out=pace_plan(plan,[source],audio,[],25,{'comic_hold_seconds':3})
  left,right=out['decisions'];self.assertLessEqual(left['end_frame'],right['start_frame']);self.assertLessEqual(left['source_ranges'][-1]['end_frame'],right['source_ranges'][0]['start_frame'])
