import unittest,sys
from pathlib import Path
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))
from staged_dialogue import build_staged,prepare_dialogue
class Encoder:
 def encode(self,texts):
  # Equal phrases have equal unit vectors; different fixtures stay independent.
  values=[]
  for text in texts:
   row=np.zeros(64);row[sum(ord(c) for c in text)%64]=1;values.append(row)
  return np.array(values)
def source(id,texts):
 segments=[]
 for i,text in enumerate(texts):
  words=text.split();start=i*100+10
  segments.append({'text':text,'start_frame':start,'end_frame':start+len(words)*12,'words':[{'text':word,'start_frame':start+j*12,'end_frame':start+(j+1)*12} for j,word in enumerate(words)]})
 return {'media_id':id,'take_id':id+':take:1','path':'unused.mp4','duration_frames':600,'fps':25,'segments':segments}
def payload(sources,sizes,missing=False):
 beats=[{'beat_id':'b1','kind':'dialogue','character':'ALICE','text':'Prima frase completa adesso.'},{'beat_id':'b2','kind':'dialogue','character':'BOB','text':'Seconda risposta completa qui.'}]
 if missing:beats.append({'beat_id':'b3','kind':'dialogue','character':'ALICE','text':'Battuta mai registrata.'})
 p={'beats':beats,'sources':sources,'shots':[{'media_id':s['media_id'],'start_frame':0,'end_frame':600,'shot_size':sizes[i],'confidence':.9} for i,s in enumerate(sources)],'fps':25,'settings':{'minimum_shot_seconds':1.2},'directions':{'profile':'none','markers':{}}}
 prepared=prepare_dialogue(p);labels={}
 for clip in prepared['clips']:
  labels[clip['key']]={u['id']:('1/P1' if 'Prima' in u['text'] else '2/P2') for u in clip['units']}
 p.update(prepared=prepared,classifications=labels)
 return p
class CameraAvailabilityTests(unittest.TestCase):
 def run_plan(self,p):
  with patch('transcript_align.LocalSemanticEncoder',Encoder),patch('active_speaker.analyze_candidate',return_value={'status':'visible'}),patch('listening_reaction.listening_overlay',return_value=None):
   return build_staged(p)
 def test_two_singles_work_without_a_master(self):
  p=payload([source('a',['Prima frase completa adesso.']),source('b',['Seconda risposta completa qui.'])],['close','close'])
  result=self.run_plan(p)
  self.assertEqual([d['media_id'] for d in result['decisions']],['a','b'])
  self.assertEqual({d['shot_size'] for d in result['decisions']},{'close'})
  self.assertFalse(result['planning_summary']['master_available'])
 def test_one_master_preserves_a_continuous_take_without_forced_camera_changes(self):
  p=payload([source('a',['Prima frase completa adesso.','Seconda risposta completa qui.'])],['wide'])
  result=self.run_plan(p);self.assertEqual(len(result['decisions']),2)
  self.assertEqual({d['media_id'] for d in result['decisions']},{'a'})
  self.assertEqual(result['decisions'][0]['end_frame'],result['decisions'][1]['start_frame'])
 def test_single_close_sequence_is_valid_and_does_not_invent_a_wide(self):
  p=payload([source('a',['Prima frase completa adesso.','Seconda risposta completa qui.'])],['close'])
  result=self.run_plan(p);self.assertEqual({d['shot_size'] for d in result['decisions']},{'close'})
 def test_partial_master_does_not_drop_dialogue_only_available_in_a_single(self):
  p=payload([source('a',['Prima frase completa adesso.']),source('b',['Seconda risposta completa qui.'])],['wide','close'])
  result=self.run_plan(p);self.assertEqual([d['media_id'] for d in result['decisions']],['a','b'])
 def test_one_camera_keeps_a_long_silent_pause_continuous(self):
  s=source('a',['Prima frase completa adesso.','Seconda risposta completa qui.'])
  for key in ['start_frame','end_frame']:s['segments'][1][key]+=100
  for word in s['segments'][1]['words']:
   word['start_frame']+=100;word['end_frame']+=100
  result=self.run_plan(payload([s],['wide']))
  self.assertEqual(result['decisions'][0]['end_frame'],result['decisions'][1]['start_frame'])
 def test_scripted_suspension_is_not_rejected_as_an_abandoned_take(self):
  p=payload([source('a',['Prima frase completa adesso...','Seconda risposta completa qui.'])],['close'])
  p['beats'][0]['text']='Prima frase completa adesso...'
  result=self.run_plan(p);self.assertEqual(len(result['decisions']),2)
 def test_meaningful_short_final_reply_is_not_lost_to_the_minimum_shot_target(self):
  p=payload([source('a',['Prima frase completa adesso.']),source('b',['Si.'])],['close','close'])
  p['beats'][1]['text']='Si.'
  result=self.run_plan(p);self.assertEqual(len(result['decisions']),2)
  self.assertTrue(result['decisions'][1]['warnings'])
 def test_separate_camera_takes_may_be_recorded_out_of_screenplay_order(self):
  a=source('a',['Terza frase completa finale.','Prima frase completa adesso.']);b=source('b',['Seconda risposta completa qui.'])
  p=payload([a,b],['close','close']);p['beats'].append({'beat_id':'b3','kind':'dialogue','character':'ALICE','text':'Terza frase completa finale.'})
  p['prepared']=prepare_dialogue(p)
  for clip in p['prepared']['clips']:
   p['classifications'][clip['key']]={u['id']:('3/P1' if 'Terza' in u['text'] else '1/P1' if 'Prima' in u['text'] else '2/P2') for u in clip['units']}
  result=self.run_plan(p);self.assertEqual([d['media_id'] for d in result['decisions']],['a','b','a'])
  self.assertLess(result['decisions'][2]['start_frame'],result['decisions'][0]['start_frame'])
 def test_unrecorded_script_lines_are_visible_as_unmatched_not_silently_lost(self):
  p=payload([source('a',['Prima frase completa adesso.','Seconda risposta completa qui.'])],['wide'],True)
  result=self.run_plan(p);self.assertEqual(result['unmatched_beats'],['b3'])
  self.assertTrue(any(b['beat_id']=='b3' for b in result['review_beats']))
if __name__=='__main__':unittest.main()
