import sys,unittest,json
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))

def utterance(id,start,end,voice=None):
 return {'id':id,'start':start,'end':end,'text':'Una frase completa per identificare la voce.','voice':voice,'voice_evidence':{'status':'identified' if voice else 'unknown','voice':voice,'basis':'source_local_voice_embedding'}}
def fixture():
 source={'media_id':'recording','fps':25,'duration_frames':400,'name':'clip'}
 units=[utterance('a1',0,50,'A'),utterance('b1',75,125,'B'),utterance('a2',150,200,'A'),utterance('b2',225,275,'B'),utterance('query',300,315)]
 segments=[{'start_frame':u['start'],'end_frame':u['end'],'cluster':'1' if u['voice']=='A' or u['id']=='query' else '2'} for u in units]
 return source,units,segments

class VoiceFusionTests(unittest.TestCase):
 def test_unknown_voice_can_use_independent_cluster_consensus(self):
  from voice_fusion import fuse_voice_units,FALLBACK_BASIS
  source,units,segments=fixture();result=fuse_voice_units(source,units,segments)
  q=result['units'][-1];self.assertEqual(q['voice'],'A');self.assertEqual(q['voice_evidence']['basis'],FALLBACK_BASIS);self.assertFalse(q['voice_evidence']['enrollment_eligible']);self.assertEqual(result['summary']['fallback_identified'],1)
 def test_existing_voice_is_not_overwritten_by_secondary_disagreement(self):
  from voice_fusion import fuse_voice_units
  source,units,segments=fixture();units[-1]=utterance('query',300,315,'B');result=fuse_voice_units(source,units,segments)
  self.assertEqual(result['units'][-1]['voice'],'B');self.assertTrue(result['units'][-1]['diarization_evidence']['conflict']);self.assertEqual(result['summary']['conflicts'],1)
 def test_query_and_overlapping_anchors_cannot_certify_themselves(self):
  from voice_fusion import fuse_voice_units
  source,units,segments=fixture();result=fuse_voice_units(source,units,segments)
  # Each A anchor has only one independent A peer after leave-overlap-out.
  self.assertIsNone(result['units'][0]['diarization_evidence']['candidate_voice'])
 def test_repeated_identical_anchor_intervals_are_not_independent(self):
  from voice_fusion import fuse_voice_units
  source,units,segments=fixture();units[2]=utterance('a2',0,50,'A');result=fuse_voice_units(source,units,segments)
  self.assertIsNone(result['units'][-1]['voice'])
 def test_overlapping_anchor_chain_is_one_observation(self):
  from voice_fusion import fuse_voice_units
  source,units,segments=fixture();units[2]=utterance('a2',25,80,'A');segments.append({'start_frame':0,'end_frame':80,'cluster':'1'});result=fuse_voice_units(source,units,segments)
  self.assertIsNone(result['units'][-1]['voice'])
 def test_overlapping_speakers_and_weak_coverage_stay_unknown(self):
  from voice_fusion import fuse_voice_units
  for add in [[{'start_frame':300,'end_frame':315,'cluster':'1'},{'start_frame':300,'end_frame':315,'cluster':'2'}],[{'start_frame':300,'end_frame':304,'cluster':'1'}]]:
   source,units,segments=fixture();segments=segments[:-1]+add;result=fuse_voice_units(source,units,segments);self.assertIsNone(result['units'][-1]['voice'])
 def test_conflicting_cluster_anchors_are_not_forced_to_a_person(self):
  from voice_fusion import fuse_voice_units
  source,units,segments=fixture();units.insert(4,utterance('conflict',275,300,'B'));segments.append({'start_frame':275,'end_frame':300,'cluster':'1'});result=fuse_voice_units(source,units,segments)
  self.assertIsNone(result['units'][-1]['voice'])
 def test_fallback_predictions_cannot_train_other_fallback_predictions(self):
  from voice_fusion import fuse_voice_units,FALLBACK_BASIS
  source,units,segments=fixture()
  for u in [units[0],units[2]]:u['voice_evidence']['basis']=FALLBACK_BASIS
  result=fuse_voice_units(source,units,segments);self.assertIsNone(result['units'][-1]['voice'])
 def test_source_local_cluster_numbers_are_not_global_voice_ids(self):
  from voice_fusion import fuse_voice_units
  source,units,segments=fixture();a=fuse_voice_units(source,units,segments)
  for u in units:
   if u['voice']=='A':u['voice']='C';u['voice_evidence']['voice']='C'
  source['media_id']='another-recording';b=fuse_voice_units(source,units,segments)
  self.assertEqual(a['units'][-1]['voice'],'A');self.assertEqual(b['units'][-1]['voice'],'C')
 def test_fusion_preserves_original_units_and_transcript_timing(self):
  from voice_fusion import fuse_voice_units
  source,units,segments=fixture();original=deepcopy(units);result=fuse_voice_units(source,units,segments)
  self.assertEqual(units,original)
  for old,new in zip(units,result['units']):
   for key in ['id','start','end','text']:self.assertEqual(new[key],old[key])
 def test_empty_turn_output_leaves_primary_result_available(self):
  from voice_fusion import fuse_voice_units
  source,units,_=fixture();result=fuse_voice_units(source,units,[])
  self.assertEqual([u['voice'] for u in result['units']],[u['voice'] for u in units])
 def test_fallback_voice_is_not_positive_face_enrollment_evidence(self):
  from voice_fusion import eligible_for_face_enrollment,FALLBACK_BASIS
  u=utterance('q',0,50,'A');self.assertTrue(eligible_for_face_enrollment(u));u['voice_evidence']['basis']=FALLBACK_BASIS;self.assertFalse(eligible_for_face_enrollment(u))

 def test_strong_secondary_conflict_cannot_enroll_a_face(self):
  from voice_fusion import eligible_for_face_enrollment
  u=utterance('q',0,50,'A');u['diarization_evidence']={'conflict':True}
  self.assertFalse(eligible_for_face_enrollment(u))

 def test_sub_200ms_unknown_does_not_get_a_forced_identity(self):
  from voice_fusion import fuse_voice_units
  source,units,segments=fixture();units[-1]['end']=303
  self.assertIsNone(fuse_voice_units(source,units,segments)['units'][-1]['voice'])

class HybridServiceTests(unittest.TestCase):
 def test_native_result_is_fused_and_reports_actual_phase(self):
  from voice_fusion import enhance_source_voices
  source,units,segments=fixture();events=[]
  class Fake:
   def analyze(self,source):return {'status':'ready','segments':segments,'cache_hit':True,'device_used':'cpu','elapsed_seconds':.1}
  result=enhance_source_voices(source,{'units':units,'gallery':[]},events.append,Fake())
  self.assertEqual(result['units'][-1]['voice'],'A');self.assertTrue(result['diarization']['cache_hit']);self.assertEqual(events[0]['phase'],'voice_diarization');self.assertEqual(events[-1]['current'],1)
 def test_missing_runtime_preserves_baseline_and_is_visible(self):
  from voice_fusion import enhance_source_voices
  from diarization import DiarizationError
  source,units,_=fixture();events=[]
  with patch('voice_fusion.get_diarizer',side_effect=DiarizationError('runtime_or_model_missing')):result=enhance_source_voices(source,{'units':units},events.append)
  self.assertEqual(result['units'],units);self.assertEqual(result['diarization']['status'],'unavailable');self.assertEqual(events[-1]['current'],1)
 def test_unexpected_native_error_is_sanitized_and_does_not_delete_speech(self):
  from voice_fusion import enhance_source_voices
  source,units,_=fixture()
  class Bad:
   def analyze(self,source):raise RuntimeError('PRIVATE_PATH_OR_CONTENT')
  result=enhance_source_voices(source,{'units':units},diarizer=Bad())
  self.assertEqual(result['units'],units);self.assertEqual(result['diarization']['status'],'failed');self.assertNotIn('PRIVATE_PATH_OR_CONTENT',json.dumps(result))
