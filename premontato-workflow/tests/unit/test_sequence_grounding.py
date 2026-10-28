import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))
class SequenceGroundingTests(unittest.TestCase):
 def test_camera_window_cannot_replace_question_with_answer(self):
  from staged_dialogue import content_equivalent
  self.assertFalse(content_equivalent('Secondo te sono solo prosciutti?','Si va bene solo un prosciutto.',.70))
  self.assertFalse(content_equivalent('Che cosa vuoi fare con questo programma?','Il programma lo faremo insieme io e te.',.55))
  self.assertTrue(content_equivalent('Andiamo a cercare i migliori taglieri in Italia.','Andremo a cercare i migliori taglieri in tutta Italia.',.86))
 def test_substring_repeated_delivery_is_not_added_as_a_second_moment(self):
  from staged_dialogue import unique_moments
  rows=[{'clip_id':'a','beat':'B1','start':10,'end':90,'text':'Andremo a cercare i migliori salumieri di tutta Italia.'},{'clip_id':'a','beat':'B1','start':100,'end':130,'text':'Andremo a cercare i migliori salumieri.'},{'clip_id':'a','beat':'B1','start':140,'end':180,'text':'Poi mostreremo le loro ricette.'}]
  selected=unique_moments(rows)
  self.assertEqual([r['start'] for r in selected],[10,140])
 def test_same_field_alternative_files_are_not_different_angles(self):
  from staged_dialogue import same_field
  a={'media_id':'a','shot_size':'close','dialogue_character':'ALICE','camera_id':'c'}
  self.assertTrue(same_field(a,{**a,'media_id':'b'}))
  self.assertFalse(same_field(a,{**a,'media_id':'b','dialogue_character':'BOB'}))
  self.assertFalse(same_field(a,{**a,'shot_size':'wide'}))
 def test_overlapping_words_cannot_be_reused_when_master_is_missing(self):
  from staged_dialogue import follows_source
  self.assertFalse(follows_source([{'clip_id':'a','matched_start_frame':100,'matched_end_frame':180}],{'clip_id':'a','matched_start_frame':150,'matched_end_frame':220}))
  self.assertFalse(follows_source([{'clip_id':'a','matched_start_frame':100,'matched_end_frame':180}],{'clip_id':'a','matched_start_frame':50,'matched_end_frame':90}))
  self.assertTrue(follows_source([{'clip_id':'a','matched_start_frame':100,'matched_end_frame':180}],{'clip_id':'b','matched_start_frame':50,'matched_end_frame':90}))
class FaceRoleTests(unittest.TestCase):
 def test_single_conflicting_anchor_cannot_override_repeated_other_role(self):
  from speaker_identity import match_role
  gallery=[{'role':'A','media_id':str(i),'vector':[1,0]} for i in range(3)]+[{'role':'B','media_id':'bad','vector':[1,0]}]+[{'role':'B','media_id':str(i),'vector':[0,1]} for i in range(3)]
  self.assertEqual(match_role([1,0],gallery),'A')
  self.assertIsNone(match_role([.7,.7],gallery))
class PerformanceChoiceTests(unittest.TestCase):
 def test_last_complete_performance_wins_over_more_literal_earlier_file(self):
  from staged_dialogue import choose_performances
  sources={'old':{'name':'001.mp4','take_index':1},'new':{'name':'002.mp4','take_index':1}}
  rows=[{'id':c+str(i),'clip':c,'start':i*100,'end':i*100+50,'text':'Frase completa di dialogo.'} for c in sources for i in range(3)]
  labels={u['id']:str(i%3+1)+'/P1' for i,u in enumerate(rows)}
  selected=choose_performances(rows,labels,sources,{'old':'field-a','new':'field-a'})
  self.assertEqual(selected['allowed'],{'new0','new1','new2'})
 def test_last_incomplete_restart_does_not_replace_full_take_in_same_file(self):
  from staged_dialogue import choose_performances
  rows=[{'id':str(i),'clip':'a','start':i*100,'end':i*100+50,'text':'Frase completa qui.'} for i in range(5)]
  labels={str(i):str([1,2,3,1,2][i])+'/P1' for i in range(5)}
  selected=choose_performances(rows,labels,{'a':{'name':'a'}},{'a':'field'})
  self.assertEqual(selected['allowed'],{'0','1','2'})
class GenericFragmentTests(unittest.TestCase):
 def test_pointing_filler_does_not_precede_the_full_delivery_as_a_separate_take(self):
  from staged_dialogue import trim_generic_fragments
  rows=[{'beat':'B1','text':'Qui qui no?','start':10,'end':45},{'beat':'B1','text':'Viaggeremo in Italia per incontrare i migliori artigiani.','start':100,'end':220}]
  self.assertEqual(trim_generic_fragments(rows,{'B1':'Viaggeremo in Italia, qui e qui, per trovare i migliori artigiani.'}),[rows[1]])
 def test_short_scripted_reply_remains(self):
  from staged_dialogue import trim_generic_fragments
  row={'beat':'B1','text':'Si!','start':10,'end':30}
  self.assertEqual(trim_generic_fragments([row],{'B1':'Si!'}),[row])
class AnchorGroundingTests(unittest.TestCase):
 def test_generic_adlib_does_not_teach_the_wrong_face_role(self):
  from staged_dialogue import role_anchor_score
  self.assertEqual(role_anchor_score('Ma come che ne so?','Tu che ne sai di queste cose? Sei una biologa!',.62),0)
  self.assertGreater(role_anchor_score('Tu sei una biologa, che ne sai di queste cose?','Tu che ne sai di queste cose? Sei una biologa!',.8),0)
class PartialLatestPerformanceTests(unittest.TestCase):
 def test_short_fragment_is_missing_content_not_successful_coverage(self):
  from staged_dialogue import choose_performances
  rows=[{'id':'old','clip':'a','start':0,'end':100,'text':'Tu sei una biologa, che cosa puoi sapere di questi prodotti?'},{'id':'new','clip':'b','start':0,'end':30,'text':'Che cosa e questo?'}]
  result=choose_performances(rows,{'old':'1/P1','new':'1/P1'},{'a':{'name':'001'},'b':{'name':'002'}},{'a':'field','b':'field'})
  self.assertEqual(result['allowed'],{'old'})
class ShortRepeatedQuestionTests(unittest.TestCase):
 def test_repeated_short_question_with_one_content_word_is_kept_once(self):
  from staged_dialogue import unique_moments
  rows=[{'clip_id':'a','beat':'B1','start':10,'end':35,'text':'Ti sei vista?'},{'clip_id':'a','beat':'B1','start':60,'end':90,'text':'Ti sei vista, te?'}]
  self.assertEqual(len(unique_moments(rows)),1)
class NonDialogueNoiseTests(unittest.TestCase):
 def test_unrelated_repeated_no_is_not_a_delivery_of_a_distinctive_script_line(self):
  from staged_dialogue import trim_generic_fragments
  r={'beat':'B1','text':'No no no no no no.','start':0,'end':40}
  self.assertEqual(trim_generic_fragments([r],{'B1':'Lascia perdere questa idea.'}),[])
 def test_micro_fragment_does_not_cover_a_full_answer(self):
  from staged_dialogue import trim_generic_fragments
  r={'beat':'B1','text':'no','start':0,'end':3}
  self.assertEqual(trim_generic_fragments([r],{'B1':'No, hai ragione.'}),[])
class ContinuousGapTests(unittest.TestCase):
 def test_short_filler_can_remain_inside_a_continuous_take(self):
  from staged_dialogue import harmless_gap
  self.assertTrue(harmless_gap([{'text':'Allora,'}],60,25))
  self.assertFalse(harmless_gap([{'text':'Stop,'},{'text':'ripartiamo.'}],60,25))
  self.assertFalse(harmless_gap([{'text':'no'}]*6,60,25))
class ResolveVoiceTests(unittest.TestCase):
 def test_preparation_preserves_voice_on_single_speaker_segment(self):
  from staged_dialogue import prepare_dialogue
  source={'media_id':'m','take_id':'t','duration_frames':200,'segments':[{'speaker_name':'Voice A','words':[{'text':'Porta','start_frame':10,'end_frame':25},{'text':'aperta.','start_frame':25,'end_frame':50}]}]}
  p=prepare_dialogue({'sources':[source],'beats':[],'fps':25});u=p['clips'][0]['units'][0];self.assertEqual(u['speaker_name'],'Voice A');self.assertTrue(u['speaker_reliable'])
 def test_mixed_turn_segment_label_is_not_certified_for_each_short_sentence(self):
  from staged_dialogue import prepare_dialogue
  source={'media_id':'m','duration_frames':200,'segments':[{'speaker_name':'Voice A','words':[{'text':w,'start_frame':i*20,'end_frame':(i+1)*20} for i,w in enumerate(['Arrivi?','Certo.','Adesso?','Subito.'])]}]}
  p=prepare_dialogue({'sources':[source],'beats':[],'fps':25});self.assertTrue(all(not u['speaker_reliable'] for u in p['clips'][0]['units']))
 def test_confident_voice_mapping_is_local_to_each_source(self):
  from staged_dialogue import resolve_voice_roles
  beats=[{'text':'La chiave verde resta sotto il vaso.','character':'A'},{'text':'Il pacco azzurro parte domani mattina.','character':'B'}]
  units=[{'id':str(i),'clip':cid,'speaker_name':'Voice 1','speaker_reliable':True,'start':i*100,'text':text,'_anchor_score':1} for i,(cid,text) in enumerate([('x','La chiave verde resta sotto il vaso.'),('x','La chiave resta sotto il vaso verde.'),('y','Il pacco azzurro parte domani mattina.'),('y','Il pacco parte domani mattina.')])]
  labels={str(i):('1/P1' if i<2 else '2/P2') for i in range(4)}
  roles=resolve_voice_roles(units,labels,beats,{'P1':'A','P2':'B'});self.assertEqual(roles[('x','Voice 1')],'A');self.assertEqual(roles[('y','Voice 1')],'B')
class RoutedVoiceTests(unittest.TestCase):
 def test_scene_routing_keeps_resolve_voice_evidence(self):
  import numpy as np
  from scene_edit_jobs import route_scenes
  from staged_dialogue import prepare_dialogue
  class Encoder:
   def encode(self,texts):return np.array([[1.,0.] for _ in texts])
  source={'media_id':'m','take_id':'t','duration_frames':200,'segments':[{'speaker_name':'Voice A','words':[{'text':'Chiave','start_frame':10,'end_frame':25},{'text':'verde','start_frame':25,'end_frame':40},{'text':'nascosta.','start_frame':40,'end_frame':60}]}]}
  scene={'scene_id':'s','heading':'Scena','beats':[{'beat_id':'b','scene_id':'s','kind':'dialogue','character':'A','text':'Chiave verde nascosta.'}]}
  result=route_scenes({'scenes':[scene],'sources':[source],'fps':25},Encoder());routed=result['jobs'][0]['sources'];p=prepare_dialogue({'sources':routed,'beats':scene['beats'],'fps':25})
  self.assertEqual(p['clips'][0]['units'][0]['speaker_name'],'Voice A');self.assertTrue(p['clips'][0]['units'][0]['speaker_reliable'])
