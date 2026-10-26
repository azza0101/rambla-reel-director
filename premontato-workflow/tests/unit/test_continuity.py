import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[2]/'worker'))
from edit_selector import pace_plan

class ContinuityTests(unittest.TestCase):
 def source(self):return {'media_id':'m','take_id':'t','duration_frames':600,'start_frame':0,'end_frame':600,'segments':[{'words':[{'text':'uno','start_frame':10,'end_frame':45},{'text':'due','start_frame':120,'end_frame':150}]}]}
 def decision(self,beat,start,end):return {'beat_id':beat,'media_id':'m','take_id':'t','shot_size':'wide','start_frame':start,'end_frame':end,'matched_start_frame':start,'matched_end_frame':end,'alternatives':[]}
 def test_internal_silence_keeps_a_continuous_angle(self):
  out=pace_plan({'decisions':[self.decision('a',0,160)]},[self.source()],{'m':{'status':'ok','silences':[{'start_frame':45,'end_frame':120}]}},[],25,{})
  self.assertEqual(out['decisions'][0]['source_ranges'],[{'start_frame':0,'end_frame':160}])
 def test_consecutive_master_lines_preserve_the_source_gap(self):
  out=pace_plan({'decisions':[self.decision('a',0,50),self.decision('b',110,160)]},[self.source()],{},[],25,{})
  self.assertEqual(out['decisions'][0]['end_frame'],out['decisions'][1]['start_frame'])
 def test_backwards_same_angle_is_rejected_instead_of_a_jump(self):
  with self.assertRaisesRegex(ValueError,'[Cc]ontinuit'):
   pace_plan({'decisions':[self.decision('a',110,160),self.decision('b',0,50)]},[self.source()],{},[],25,{})
 def test_script_action_uses_shared_wide_coverage_between_lines(self):
  left=self.decision('a',0,50);right={**self.decision('b',210,250),'media_id':'other','take_id':'other','shot_size':'close','alternatives':[self.decision('b',200,250)]}
  beats=[{'beat_id':'a','kind':'dialogue'},{'beat_id':'movement','kind':'action','text':'Lei esce e lui si avvicina'},{'beat_id':'b','kind':'dialogue'}]
  out=pace_plan({'decisions':[left,right]},[self.source(),{'media_id':'other','take_id':'other','duration_frames':600,'segments':[]}],{},beats,25,{})
  action=out['decisions'][0]['action_after'][0];self.assertEqual((action['start_frame'],action['end_frame']),(50,200));self.assertEqual(action['beat_id'],'movement')
  self.assertEqual(out['pacing_summary']['duration_frames'],240)
 def test_pause_directive_is_not_a_separate_action_clip(self):
  out=pace_plan({'decisions':[self.decision('a',0,50),self.decision('b',110,160)]},[self.source()],{},[{'beat_id':'a','kind':'dialogue'},{'beat_id':'p','kind':'action','text':'Pausa'},{'beat_id':'b','kind':'dialogue'}],25,{})
  self.assertFalse(out['decisions'][0].get('action_after'))

 def test_manual_bounds_are_not_extended_to_hide_a_jump(self):
  left=self.decision('a',0,50);left['manual']=True
  with self.assertRaisesRegex(ValueError,'[Cc]ontinuit'):
   pace_plan({'decisions':[left,self.decision('b',110,160)]},[self.source()],{},[],25,{})

 def test_action_stops_before_the_next_lines_opening_words_on_an_alternate_take(self):
  source=self.source();source['segments'][0]['words']=[{'text':'Tu','start_frame':190,'end_frame':200},{'text':'sei','start_frame':200,'end_frame':210}]
  left=self.decision('a',0,50);right={**self.decision('b',210,250),'media_id':'other','take_id':'other','shot_size':'close','alternatives':[self.decision('b',200,250)]}
  beats=[{'beat_id':'a','kind':'dialogue'},{'beat_id':'exit','kind':'action','text':'Lei esce'},{'beat_id':'b','kind':'dialogue'}]
  out=pace_plan({'decisions':[left,right]},[source,{'media_id':'other','take_id':'other','duration_frames':600,'segments':[]}],{},beats,25,{})
  self.assertEqual(out['decisions'][0]['action_after'][0]['end_frame'],190)
