import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[2]/'worker'))
import shot_analyzer

class Capture:
 def __init__(self,opened=True,mode=2):self.opened=opened;self.mode=mode;self.released=False
 def isOpened(self):return self.opened
 def get(self,key):return self.mode
 def release(self):self.released=True

class VideoCaptureTests(unittest.TestCase):
 def test_windows_requests_existing_hardware_decoder_and_reports_actual_mode(self):
  calls=[];cap=Capture();cv=type('CV',(),{'CAP_FFMPEG':1900,'CAP_PROP_HW_ACCELERATION':50,'VIDEO_ACCELERATION_ANY':1,'VIDEO_ACCELERATION_NONE':0,'VIDEO_ACCELERATION_D3D11':2})()
  cv.VideoCapture=lambda *args:(calls.append(args) or cap)
  with patch.object(sys,'platform','win32'):result,backend=shot_analyzer.open_video_capture(cv,'clip.mp4')
  self.assertIs(result,cap);self.assertEqual(backend,'D3D11');self.assertEqual(calls,[('clip.mp4',1900,[50,1])])
 def test_a_rejected_hardware_open_is_released_before_cpu_fallback(self):
  bad,good=Capture(False),Capture(mode=0);calls=[];cv=type('CV',(),{'CAP_FFMPEG':1900,'CAP_PROP_HW_ACCELERATION':50,'VIDEO_ACCELERATION_ANY':1,'VIDEO_ACCELERATION_NONE':0,'VIDEO_ACCELERATION_D3D11':2})()
  cv.VideoCapture=lambda *args:(calls.append(args) or (bad if len(args)>1 else good))
  with patch.object(sys,'platform','win32'):result,backend=shot_analyzer.open_video_capture(cv,'clip.mp4')
  self.assertTrue(bad.released);self.assertIs(result,good);self.assertEqual(backend,'CPU');self.assertEqual(len(calls),2)
 def test_an_unsupported_signature_uses_cpu_without_changing_other_platforms(self):
  cap=Capture(mode=0);calls=[];cv=type('CV',(),{'CAP_FFMPEG':1900,'CAP_PROP_HW_ACCELERATION':50,'VIDEO_ACCELERATION_ANY':1})()
  def open_capture(*args):
   calls.append(args)
   if len(args)>1:raise RuntimeError('Unsupported decoder')
   return cap
  cv.VideoCapture=open_capture
  for platform in ['win32','linux']:
   calls.clear()
   with patch.object(sys,'platform',platform):result,backend=shot_analyzer.open_video_capture(cv,'clip.mp4')
   self.assertIs(result,cap);self.assertEqual(backend,'CPU');self.assertEqual(len(calls),2 if platform=='win32' else 1)
 def test_automatic_cpu_fallback_is_never_reported_as_gpu(self):
  cap=Capture(mode=0);cv=type('CV',(),{'CAP_FFMPEG':1900,'CAP_PROP_HW_ACCELERATION':50,'VIDEO_ACCELERATION_ANY':1,'VIDEO_ACCELERATION_NONE':0,'VIDEO_ACCELERATION_D3D11':2})()
  cv.VideoCapture=lambda *args:cap
  with patch.object(sys,'platform','win32'):result,backend=shot_analyzer.open_video_capture(cv,'clip.mp4')
  self.assertEqual(backend,'CPU')
