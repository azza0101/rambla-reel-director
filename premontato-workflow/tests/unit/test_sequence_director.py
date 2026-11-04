import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))


def shot(mid,start,end,ids,field='a:close',visible=True,similarity=1.):
 return {'media_id':mid,'start_frame':start,'end_frame':end,'ids':ids,'field':field,'voice':'a','speaker_visible':visible,'similarity':similarity}


class SequenceDirectorTests(unittest.TestCase):
 def test_context_can_disambiguate_a_reordered_short_question(self):
  from sequence_director import contextual_question_match
  self.assertTrue(contextual_question_match("E questo che cos'è?","Che cos'è questo?",.80,.91))
 def test_context_does_not_make_a_different_question_equivalent(self):
  from sequence_director import contextual_question_match
  self.assertFalse(contextual_question_match("E questo che cos'è?","Questo è buono?",.88,.95))
 def test_short_question_requires_context_and_preserves_negation(self):
  from sequence_director import contextual_question_match
  self.assertFalse(contextual_question_match("E questo che cos'è?","Che cos'è questo?",.80,.5))
  self.assertFalse(contextual_question_match("E questo non è buono?","E questo è buono?",.95,.95))
 def test_generic_repeated_answers_are_not_repaired_by_question_rule(self):
  from sequence_director import contextual_question_match
  self.assertFalse(contextual_question_match("Un altro prosciutto.","Un altro prosciutto.",.99,.99))
 def test_last_good_take_wins_over_small_literal_similarity_gain(self):
  from sequence_director import select_sequence
  rows=[[shot('old',0,50,['q'],similarity=1.),shot('new',100,150,['q'],similarity=.91)]]
  p=select_sequence(rows,{'a:close':'new'},25)
  self.assertEqual(p['decisions'][0]['media_id'],'new')
 def test_lookahead_avoids_same_field_take_jump(self):
  from sequence_director import select_sequence
  rows=[[shot('old',0,50,['q'],similarity=1.),shot('new',100,150,['q'],similarity=.95)],[shot('new',150,200,['r'])]]
  p=select_sequence(rows,{},25)
  self.assertEqual([x['media_id'] for x in p['decisions']],['new','new'])
 def test_source_order_is_preserved_across_an_intervening_camera(self):
  from sequence_director import select_sequence
  rows=[[shot('a',100,150,['q'])],[shot('b',0,50,['r'],field='b:close')],[shot('a',80,100,['s']),shot('a',150,200,['s'])]]
  p=select_sequence(rows,{},25)
  self.assertEqual(p['decisions'][-1]['start_frame'],150)
 def test_unknown_voice_cannot_be_certified_by_just_selecting_an_alternative(self):
  from sequence_director import select_sequence
  x=shot('a',0,50,['q'],visible=False);x['voice']=None
  p=select_sequence([[x]],{},25)
  self.assertFalse(p['editorial_ready']);self.assertEqual(p['unresolved_ids'],['q'])
 def test_repeated_gag_answer_ids_are_retained_without_deduplication(self):
  from sequence_director import select_sequence
  p=select_sequence([[shot('a',0,50,['answer1'])],[shot('b',0,50,['question2'],field='b')],[shot('a',50,100,['answer2'])]],{},25)
  self.assertEqual([u for d in p['decisions'] for u in d['ids']],['answer1','question2','answer2'])
 def test_mismatched_alternative_event_ids_are_rejected(self):
  from sequence_director import select_sequence
  with self.assertRaises(ValueError):select_sequence([[shot('a',0,50,['q']),shot('b',0,50,['invented'])]],{},25)
 def test_no_legal_path_does_not_drop_the_problematic_turn(self):
  from sequence_director import select_sequence
  with self.assertRaises(ValueError):select_sequence([[shot('a',100,150,['q'])],[shot('a',0,50,['r'])]],{},25)
 def test_exposed_splice_is_reported_when_no_covering_field_exists(self):
  from sequence_director import select_sequence
  p=select_sequence([[shot('a',0,50,['q'])],[shot('b',0,50,['r'])]],{},25)
  self.assertEqual(p['exposed_splice_positions'],[50]);self.assertFalse(p['editorial_ready'])
 def test_verified_speaker_beats_a_contiguous_but_unverified_source(self):
  from sequence_director import select_sequence
  p=select_sequence([[shot('a',0,50,['q'])],[shot('a',50,100,['r'],visible=False),shot('b',100,150,['r'],field='b:close')]],{},25)
  self.assertEqual(p['decisions'][-1]['media_id'],'b')
