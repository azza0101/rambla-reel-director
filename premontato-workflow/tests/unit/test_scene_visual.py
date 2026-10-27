import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))
try:
 from scene_visual import sample_indices, rank_visual_scenes, scene_queries
except ImportError:
 sample_indices=rank_visual_scenes=scene_queries=None
class VisualCatalogTest(unittest.TestCase):
 def test_visual_catalog_is_available(self): self.assertTrue(callable(rank_visual_scenes),'visual catalog must rank images against script actions')
 def test_sampling_is_bounded_and_covers_end(self):
  self.assertTrue(callable(sample_indices));ids=sample_indices(2500,25,5,12);self.assertLessEqual(len(ids),12);self.assertEqual(ids[0],0);self.assertEqual(ids[-1],2499);self.assertEqual(len(ids),len(set(ids)))
 def test_queries_include_actions_not_only_dialogue(self):
  self.assertTrue(callable(scene_queries));q=scene_queries([{'scene_id':'a','heading':'SCENA 1 ESTERNO','beats':[{'kind':'action','text':'Un uomo bussa alla serranda chiusa.'},{'kind':'dialogue','text':'Aprimi!'}]}]);self.assertIn('serranda',q[0]['text']);self.assertEqual(q[0]['scene_id'],'a')
 def test_consistent_visual_evidence_assigns_but_ties_abstain(self):
  self.assertTrue(callable(rank_visual_scenes));q=[{'scene_id':'a','text':'porta'},{'scene_id':'b','text':'mare'}];r=rank_visual_scenes(q,[[1,0],[0,1]],[[.95,.05],[.94,.06]], [0,125]);self.assertEqual(r['scene_id'],'a');self.assertEqual(r['basis'],'visual');self.assertEqual(r['evidence'][0]['frame'],0);self.assertIsNone(rank_visual_scenes(q,[[1,0],[1,0]],[[1,0]],[0])['scene_id'])
 def test_unrelated_frames_remain_unassigned(self):
  self.assertTrue(callable(rank_visual_scenes));self.assertIsNone(rank_visual_scenes([{'scene_id':'a'}],[[1,0]],[[0,1]],[0])['scene_id'])

class VisualQueryDetailTest(unittest.TestCase):
 def test_separate_actions_are_retrieved_independently(self):
  q=scene_queries([{'scene_id':'s','heading':'ESTERNO','beats':[{'kind':'action','text':'Una donna arriva davanti alla serranda. Bussa tre volte sulla lamiera. Entra nel negozio.'}]}]);self.assertGreaterEqual(len(q),3);self.assertTrue(any('Bussa' in x['text'] and 'Entra' not in x['text'] for x in q))

class VisualRoleTest(unittest.TestCase):
 def test_queries_separate_broll_from_people_and_actions(self):
  from scene_visual import role_queries
  q=role_queries();self.assertTrue(any(r['role']=='broll' for r in q));self.assertTrue(any(r['role']=='action' for r in q));self.assertTrue(any(r['role']=='dialogue' for r in q))
 def test_pure_detail_is_broll_but_mixed_action_is_not(self):
  from scene_visual import rank_visual_role
  q=[{'role':'broll'},{'role':'action'},{'role':'dialogue'}];v=[[1,0,0],[0,1,0],[0,0,1]]
  self.assertEqual(rank_visual_role(q,v,[[1,0,0],[1,0,0]])['category'],'broll')
  self.assertIsNone(rank_visual_role(q,v,[[1,0,0],[0,1,0],[0,1,0]])['category'])

class VisualSettingTest(unittest.TestCase):
 def test_single_concrete_action_is_not_a_generic_setting(self):
  q=scene_queries([{'scene_id':'s','heading':'ESTERNO','beats':[{'kind':'action','text':'Un uomo apre la porta e fa entrare una donna.'}]}]);self.assertEqual(q[0]['specificity'],'action')
 def test_setting_description_is_weaker_than_dialogue(self):
  q=scene_queries([{'scene_id':'s','heading':'INT NEGOZIO','beats':[{'kind':'action','text':"Lui e lei sono all'interno di un negozio."}]}]);self.assertEqual(q[0]['specificity'],'setting')

class VisualUninformativeTest(unittest.TestCase):
 def test_uninformative_frame_does_not_veto_a_clear_detail(self):
  from scene_visual import rank_visual_role
  q=[{'role':'broll'},{'role':'action'},{'role':'dialogue'}]
  self.assertEqual(rank_visual_role(q,[[1,0,0],[0,1,0],[0,0,1]],[[1,0,0],[0,0,0]])['category'],'broll')

class VisualNeighborTest(unittest.TestCase):
 def test_neighbor_matching_needs_images_not_only_file_proximity(self):
  from scene_visual import rank_visual_neighbors
  refs=[{'media_id':'a','scene_id':'scene-a','side':'after','vectors':[[1,0]]},{'media_id':'b','scene_id':'scene-b','side':'before','vectors':[[0,1]]}]
  self.assertEqual(rank_visual_neighbors([[1,0],[.99,.01]],refs)['scene_id'],'scene-a')
  self.assertIsNone(rank_visual_neighbors([[1,1]],refs)['scene_id'])
 def test_neighbor_matching_abstains_on_unrelated_images(self):
  from scene_visual import rank_visual_neighbors
  self.assertIsNone(rank_visual_neighbors([[0,1]],[{'media_id':'a','scene_id':'s','vectors':[[1,0]]}])['scene_id'])

class NarrativeContextTest(unittest.TestCase):
 def test_closeup_keeps_nearby_action_scene_with_joint_evidence(self):
  from scene_visual import rank_narrative_context
  visual={'candidates':[{'scene_id':'other','score':.35},{'scene_id':'s','score':.349}]}
  role={'category':'broll','roles':['broll','dialogue','broll']}
  refs=[{'media_id':'r','scene_id':'s','distance':2,'basis':'visual_action','vectors':[[1,0]]}]
  r=rank_narrative_context(visual,role,[[.52,.854],[.51,.86],[.48,.877]],refs)
  self.assertEqual(r['scene_id'],'s');self.assertEqual(r['strength'],'narrative_context')
 def test_nearness_alone_and_pure_detail_never_assign(self):
  from scene_visual import rank_narrative_context
  visual={'candidates':[{'scene_id':'s','score':.35}]};refs=[{'media_id':'r','scene_id':'s','distance':2,'basis':'visual_action','vectors':[[1,0]]}]
  self.assertIsNone(rank_narrative_context(visual,{'roles':['broll','broll']},[[.52,.854]],refs)['scene_id'])
  self.assertIsNone(rank_narrative_context(visual,{'roles':['dialogue']},[[0,1]],refs)['scene_id'])
  refs[0]['distance']=10
  self.assertIsNone(rank_narrative_context(visual,{'roles':['dialogue']},[[.52,.854]],refs)['scene_id'])
 def test_conflicting_visual_scene_and_equal_neighbor_evidence_abstain(self):
  from scene_visual import rank_narrative_context
  role={'roles':['dialogue']};refs=[{'media_id':'r','scene_id':'s','distance':2,'basis':'visual_action','vectors':[[1,0]]}]
  self.assertIsNone(rank_narrative_context({'candidates':[{'scene_id':'other','score':.5},{'scene_id':'s','score':.31}]},role,[[.52,.854]],refs)['scene_id'])
  refs.append({'media_id':'b','scene_id':'other','distance':1,'basis':'strong_speech','vectors':[[1,0]]})
  self.assertIsNone(rank_narrative_context({'candidates':[{'scene_id':'s','score':.35}]},role,[[.52,.854]],refs)['scene_id'])
