import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))
class CloseFirstStyleTests(unittest.TestCase):
 def test_close_beats_unknown_and_medium_even_if_recorded_much_earlier(self):
  from staged_dialogue import camera_style_score
  close=camera_style_score('close','visible',.8,100,25)
  self.assertGreater(close,camera_style_score('unknown','visible',1,1000000,25))
  self.assertGreater(close,camera_style_score('medium','visible',1,1000000,25))
  self.assertGreater(camera_style_score('wide','visible',.8,1,25,opening=True),close)
  self.assertGreater(camera_style_score('wide','visible',.8,1,25,release=True),close)
 def test_final_candidate_checks_replace_wrong_camera_profile_and_choose_verified_speaker(self):
  from staged_dialogue import verify_camera_candidates
  rows=[dict(clip_id=c,media_id=c,shot_size='close',speaker_coverage='visible',semantic=.9,matched_start_frame=i,matched_end_frame=i+30,start_frame=i,end_frame=i+30,score=10-i) for i,c in enumerate(['wrong','right'])]
  calls=[]
  def analyze(source,start,end):
   calls.append(source['media_id']);return {'status':'absent' if source['media_id']=='wrong' else 'visible'}
  checked=verify_camera_candidates(rows,{c:{'media_id':c} for c in ['wrong','right']},analyze,25)
  best=max(checked,key=lambda r:r['score']);self.assertEqual(best['media_id'],'right');self.assertEqual(best['speaker_coverage_source'],'audio_visual_interval');self.assertEqual(calls,['wrong','right'])
 def test_camera_profile_is_not_kept_as_certainty_when_final_evidence_is_unknown(self):
  from staged_dialogue import verify_camera_candidates
  row=dict(clip_id='a',media_id='a',shot_size='close',speaker_coverage='visible',semantic=.9,matched_start_frame=0,matched_end_frame=30,start_frame=0,end_frame=30,score=10)
  checked=verify_camera_candidates([row],{'a':{}},lambda *args:{'status':'unknown'},25)
  self.assertEqual(checked[0]['speaker_coverage'],'unknown')
