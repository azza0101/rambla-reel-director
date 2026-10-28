import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))
class SceneContextTests(unittest.TestCase):
 def test_rejected_generic_route_is_restored_between_agreeing_anchors(self):
  from scene_edit_jobs import fill_scene_context
  rows=[{'id':'a','start':0,'end':100},{'id':'b','start':130,'end':200},{'id':'c','start':230,'end':300}]
  routes={('clip','a'):'scene1',('clip','b'):None,('clip','c'):'scene1'}
  fill_scene_context('clip',rows,routes,25)
  self.assertEqual(routes[('clip','b')],'scene1')
 def test_scene_boundary_is_not_invented_from_nearest_anchor(self):
  from scene_edit_jobs import fill_scene_context
  rows=[{'id':'a','start':0,'end':100},{'id':'b','start':130,'end':200},{'id':'c','start':230,'end':300}]
  routes={('clip','a'):'scene1',('clip','b'):None,('clip','c'):'scene2'}
  fill_scene_context('clip',rows,routes,25)
  self.assertIsNone(routes[('clip','b')])
 def test_long_recording_break_is_not_bridged(self):
  from scene_edit_jobs import fill_scene_context
  rows=[{'id':'a','start':0,'end':100},{'id':'b','start':130,'end':200},{'id':'c','start':2000,'end':2100}]
  routes={('clip','a'):'scene1',('clip','b'):None,('clip','c'):'scene1'}
  fill_scene_context('clip',rows,routes,25)
  self.assertIsNone(routes[('clip','b')])
