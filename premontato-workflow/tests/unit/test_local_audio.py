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
   self.assertIsInstance(second,np.memmap);self.assertFalse(second.flags.writeable)
   from asd_features import mfcc
   np.testing.assert_array_equal(mfcc(second[1000:9000]),mfcc(first[1000:9000]))
   second._mmap.close()
   write(200);changed,meta=load_pcm16(source);self.assertFalse(meta['cache_hit']);self.assertEqual(int(changed[0]),200)

 def test_rejected_mappings_close_before_atomic_cache_replacement(self):
  invalid=[np.zeros(16000,dtype=np.float32),np.zeros((1,16000),dtype='<i2'),np.zeros(0,dtype='<i2'),np.zeros(32001,dtype='<i2')]
  for bad in invalid:
   with self.subTest(shape=bad.shape,dtype=bad.dtype),tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'PREMONTATO_CACHE_DIR':folder}):
    source_file=Path(folder)/'source.wav';source_file.write_bytes(b'fixture')
    source={'path':str(source_file),'duration_frames':25,'fps':25}
    samples=np.arange(16000,dtype='<i2')
    from types import SimpleNamespace
    result=SimpleNamespace(returncode=0,stdout=samples.tobytes())
    with patch('local_audio.ffmpeg_path',return_value='ffmpeg'),patch('local_audio.subprocess.run',return_value=result) as decode:
     load_pcm16(source)
     target=next((Path(folder)/'audio-pcm').glob('*.npy'));np.save(target,bad,allow_pickle=False)
     mappings=[];real_load=np.load;real_replace=os.replace
     def tracked_load(*args,**kwargs):
      value=real_load(*args,**kwargs)
      if isinstance(value,np.memmap):mappings.append(value)
      return value
     def checked_replace(*args,**kwargs):
      self.assertTrue(mappings,'cache must be opened without a full PCM allocation')
      self.assertTrue(all(value._mmap.closed for value in mappings),'Windows cannot replace an open mapping')
      return real_replace(*args,**kwargs)
     with patch('local_audio.np.load',side_effect=tracked_load),patch('local_audio.os.replace',side_effect=checked_replace):
      repaired,metadata=load_pcm16(source)
     self.assertFalse(metadata['cache_hit']);np.testing.assert_array_equal(repaired,samples)
     reused,metadata=load_pcm16(source)
     self.assertTrue(metadata['cache_hit']);np.testing.assert_array_equal(reused,samples)
     reused._mmap.close();self.assertEqual(decode.call_count,2)

 def test_truncated_cache_is_redecoded_without_changing_samples(self):
  with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'PREMONTATO_CACHE_DIR':folder}):
   source_file=Path(folder)/'source.wav';source_file.write_bytes(b'fixture')
   source={'path':str(source_file),'duration_frames':25,'fps':25};samples=np.arange(16000,dtype='<i2')
   from types import SimpleNamespace
   with patch('local_audio.ffmpeg_path',return_value='ffmpeg'),patch('local_audio.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=samples.tobytes())) as decode:
    load_pcm16(source);target=next((Path(folder)/'audio-pcm').glob('*.npy'))
    target.write_bytes(target.read_bytes()[:-2])
    repaired,metadata=load_pcm16(source)
    self.assertFalse(metadata['cache_hit']);np.testing.assert_array_equal(repaired,samples);self.assertEqual(decode.call_count,2)
if __name__=='__main__':unittest.main()
