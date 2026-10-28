import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))
class PerformanceSpineTests(unittest.TestCase):
 def test_omissions_preserve_every_word_between_retained_units(self):
  from performance_spine import compile_spine
  units=[{'id':'S0','start':10,'end':30,'text':'Prima.'},{'id':'S1','start':35,'end':45,'text':'E poi.'},{'id':'S2','start':50,'end':70,'text':'Regia.'},{'id':'S3','start':90,'end':150,'text':'Fine.'}]
  result=compile_spine(units,{'omit':['S2'],'missing':[]},200,25)
  self.assertEqual([(b['start_frame'],b['end_frame']) for b in result['blocks']],[(6,50),(86,158)])
  self.assertEqual(result['kept_ids'],['S0','S1','S3'])
 def test_unknown_ids_fail_instead_of_silently_dropping_words(self):
  from performance_spine import compile_spine
  with self.assertRaises(ValueError):compile_spine([{'id':'S0','start':10,'end':50,'text':'Si.'}],{'omit':['S99'],'missing':[]},100,25)
 def test_handles_never_cross_omitted_speech(self):
  from performance_spine import compile_spine
  us=[{'id':'S0','start':10,'end':30,'text':'A'},{'id':'S1','start':31,'end':34,'text':'Regia'},{'id':'S2','start':35,'end':60,'text':'B'}]
  b=compile_spine(us,{'omit':['S1'],'missing':[]},80,25)['blocks']
  self.assertLessEqual(b[0]['end_frame'],31);self.assertGreaterEqual(b[1]['start_frame'],34)
 def test_contiguous_model_blocks_merge_without_extra_cuts(self):
  from performance_spine import validate_ranges
  us=[{'id':'S0','start':0,'end':20},{'id':'S1','start':22,'end':50}]
  self.assertEqual(validate_ranges(us,[{'first':'S0','last':'S0'},{'first':'S1','last':'S1'}]),[{'first':'S0','last':'S1'}])
 def test_overlapping_model_ranges_rejected(self):
  from performance_spine import validate_ranges
  us=[{'id':'S0','start':0,'end':20},{'id':'S1','start':22,'end':50}]
  with self.assertRaises(ValueError):validate_ranges(us,[{'first':'S0','last':'S1'},{'first':'S1','last':'S1'}])
if __name__=='__main__':unittest.main()
