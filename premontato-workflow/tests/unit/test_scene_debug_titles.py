import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))
from local_audio import render_scene_debug_titles
class SceneDebugTitlesTests(unittest.TestCase):
 def test_title_has_exact_duration_alpha_and_reuses_existing_asset(self):
  import cv2
  with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'PREMONTATO_CACHE_DIR':str(Path(folder)/'cache'/'shots')}):
   payload={'scenes':[{'number':2,'frames':60}], 'fps':25,'width':1920,'height':1080}
   first=render_scene_debug_titles(payload);p=Path(first['assets']['2']);self.assertTrue(p.is_file());stamp=p.stat().st_mtime_ns
   cap=cv2.VideoCapture(str(p));self.assertEqual(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),60);self.assertAlmostEqual(cap.get(cv2.CAP_PROP_FPS),25);cap.release()
   import subprocess
   from local_audio import ffmpeg_path
   alpha=subprocess.run([ffmpeg_path(),'-v','error','-i',str(p),'-frames:v','1','-vf','alphaextract','-pix_fmt','gray','-f','rawvideo','pipe:1'],capture_output=True,check=True).stdout
   self.assertEqual(min(alpha),0);self.assertEqual(max(alpha),255);self.assertGreater(alpha.count(0),len(alpha)*.9)
   second=render_scene_debug_titles(payload);self.assertEqual(p.stat().st_mtime_ns,stamp);self.assertEqual(second['cache_hits'],1)
 def test_rejects_bad_or_unbounded_title_jobs(self):
  for job in [{'scenes':[{'number':1,'frames':0}],'fps':25},{'scenes':[{'number':0,'frames':25}],'fps':25},{'scenes':[{'number':1,'frames':25}],'fps':0}]:
   with self.assertRaises(ValueError):render_scene_debug_titles(job)
