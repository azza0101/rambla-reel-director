import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))
class SceneRunTests(unittest.TestCase):
 def test_a_later_scene_breaks_performance_even_if_same_scene_returns(self):
  from scene_edit_jobs import scene_ranges
  rows=[{'id':str(i),'start':i*50,'end':i*50+40} for i in range(5)];routes={('c',str(i)):s for i,s in enumerate(['a',None,'a','b','a'])}
  self.assertEqual(scene_ranges('c',rows,routes,'a',25),[{'start_frame':0,'end_frame':140},{'start_frame':200,'end_frame':240}])
 def test_large_gap_separates_pickup_from_initial_performance(self):
  from scene_edit_jobs import scene_ranges
  rows=[{'id':'a','start':0,'end':100},{'id':'b','start':1000,'end':1100}];routes={('c','a'):'s',('c','b'):'s'}
  self.assertEqual(len(scene_ranges('c',rows,routes,'s',25)),2)
 def test_no_anchor_does_not_assign_the_whole_clip(self):
  from scene_edit_jobs import scene_ranges
  self.assertEqual(scene_ranges('c',[{'id':'a','start':0,'end':100}],{('c','a'):None},'s',25),[])
