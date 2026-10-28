import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))
class VideoReaderTests(unittest.TestCase):
 def test_preroll_bias_is_calibrated(self):
  from video_reader import index_bias,check_timestamp
  self.assertEqual(index_bias(-1000,1/25000,0,25),1)
  self.assertAlmostEqual(check_timestamp(1000,1/25000,0,1,25),0)
  with self.assertRaises(ValueError):check_timestamp(2000,1/25000,0,1,25)
 def test_batch_bounds_never_exceed_source(self):
  from video_reader import batch_indices
  self.assertEqual(batch_indices(92,100,10,8,1),[92])
  self.assertEqual(batch_indices(0,500,50,3,0),[0,50,100])
 def test_gpu_failure_keeps_original_decoder_available(self):
  from video_reader import read_asd_video
  with patch('video_reader.get_reader',side_effect=RuntimeError('no GPU')):
   self.assertIsNone(read_asd_video({'path':'fake','fps':25,'duration_frames':100},0,1))
 def test_non_25fps_speaker_uses_original_resampling(self):
  from video_reader import read_asd_video
  with patch('video_reader.get_reader') as reader:
   self.assertIsNone(read_asd_video({'path':'fake','fps':50,'duration_frames':100},0,1));reader.assert_not_called()
class ReaderFrameTests(unittest.TestCase):
 def test_batch_requests_compensate_preroll_and_validate_each_frame(self):
  import numpy as np
  from video_reader import Reader
  class Frame:
   def __init__(self,index):self.timestamp=index*1000;self.array=np.array([[[1,2,3]]],dtype=np.uint8)
   def __dlpack__(self,*args,**kwargs):return self.array.__dlpack__(*args,**kwargs)
   def __dlpack_device__(self):return self.array.__dlpack_device__()
  class Decoder:
   def get_batch_frames_by_index(self,indices):self.indices=indices;return [Frame(i-1) for i in indices]
  r=Reader.__new__(Reader);r.decoder=Decoder();r.count=200;r.bias=1;r.fps=25;r.tb=1/25000;r.origin=0;r.timestamp_checks=0
  images=r.frames([0,50,100]);self.assertEqual(r.decoder.indices,[1,51,101]);self.assertEqual(r.timestamp_checks,3);self.assertEqual(images[0].tolist(),[[[3,2,1]]])
class ReaderWindowBoundsTests(unittest.TestCase):
 def test_preroll_cannot_seek_window_past_native_eof(self):
  from video_reader import Reader
  from unittest.mock import Mock
  r=Reader.__new__(Reader);r.count=100;r.native_count=100;r.bias=1;r.decoder=Mock()
  with self.assertRaises(ValueError):r.window(50,50)
  r.decoder.seek_to_index.assert_not_called()
 def test_negative_native_index_rejected_before_seek(self):
  from video_reader import Reader
  from unittest.mock import Mock
  r=Reader.__new__(Reader);r.count=100;r.native_count=100;r.bias=-1;r.decoder=Mock()
  with self.assertRaises(ValueError):r.window(0,10)
  r.decoder.seek_to_index.assert_not_called()
 def test_resolve_count_cannot_override_shorter_native_stream(self):
  from video_reader import Reader
  from unittest.mock import Mock
  r=Reader.__new__(Reader);r.count=120;r.native_count=100;r.bias=0;r.decoder=Mock()
  with self.assertRaises(ValueError):r.frames([110])
  r.decoder.get_batch_frames_by_index.assert_not_called()
