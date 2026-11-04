import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))
class ObservedCameraTests(unittest.TestCase):
 def test_last_complete_performance_wins_before_literal_similarity(self):
  from observed_camera import lock_performances
  rows=[{'id':'old','field':'a','order':1,'coverage':1.,'usable':True},{'id':'last','field':'a','order':2,'coverage':.94,'usable':True},{'id':'pickup','field':'a','order':3,'coverage':.4,'usable':True}]
  self.assertEqual(lock_performances(rows)['a'],'last')
 def test_aborted_latest_does_not_replace_good_take(self):
  from observed_camera import lock_performances
  rows=[{'id':'good','field':'a','order':1,'coverage':1.,'usable':True},{'id':'bad','field':'a','order':2,'coverage':1.,'usable':False}]
  self.assertEqual(lock_performances(rows)['a'],'good')
 def test_monotonic_alignment_keeps_two_equal_gag_answers(self):
  from observed_camera import align_turns
  turns=[{'voice':'a'},{'voice':'b'},{'voice':'a'},{'voice':'b'}]
  candidates=[{'voice':'a','start_frame':0,'end_frame':10},{'voice':'b','start_frame':20,'end_frame':30},{'voice':'a','start_frame':40,'end_frame':50},{'voice':'b','start_frame':60,'end_frame':70}]
  sim=[[1,0,.8,0],[0,1,0,1],[.8,0,1,0],[0,1,0,1]]
  self.assertEqual(align_turns(turns,candidates,sim),[0,1,2,3])
 def test_unknown_voice_is_not_forced(self):
  from observed_camera import align_turns
  self.assertEqual(align_turns([{'voice':None}],[{'voice':'a','start_frame':0,'end_frame':10}],[[1]]),[None])
 def test_missing_middle_turn_can_be_skipped_without_moving_backwards(self):
  from observed_camera import align_turns
  t=[{'voice':'a'},{'voice':'b'},{'voice':'a'}];c=[{'voice':'a','start_frame':10,'end_frame':20},{'voice':'a','start_frame':30,'end_frame':40}]
  self.assertEqual(align_turns(t,c,[[1,.6],[0,0],[.6,1]]),[0,None,1])
 def test_audit_does_not_relabel_uncovered_jump_as_fixed(self):
  from observed_camera import audit_edit
  d=[{'media_id':'m','field':'a','start_frame':0,'end_frame':50,'record_frame':0,'ids':['u1']},{'media_id':'m','field':'a','start_frame':100,'end_frame':150,'record_frame':50,'ids':['u2']}]
  a=audit_edit(d,[],['u1','u2'],25)
  self.assertEqual(a['exposed_same_field_joins'],[50]);self.assertFalse(a['ready'])
 def test_audit_detects_lost_and_duplicate_events(self):
  from observed_camera import audit_edit
  d=[{'media_id':'m','field':'a','start_frame':0,'end_frame':50,'record_frame':0,'ids':['u1','u1']}]
  a=audit_edit(d,[],['u1','u2'],25)
  self.assertEqual(a['missing_events'],['u2']);self.assertEqual(a['duplicate_events'],['u1'])
 def test_covered_join_preserves_base_audio_and_minimum_length(self):
  from observed_camera import audit_edit
  d=[{'media_id':'m','field':'a','start_frame':0,'end_frame':50,'record_frame':0,'ids':['u1']},{'media_id':'m','field':'a','start_frame':100,'end_frame':150,'record_frame':50,'ids':['u2']}]
  c={'start_frame':0,'end_frame':40,'record_frame':30,'verified_listener':True,'different_person':True,'audio':'base_unchanged'}
  self.assertTrue(audit_edit(d,[c],['u1','u2'],25)['ready'])
  c['end_frame']=20;self.assertFalse(audit_edit(d,[c],['u1','u2'],25)['ready'])
 def test_listener_requires_other_known_person_and_consistent_voice(self):
  from observed_camera import listener_evidence
  self.assertTrue(listener_evidence('a',['b','b',None])['verified_listener'])
  self.assertFalse(listener_evidence('a',['a','a'])['verified_listener'])
  self.assertFalse(listener_evidence('a',['b','c'])['verified_listener'])
  self.assertFalse(listener_evidence(None,['b'])['verified_listener'])
 def test_listener_insufficient_audio_evidence_stays_uncertain(self):
  from observed_camera import listener_evidence
  self.assertFalse(listener_evidence('a',['b',None,None])['verified_listener'])
 def test_audit_flags_reused_source_frames_even_with_distinct_event_ids(self):
  from observed_camera import audit_edit
  d=[{'media_id':'m','field':'a','start_frame':0,'end_frame':50,'record_frame':0,'ids':['u1']},{'media_id':'m','field':'b','start_frame':40,'end_frame':100,'record_frame':50,'ids':['u2']}]
  self.assertFalse(audit_edit(d,[],['u1','u2'],25)['ready'])
 def test_audit_flags_subsecond_flash_shot(self):
  from observed_camera import audit_edit
  d=[{'media_id':'m','field':'a','start_frame':0,'end_frame':10,'record_frame':0,'ids':['u1']}]
  self.assertFalse(audit_edit(d,[],['u1'],25)['ready'])
 def test_contiguous_turn_boundaries_are_not_physical_flash_cuts(self):
  from observed_camera import audit_edit
  d=[{'media_id':'m','field':'a','start_frame':i*10,'end_frame':(i+1)*10,'record_frame':i*10,'ids':[str(i)]} for i in range(4)]
  self.assertEqual(audit_edit(d,[],[str(i) for i in range(4)],25)['short_shots'],[])
 def test_discontinuous_short_fragments_remain_flash_cuts(self):
  from observed_camera import audit_edit
  d=[{'media_id':'m','field':'a','start_frame':i*20,'end_frame':i*20+10,'record_frame':i*10,'ids':[str(i)]} for i in range(4)]
  self.assertEqual(audit_edit(d,[],[str(i) for i in range(4)],25)['short_shots'],[0,1,2,3])
 def test_overlapping_alternative_windows_are_not_reused_in_alignment(self):
  from observed_camera import align_windows
  t=[{'voice':'a'},{'voice':'b'}];c=[{'voice':'a','start_frame':0,'end_frame':100},{'voice':'a','start_frame':0,'end_frame':40},{'voice':'b','start_frame':40,'end_frame':80}]
  self.assertEqual(align_windows(t,c,[[1,.8,0],[0,0,1]]),[1,2])
 def test_alternative_windows_preserve_two_equal_answers_in_time_order(self):
  from observed_camera import align_windows
  t=[{'voice':'b'},{'voice':'b'}];c=[{'voice':'b','start_frame':0,'end_frame':40},{'voice':'b','start_frame':30,'end_frame':70},{'voice':'b','start_frame':80,'end_frame':120}]
  result=align_windows(t,c,[[1,1,1],[1,1,1]])
  self.assertLessEqual(c[result[0]]['end_frame'],c[result[1]]['start_frame'])
 def test_rejected_visual_candidate_is_replaced_before_alignment_finishes(self):
  from observed_camera import verified_alignment
  t=[{'voice':'a'}];c=[{'voice':'a','start_frame':0,'end_frame':40},{'voice':'a','start_frame':80,'end_frame':120}];seen=[]
  def check(j):seen.append(j);return j==1
  self.assertEqual(verified_alignment(t,c,[[1.,.9]],check),[1]);self.assertEqual(seen,[0,1])
 def test_visual_retry_never_returns_unverified_window_when_budget_ends(self):
  from observed_camera import verified_alignment
  t=[{'voice':'a'}];c=[{'voice':'a','start_frame':i*50,'end_frame':i*50+40} for i in range(3)]
  self.assertEqual(verified_alignment(t,c,[[1.,.9,.8]],lambda j:False,max_rounds=1),[None])
 def test_rejected_source_window_is_not_retried_for_another_turn(self):
  from observed_camera import verified_alignment
  t=[{'voice':'a'},{'voice':'a'}]
  c=[{'voice':'a','start_frame':i*50,'end_frame':i*50+40} for i in range(3)]
  seen=[]
  def check(j):seen.append(j);return j==1
  result=verified_alignment(t,c,[[.95,.9,.99],[.99,.9,.95]],check,max_rounds=2)
  self.assertIn(1,result);self.assertEqual(seen.count(1),1)
