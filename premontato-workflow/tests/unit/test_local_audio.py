import unittest,sys,tempfile,wave,os
from pathlib import Path
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).parents[2]/'worker'))
from local_audio import load_pcm16
class LocalAudioTests(unittest.TestCase):
 def test_reuses_exact_pcm_and_invalidates_on_changed_source(self):
  with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'PREMONTATO_CACHE_DIR':folder}):
   file=Path(folder)/'source.wav'
   def write(value):
    with wave.open(str(file),'wb') as wav:wav.setparams((1,2,16000,0,'NONE','not compressed'));wav.writeframes(np.full(16000,value,dtype='<i2').tobytes())
   source={'path':str(file),'duration_frames':25,'fps':25};write(100)
   first,meta=load_pcm16(source);self.assertFalse(meta['cache_hit']);self.assertEqual(first.dtype,np.int16);np.testing.assert_array_equal(first,np.full(16000,100,dtype=np.int16))
   with patch('subprocess.run',side_effect=AssertionError('must not decode again')):second,meta=load_pcm16(source)
   self.assertTrue(meta['cache_hit']);np.testing.assert_array_equal(second,first)
   write(200);changed,meta=load_pcm16(source);self.assertFalse(meta['cache_hit']);self.assertEqual(int(changed[0]),200)
if __name__=='__main__':unittest.main()
