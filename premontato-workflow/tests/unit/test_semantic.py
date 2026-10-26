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

 def test_partial_restart_does_not_continue_through_an_aborted_sentence(self):
  source={'media_id':'m','segments':[{'start_frame':0,'words':[{'text':'Potrei aiutarti ma...','start_frame':0,'end_frame':30},{'text':'Rifacciamo da capo.','start_frame':31,'end_frame':60}]}]}
  self.assertFalse(any(r['start_frame']==0 and r['end_frame']==60 for r in semantic_windows(source,25)))

 def test_complete_opening_wins_over_a_stronger_truncated_repetition(self):
  import numpy as np
  from unittest.mock import patch
  from transcript_align import semantic_scene_hits, opening_anchor
  text='Va bene, ma cosa significa? Guarda quel ragazzo, gli ho promesso di aiutarlo e questa sera manterrò la promessa.'
  head='Va bene, ma cosa significa?';tail='Guarda quel ragazzo, gli ho promesso di aiutarlo e questa sera manterrò la promessa.'
  class Encoder:
   def encode(self,texts):
    return np.array([[0.,1.] if t==opening_anchor({'text':text}) else [.92,.1] if t==tail else [.1,.9] if t==head else [1.,0.] if t==text else [.8,.8] for t in texts])
  sources=[{'media_id':'complete','take_id':'earlier','segments':[{'start_frame':0,'words':[{'text':head,'start_frame':0,'end_frame':40},{'text':tail,'start_frame':41,'end_frame':100}]}]}, {'media_id':'partial','take_id':'later','segments':[{'start_frame':0,'words':[{'text':tail,'start_frame':0,'end_frame':60}]}]}]
  with patch('transcript_align._SEMANTIC_ENCODER',Encoder()): hits=semantic_scene_hits([{'beat_id':'b','kind':'dialogue','text':text}],sources,25)
  self.assertIn(('earlier','b'),hits);self.assertNotIn(('later','b'),hits)

 def test_complete_opening_expands_to_an_equivalent_validated_candidate_without_crossing_previous_line(self):
  from transcript_align import prefer_complete_opening
  hit={'start_frame':50,'end_frame':150,'score':.8,'opening_checked':True,'text':'Continuiamo il discorso.'}
  full={**hit,'start_frame':10,'score':.75,'text':'Va bene, ma che significa? Continuiamo il discorso.'}
  self.assertEqual(prefer_complete_opening(hit,[full,hit],0)['start_frame'],10)
  self.assertEqual(prefer_complete_opening(hit,[full,hit],30)['start_frame'],50)

 def test_opening_anchor_requires_specific_words_not_only_a_generic_semantic_match(self):
  from transcript_align import opening_words_overlap
  self.assertGreaterEqual(opening_words_overlap('Eeeh va bene! Ma che significa?','Eh, va bene, ma cosa significa?'),2)
  self.assertEqual(opening_words_overlap('Eeeh va bene! Ma che significa?','Passa, passata.'),0)

 def test_dialogue_handles_never_include_words_of_adjacent_lines(self):
  from transcript_align import safe_dialogue_handles
  source={'duration_frames':250,'segments':[{'words':[{'text':'prima','start_frame':80,'end_frame':99},{'text':'battuta','start_frame':100,'end_frame':150},{'text':'dopo','start_frame':153,'end_frame':180}]}]}
  self.assertEqual(safe_dialogue_handles({'start_frame':100,'end_frame':150},source,25),(99,153))

 def test_next_line_ownership_needs_specific_content_not_a_generic_question(self):
  from transcript_align import fragment_supports_line
  beat={'text':"Non ho capito, ti immoli con l'ingegnere?"}
  self.assertTrue(fragment_supports_line("No, capito, dimmoli con l'ingegnere.",beat))
  self.assertFalse(fragment_supports_line('Butti su questa cosa, dai.',beat))
