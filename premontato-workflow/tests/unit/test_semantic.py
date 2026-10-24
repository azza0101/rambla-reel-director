import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[2]/'worker'))
from transcript_align import semantic_windows, contextual_path

class SemanticTests(unittest.TestCase):
 def test_windows_keep_word_times_and_do_not_join_silences(self):
  source={'media_id':'m','segments':[{'words':[{'text':'Puoi','start_frame':0,'end_frame':8},{'text':'restare.','start_frame':9,'end_frame':20},{'text':'Buonanotte.','start_frame':200,'end_frame':230}]}]}
  rows=semantic_windows(source,25)
  self.assertTrue(rows)
  self.assertFalse(any(r['start_frame']==0 and r['end_frame']==230 for r in rows))
 def test_context_prevents_wrong_late_short_response(self):
  rows=[[{'start_frame':10,'end_frame':20,'score':.8}], [{'start_frame':80,'end_frame':90,'score':.95},{'start_frame':21,'end_frame':29,'score':.7}], [{'start_frame':30,'end_frame':60,'score':.9}]]
  path=contextual_path(rows)
  self.assertEqual([p['start_frame'] for p in path],[10,21,30])
 def test_unrelated_dialogue_can_remain_unmatched(self):
  self.assertEqual(contextual_path([[],[]]),[None,None])

 def test_candidate_window_does_not_merge_distinct_observed_speaker_turns(self):
  source={'media_id':'m','segments':[{'speaker_name':'Voice A','words':[{'text':'Puoi','start_frame':0,'end_frame':8},{'text':'restare.','start_frame':9,'end_frame':20}]},{'speaker_name':'Voice B','words':[{'text':'Preferisco','start_frame':25,'end_frame':38},{'text':'andare.','start_frame':39,'end_frame':52}]}]}
  rows=semantic_windows(source,25)
  self.assertFalse(any(r['start_frame']==0 and r['end_frame']==52 for r in rows))
 def test_sentence_completion_crosses_a_dramatic_pause_but_never_next_line(self):
  from transcript_align import extend_utterance_end
  hit={'start_frame':0,'end_frame':40,'text':'Puoi restare.'}
  words=[{'text':'Puoi','start_frame':0,'end_frame':10},{'text':'restare.','start_frame':11,'end_frame':40},{'text':'Dormiremo','start_frame':73,'end_frame':85},{'text':'insieme.','start_frame':86,'end_frame':100},{'text':'No.','start_frame':130,'end_frame':145}]
  extended=extend_utterance_end(hit,words,120,25)
  self.assertEqual(extended['end_frame'],100);self.assertIn('insieme.',extended['text']);self.assertNotIn('No.',extended['text'])

 def test_short_next_line_opener_is_not_appended_to_previous_complete_sentence(self):
  from transcript_align import is_next_line_opener
  self.assertTrue(is_next_line_opener('Marco!',{'text':'Marco. Che succede?'}))
  self.assertFalse(is_next_line_opener('Alberto!',{'text':'Marco. Che succede?'}))
  self.assertFalse(is_next_line_opener('Va tutto bene.',{'text':'Marco. Che succede?'}))

 def test_high_semantic_similarity_does_not_hide_low_textual_coverage(self):
  from unittest.mock import patch
  from protocol import dispatch
  hit={'start_frame':20,'end_frame':80,'text':'Guarda il ragazzo, lo aiuto io.','score':.86,'semantic_score':.9,'coverage':.3}
  payload={'fps':25,'semantic':True,'beats':[{'beat_id':'b','kind':'dialogue','character':'LUCA','text':'Va bene, ma che significa? Guarda il ragazzo, lo aiuto io.'}],'sources':[{'media_id':'m','take_id':'t','take_index':1,'duration_frames':200,'segments':[]}],'shots':[]}
  with patch('transcript_align.semantic_scene_hits',return_value={('t','b'):[hit]}):
   decision=dispatch({'protocol':1,'request_id':'coverage','action':'build_plan','payload':payload})['result']['decisions'][0]
  self.assertTrue(any('completezza' in w for w in decision['warnings']))

 def test_sentence_extension_cannot_restore_rejected_opener_when_next_line_unmatched(self):
  import numpy as np
  from unittest.mock import patch
  from transcript_align import semantic_scene_hits
  first='Ti prego vieni qui e resta con me stanotte.';following='Marco. Che cosa hai deciso di fare domani?'
  class Encoder:
   def encode(self,texts): return np.array([[0.,1.] if t==following else [.2,0.] if t=='Marco.' else [1.,0.] for t in texts])
  beats=[{'beat_id':'a','kind':'dialogue','text':first},{'beat_id':'b','kind':'dialogue','text':following}]
  sources=[{'media_id':'m','take_id':'t','segments':[{'start_frame':0,'words':[{'text':first,'start_frame':0,'end_frame':35},{'text':'Marco.','start_frame':70,'end_frame':80}]}]}]
  with patch('transcript_align._SEMANTIC_ENCODER',Encoder()): result=semantic_scene_hits(beats,sources,25)
  self.assertNotIn(('t','b'),result);self.assertEqual(result[('t','a')][0]['end_frame'],35);self.assertNotIn('Marco',result[('t','a')][0]['text'])
