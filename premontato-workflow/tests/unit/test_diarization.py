import sys,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))

class NormalizeDiarizationTests(unittest.TestCase):
 def test_seconds_are_converted_to_half_open_source_frames_and_padding_clamped(self):
  from diarization import normalize_segments
  source={'fps':25,'duration_frames':250}
  result=normalize_segments([{'start':.041,'end':1.019,'speaker':1},{'start':9.9,'end':10.01,'speaker':2}],source)
  self.assertEqual(result,[{'start_frame':1,'end_frame':26,'cluster':'1'},{'start_frame':247,'end_frame':250,'cluster':'2'}])
 def test_overlapping_duplicates_of_same_cluster_are_merged(self):
  from diarization import normalize_segments
  rows=[{'start':0,'end':1.5,'speaker':1},{'start':.5,'end':2,'speaker':1},{'start':1,'end':2,'speaker':2}]
  result=normalize_segments(rows,{'fps':25,'duration_frames':100})
  self.assertEqual(result,[{'start_frame':0,'end_frame':50,'cluster':'1'},{'start_frame':25,'end_frame':50,'cluster':'2'}])
 def test_invalid_native_intervals_do_not_become_speaker_evidence(self):
  from diarization import normalize_segments
  for row in [{'start':-1,'end':1,'speaker':1},{'start':0,'end':float('nan'),'speaker':1},{'start':0,'end':1,'speaker':True},{'start':0,'end':1,'speaker':'1'},{'start':2,'end':1,'speaker':1},{'start':0,'end':11,'speaker':1}]:
   with self.subTest(row=row),self.assertRaises(ValueError):normalize_segments([row],{'fps':25,'duration_frames':250})
 def test_invalid_source_clock_is_rejected(self):
  from diarization import normalize_segments
  for fps,count in [(0,25),(float('inf'),25),(25,True),(True,25),(25,-1)]:
   with self.subTest(fps=fps,count=count),self.assertRaises(ValueError):normalize_segments([],{'fps':fps,'duration_frames':count})
 def test_empty_speech_is_a_valid_diarization_result(self):
  from diarization import normalize_segments
  self.assertEqual(normalize_segments([],{'fps':25,'duration_frames':100}),[])

class NativeDiarizationTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.movie=self.root/'source.mp4';self.movie.write_bytes(b'private-source');self.runtime=self.root/'nemo-speech.exe';self.runtime.write_bytes(b'test-runtime');self.model=self.root/'model.gguf';self.model.write_bytes(b'test-model')
  self.source={'media_id':'source-a','path':str(self.movie),'fps':25,'duration_frames':50,'name':'clip'}
 def engine(self,device='cpu'):
  import hashlib
  from diarization import NemotronDiarizer
  with patch('diarization.MODEL_SHA256',hashlib.sha256(self.model.read_bytes()).hexdigest()):return NemotronDiarizer(self.runtime,self.model,device=device,cache_root=self.root/'cache')
 def fake_run(self,command,**kwargs):
  output=Path(command[command.index('--output')+1]);output.write_text(json.dumps({'segments':[{'start':0,'end':1,'speaker':1}]}),encoding='utf-8')
  return __import__('subprocess').CompletedProcess(command,0,b'',b'')
 def test_pinned_model_is_checked_before_native_execution(self):
  from diarization import NemotronDiarizer
  with self.assertRaises(ValueError):NemotronDiarizer(self.runtime,self.model,cache_root=self.root/'cache')
 def test_success_reuses_pcm_and_cache_without_second_native_run(self):
  engine=self.engine()
  with patch('local_audio.load_pcm16',return_value=(np.zeros(32000,dtype='<i2'),{'cache_hit':True})),patch('diarization.subprocess.run',side_effect=self.fake_run) as invoke:
   a=engine.analyze(self.source);b=engine.analyze(self.source)
  self.assertFalse(a['cache_hit']);self.assertTrue(b['cache_hit']);self.assertEqual(invoke.call_count,1);self.assertEqual(b['segments'][0]['end_frame'],25)
  command=invoke.call_args.args[0];self.assertIn('v3-offline',command);self.assertNotIn('--offline',command)
  self.assertEqual(list((self.root/'cache').glob('.native-*')),[])
 def test_source_change_invalidates_result(self):
  engine=self.engine()
  with patch('local_audio.load_pcm16',return_value=(np.zeros(32000,dtype='<i2'),{})),patch('diarization.subprocess.run',side_effect=self.fake_run) as invoke:
   engine.analyze(self.source);self.movie.write_bytes(b'different-private-source');engine.analyze(self.source)
  self.assertEqual(invoke.call_count,2)
 def test_invalid_cached_result_is_recomputed(self):
  engine=self.engine()
  with patch('local_audio.load_pcm16',return_value=(np.zeros(32000,dtype='<i2'),{})),patch('diarization.subprocess.run',side_effect=self.fake_run) as invoke:
   engine.analyze(self.source)
   cache=next((self.root/'cache').glob('*.json'));data=json.loads(cache.read_text());data['value']['segments'][0]['end']=1000;cache.write_text(json.dumps(data));result=engine.analyze(self.source)
  self.assertEqual(invoke.call_count,2);self.assertFalse(result['cache_hit'])
 def test_timeout_is_not_cached_and_does_not_expose_private_path(self):
  from diarization import DiarizationError
  import subprocess
  engine=self.engine()
  with patch('local_audio.load_pcm16',return_value=(np.zeros(32000,dtype='<i2'),{})),patch('diarization.subprocess.run',side_effect=subprocess.TimeoutExpired(['PRIVATE_PATH'],1)):
   with self.assertRaises(DiarizationError) as error:engine.analyze(self.source)
  self.assertEqual(error.exception.code,'native_timeout');self.assertNotIn('PRIVATE_PATH',str(error.exception));self.assertEqual(list((self.root/'cache').glob('*.json')),[])
 def test_bad_json_is_not_cached(self):
  from diarization import DiarizationError
  engine=self.engine()
  def broken(command,**kwargs):
   Path(command[command.index('--output')+1]).write_text('not json');return __import__('subprocess').CompletedProcess(command,0,b'',b'')
  with patch('local_audio.load_pcm16',return_value=(np.zeros(32000,dtype='<i2'),{})),patch('diarization.subprocess.run',side_effect=broken):
   with self.assertRaises(DiarizationError) as error:engine.analyze(self.source)
  self.assertEqual(error.exception.code,'invalid_native_output');self.assertEqual(list((self.root/'cache').glob('*.json')),[])
 def test_cuda_failure_retries_cpu_once_with_explicit_provenance(self):
  engine=self.engine('cuda')
  def gpu_fail(command,**kwargs):
   if command[command.index('--device')+1]=='cuda':return __import__('subprocess').CompletedProcess(command,1,b'',b'PRIVATE_PATH')
   return self.fake_run(command,**kwargs)
  with patch('local_audio.load_pcm16',return_value=(np.zeros(32000,dtype='<i2'),{})),patch('diarization.subprocess.run',side_effect=gpu_fail) as invoke:result=engine.analyze(self.source)
  self.assertEqual(invoke.call_count,2);self.assertEqual(result['device_used'],'cpu');self.assertEqual(result['fallback_reason'],'native_exit');self.assertNotIn('PRIVATE_PATH',json.dumps(result))

 def test_corrupt_cached_provenance_is_not_returned_or_exposed(self):
  engine=self.engine()
  with patch('local_audio.load_pcm16',return_value=(np.zeros(32000,dtype='<i2'),{})),patch('diarization.subprocess.run',side_effect=self.fake_run) as invoke:
   engine.analyze(self.source)
   cache=next((self.root/'cache').glob('*.json'));data=json.loads(cache.read_text());data['value']['fallback_reason']='PRIVATE_CORRUPT_CACHE';cache.write_text(json.dumps(data));result=engine.analyze(self.source)
  self.assertEqual(invoke.call_count,2);self.assertNotIn('PRIVATE_CORRUPT_CACHE',json.dumps(result))
