import os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[2]/'worker'))
import edit_selector
from protocol import dispatch

class SharedAudioCacheTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.file=Path(self.tmp.name)/'video.mp4';self.file.write_bytes(b'media')
  self.source={'media_id':'m','path':str(self.file),'fps':25,'duration_frames':100}
  self.env=patch.dict(os.environ,{'PREMONTATO_CACHE_DIR':str(Path(self.tmp.name)/'cache')});self.env.start();self.addCleanup(self.env.stop)
 def test_internal_and_ipc_share_rms_result_without_changing_silence_ranges(self):
  expected={'status':'ok','silences':[{'start_frame':10,'end_frame':40}]}
  with patch.object(edit_selector,'analyze_audio',return_value=expected) as analyze:
   a=edit_selector.cached_audio(self.source)
   b=dispatch({'protocol':1,'request_id':'audio','action':'analyze_audio','payload':{'media':self.source}})['result']
  self.assertEqual(analyze.call_count,1);self.assertFalse(a['cache_hit']);self.assertTrue(b['cache_hit']);self.assertEqual(a['silences'],b['silences'])
 def test_file_fps_and_duration_invalidate_cache(self):
  with patch.object(edit_selector,'analyze_audio',return_value={'status':'ok','silences':[]}) as analyze:
   edit_selector.cached_audio(self.source);edit_selector.cached_audio({**self.source,'fps':30});edit_selector.cached_audio({**self.source,'duration_frames':120});self.file.write_bytes(b'changed media');edit_selector.cached_audio(self.source)
  self.assertEqual(analyze.call_count,4)
 def test_unavailable_result_is_not_reused_as_measured_silence(self):
  with patch.object(edit_selector,'analyze_audio',side_effect=[{'status':'unavailable'},{'status':'ok','silences':[]}]) as analyze:
   a=edit_selector.cached_audio(self.source);b=edit_selector.cached_audio(self.source)
  self.assertEqual(analyze.call_count,2);self.assertEqual(a['status'],'unavailable');self.assertEqual(b['status'],'ok')

 def test_real_rms_measurement_exposes_scan_time_but_hit_does_not_repeat_scan(self):
  import numpy as np
  from runtime_trace import trace_pipeline
  @trace_pipeline
  def pipeline(payload,report):
   first=edit_selector.cached_audio(self.source);second=edit_selector.cached_audio(self.source)
   return {'first':first,'second':second}
  with patch('local_audio.load_pcm16',return_value=(np.zeros(64000,dtype=np.int16),{'cache_hit':True})):
   result=pipeline({},lambda e:None)
  self.assertGreater(result['performance']['rms']['scan_seconds'],0)
  self.assertEqual(result['performance']['rms']['cache_hits'],1)
  self.assertEqual(result['first']['silences'],result['second']['silences'])

 def test_script_breath_reuses_rms_previously_requested_by_protocol(self):
  from listening_reaction import add_scripted_breaths
  source={**self.source,'take_id':'t','duration_frames':100,'segments':[]}
  decision={'media_id':'m','take_id':'t','beat_id':'b','shot_size':'close','start_frame':0,'end_frame':50}
  beats=[{'beat_id':'b','kind':'dialogue','character':'A'},{'beat_id':'pause','kind':'action','text':'Silenzio'}]
  with patch.object(edit_selector,'analyze_audio',return_value={'status':'ok','silences':[{'start_frame':50,'end_frame':80}]}) as compute,patch('active_speaker.verify_listener',return_value={'verified':True}):
   dispatch({'protocol':1,'request_id':'audio','action':'analyze_audio','payload':{'media':source}})
   holds=add_scripted_breaths([decision],[source],beats,{'m':{'role':'A','start':0,'end':40}},25)
  self.assertEqual(compute.call_count,1);self.assertEqual(len(holds),1);self.assertEqual(holds[0]['start_frame'],50)
