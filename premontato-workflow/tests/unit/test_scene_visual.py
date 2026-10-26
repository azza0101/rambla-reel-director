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
