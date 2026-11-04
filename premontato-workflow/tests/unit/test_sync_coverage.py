import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))

class SyncCoverageTests(unittest.TestCase):
 def inputs(self):
  main={'media_id':'m','path':'m.mp4','duration_frames':1000,'fps':25}
  other={'media_id':'s','path':'s.mp4','duration_frames':1000,'fps':25}
  pair={'source':other,'status':'verified','offset_seconds':1.,'reference_start_seconds':0.,'reference_end_seconds':10.}
  turns=[{'voice':'a','start_frame':0,'end_frame':100,'unit_ids':['q'],'text':'question'},{'voice':'b','start_frame':100,'end_frame':200,'unit_ids':['r'],'text':'reply'}]
  return main,[pair],turns
 def test_camera_mapping_does_not_change_audio_or_event_order(self):
  from sync_coverage import compile_sync_coverage
  main,pairs,turns=self.inputs()
  def inspect(s,start,end):return {'visible_voice':'b' if s['media_id']=='m' else 'a','status':'visible'}
  p=compile_sync_coverage(main,pairs,turns,25,inspect)
  self.assertEqual(p['audio_spine'][0]['media_id'],'m');self.assertEqual(p['audio_spine'][0]['ids'],['q','r'])
  self.assertEqual(p['video_spine'][0]['media_id'],'s');self.assertEqual(p['video_spine'][0]['start_frame'],25)
  self.assertEqual(p['duration_frames'],200)
 def test_unverified_offset_never_enables_multicam(self):
  from sync_coverage import compile_sync_coverage
  main,pairs,turns=self.inputs();pairs[0]['status']='unverified'
  self.assertIsNone(compile_sync_coverage(main,pairs,turns,25,lambda *a:{}))
 def test_mapping_cannot_extrapolate_outside_certified_local_span(self):
  from sync_coverage import compile_sync_coverage
  main,pairs,turns=self.inputs();pairs[0]['reference_end_seconds']=2.
  p=compile_sync_coverage(main,pairs,turns,25,lambda s,*a:{'visible_voice':'a' if s['media_id']=='s' else None})
  self.assertTrue(all(x['media_id']=='m' for x in p['video_spine']))
 def test_long_speech_can_use_verified_listener_above_unchanged_audio(self):
  from sync_coverage import compile_sync_coverage
  main,pairs,turns=self.inputs();turns=turns[:1];turns[0]['end_frame']=150
  p=compile_sync_coverage(main,pairs,turns,25,lambda s,*a:{'visible_voice':'a' if s['media_id']=='s' else 'b','status':'visible'})
  self.assertEqual(len(p['reactions']),1);self.assertEqual(p['reactions'][0]['end_frame']-p['reactions'][0]['start_frame'],40)
  self.assertEqual(p['audio_spine'][0]['end_frame'],150)
