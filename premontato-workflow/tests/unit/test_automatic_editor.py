import sys,unittest,copy
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[2]/'worker'))
from protocol import dispatch
class AutomaticEditorTests(unittest.TestCase):
 def request(self):
  beats=[{'beat_id':str(i),'kind':'dialogue','character':'ATTREZZO','text':t} for i,t in enumerate(['prima battuta intera','seconda battuta intera','terza battuta intera'])]
  return {'protocol':1,'request_id':'asd','action':'build_plan','payload':{'fps':25,'active_speaker':True,'beats':beats,'sources':[{'media_id':name,'take_id':name,'take_index':n,'path':name+'.mp4','fps':25,'duration_frames':500,'segments':[{'start_frame':20+i*120,'end_frame':90+i*120,'text':b['text']} for i,b in enumerate(beats)]} for n,name in enumerate(['close','wrong','wide'],1)],'shots':[{'media_id':name,'start_frame':0,'end_frame':500,'shot_size':'wide' if name=='wide' else 'close','confidence':.9,'visible_subjects':[]} for name in ['close','wrong','wide']]}}
 def runplan(self,request,fn):
  with patch('active_speaker.analyze_candidate',side_effect=fn):return dispatch(request)['result']
 def test_opens_master_then_follows_visible_speaker_without_names(self):
  calls=[]
  def analyze(s,a,b):calls.append((s['media_id'],a));return {'status':'visible' if s['media_id']=='close' else 'absent','method':'test','sampled':True}
  plan=self.runplan(self.request(),analyze)
  self.assertEqual([d['media_id'] for d in plan['decisions']],['wide','close','close'])
  self.assertEqual(plan['decisions'][1]['speaker_coverage_source'],'audio_visual')
  self.assertFalse(any(a==20 for _,a in calls));self.assertFalse(any(m=='wide' for m,_ in calls))
 def test_unknown_or_missing_model_falls_back_to_master_with_warning(self):
  def unavailable(*args):raise RuntimeError('modello assente')
  plan=self.runplan(self.request(),unavailable)
  self.assertEqual([d['media_id'] for d in plan['decisions']],['wide']*3)
  self.assertTrue(any('parlante' in w.lower() and 'modello assente' in w for w in plan['warnings']))
 def test_short_generic_line_does_not_trigger_visual_inference(self):
  req=self.request()
  for source in req['payload']['sources']:source['segments'][1]['text']='ok'
  req['payload']['beats'][1]['text']='ok';calls=[]
  def analyze(s,a,b):calls.append(a);return {'status':'unknown'}
  self.runplan(req,analyze);self.assertNotIn(140,calls)
 def test_manual_visibility_wins_over_automatic_model(self):
  req=self.request()
  for shot in req['payload']['shots']:shot.update(reviewed=True,visible_subjects=['ATTREZZO'] if shot['media_id']=='close' else ['ALTRO'])
  with patch('active_speaker.analyze_candidate') as fn:
   plan=dispatch(req)['result'];fn.assert_not_called()
  self.assertEqual(plan['decisions'][1]['media_id'],'close')
 def test_does_not_interrupt_speaker_just_because_three_tight_shots_passed(self):
  from automatic_editor import choose_automatic_pool
  wide=(1,1,{}, {},{}, {'shot_size':'wide','confidence':1});close=(1,1,{}, {},{}, {'shot_size':'close','confidence':1})
  pool=choose_automatic_pool([wide,close],{id(wide):'unknown',id(close):'visible'},'free',False,[{'shot_size':'close'}]*3)
  self.assertEqual(pool,[close])
 def test_low_quality_master_or_visible_close_cannot_displace_complete_dialogue(self):
  for poor in ['wide','close']:
   req=self.request()
   for source in req['payload']['sources']:source['segments']=[{'which':source['media_id']}]
   def hits(beat,segments,fps):
    name=segments[0]['which'];start=20+int(beat['beat_id'])*120;score=.3 if name==poor or name=='wrong' else 1
    return [{'start_frame':start,'end_frame':start+70,'score':score,'coverage':score,'text':'battuta trovata'}]
   with patch('transcript_align.complete_beat_candidates',side_effect=hits):
    plan=self.runplan(req,lambda *args:{'status':'visible','method':'test','sampled':True})
   self.assertNotIn(poor,[d['media_id'] for d in plan['decisions']])
 def test_tension_and_refusal_release_are_automatic_without_markers(self):
  req=self.request();texts=['grazie per il vostro aiuto','puoi dormire nel mio letto','no non esiste posso dormire per terra']
  req['payload']['directions']={'profile':'VIDEO COLICHE','markers':{}}
  for beat,text in zip(req['payload']['beats'],texts):beat['text']=text
  for source in req['payload']['sources']:
   for segment,text in zip(source['segments'],texts):segment['text']=text
  plan=self.runplan(req,lambda *args:{'status':'visible','method':'test','sampled':True})
  self.assertEqual([d['shot_size'] for d in plan['decisions']],['wide','close','wide'])
  self.assertEqual([d['narrative_role'] for d in plan['decisions']],['free','tension','resolution'])
if __name__=='__main__':unittest.main()
