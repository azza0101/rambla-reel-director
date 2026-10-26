import unittest,sys,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[2]/'worker'))
from edit_selector import pace_plan

class ReactionTests(unittest.TestCase):
 def fixture(self):
  decisions=[{'beat_id':'invite','media_id':'girl','take_id':'g','start_frame':0,'end_frame':50,'shot_size':'close','narrative_role':'tension','alternatives':[],'warnings':[]},{'beat_id':'refuse','media_id':'wide','take_id':'w','start_frame':200,'end_frame':240,'matched_start_frame':200,'matched_end_frame':240,'shot_size':'wide','narrative_role':'resolution','alternatives':[{'media_id':'close','take_id':'c','start_frame':200,'end_frame':240,'shot_size':'close','speaker_coverage':'visible','score':.8}],'warnings':[]}]
  sources=[{'media_id':m,'take_id':t,'duration_frames':300,'segments':[{'words':[{'text':'prima','start_frame':0,'end_frame':100},{'text':'risposta','start_frame':200,'end_frame':240}]}]} for m,t in [('girl','g'),('wide','w'),('close','c')]]
  audio={m:{'status':'ok','silences':[{'start_frame':100,'end_frame':200}]} for m in ['girl','wide','close']}
  shots=[{'media_id':'close','start_frame':0,'end_frame':300,'shot_size':'close','reviewed':True,'visible_subjects':['LUI']}]
  beats=[{'beat_id':'invite','kind':'dialogue','character':'LEI'},{'beat_id':'refuse','kind':'dialogue','character':'LUI'}]
  return {'decisions':decisions},sources,audio,beats,shots
 def run_plan(self,fixture):
  p,s,a,b,shots=fixture
  return pace_plan(p,s,a,b,25,{'minimum_shot_seconds':1.2},shots=shots)
 def test_inserts_verified_word_free_reaction_before_resolution_and_counts_duration(self):
  result=self.run_plan(self.fixture());reaction=result['decisions'][1]['reaction_before']
  self.assertEqual(reaction['media_id'],'close');self.assertEqual(reaction['end_frame']-reaction['start_frame'],30)
  self.assertGreaterEqual(reaction['start_frame'],100);self.assertLess(reaction['end_frame'],200)
  self.assertEqual(result['pacing_summary']['reaction_count'],1)
  self.assertEqual(result['pacing_summary']['duration_frames'],sum(d['pacing']['duration_frames'] for d in result['decisions'])+30)
 def test_missing_audio_or_unknown_visibility_never_invents_a_reaction(self):
  for mode in ['audio','visibility','words','short','take','style']:
   fixture=self.fixture();p,s,a,b,shots=fixture
   if mode=='audio':a['close']={'status':'unavailable'}
   if mode=='visibility':shots[0]['reviewed']=False
   if mode=='words':s[2]['segments'][0]['words'].append({'text':'parola','start_frame':120,'end_frame':190})
   if mode=='short':a['close']['silences']=[{'start_frame':185,'end_frame':200}]
   if mode=='take':s[2]['start_frame']=190
   if mode=='style':p['decisions'][0]['narrative_role']='free'
   result=self.run_plan(fixture)
   self.assertNotIn('reaction_before',result['decisions'][1],mode)
 def test_recalculation_is_idempotent_and_user_can_disable_the_reaction(self):
  fixture=self.fixture();first=self.run_plan(fixture);fixture=(first,*fixture[1:]);second=self.run_plan(fixture)
  self.assertEqual(first['pacing_summary']['duration_frames'],second['pacing_summary']['duration_frames'])
  second['base_decisions'][1]['reaction_enabled']=False
  third=self.run_plan((second,*fixture[1:]));self.assertNotIn('reaction_before',third['decisions'][1]);self.assertEqual(third['pacing_summary']['reaction_count'],0)

 def test_reaction_never_replays_a_silent_hold_already_retained_in_the_scene(self):
  fixture=self.fixture();p,s,a,b,shots=fixture
  p['decisions'][0].update(media_id='close',take_id='c',end_frame=100,matched_end_frame=100)
  p['decisions'][1]['alternatives'][0].update(start_frame=150,end_frame=190)
  result=self.run_plan(fixture)
  self.assertGreaterEqual(result['decisions'][0]['end_frame'],125)
  self.assertNotIn('reaction_before',result['decisions'][1])
