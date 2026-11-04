import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))

class VisualInventoryTests(unittest.TestCase):
 def test_one_invalid_frame_does_not_block_next_sample(self):
  from unittest.mock import patch
  from visual_inventory import analyze_inventory
  with patch('visual_inventory.LocalInventory') as cls:
   cls.return_value.__enter__.return_value.observe.side_effect=[ValueError('bad json'),{'frame':25,'objects':[],'cache_hit':False}]
   p=analyze_inventory({'source':{},'frames':[0,25],'config':{}})
  self.assertFalse(p['complete']);self.assertEqual(p['samples'][0]['frame'],25);self.assertEqual(len(p['errors']),1)
 def test_malformed_http_replies_become_recoverable_validation_errors(self):
  from visual_inventory import parse_response
  for raw in ({'choices':[]},{'choices':[{'finish_reason':'stop','message':{'content':None}}]},None):
   with self.assertRaises(ValueError):parse_response(raw)
 def test_no_relevant_candidates_does_not_require_model_assets(self):
  from visual_inventory import annotate_candidates
  self.assertEqual(annotate_candidates([],[],{},'unused')['frames'],0)
 def test_zero_budget_does_not_require_any_installed_model(self):
  from visual_inventory import annotate_candidates
  self.assertEqual(annotate_candidates([],[],{},'unused',max_frames=0)['frames'],0)
 def test_cache_hit_does_not_decode_or_start_model_again(self):
  import tempfile
  from unittest.mock import patch
  from visual_inventory import LocalInventory
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'fixture';p.write_bytes(b'synthetic')
   source={'path':str(p),'fps':25,'duration_frames':100}
   config={'server':str(p),'model':str(p),'projection':str(p)}
   with LocalInventory(config,d) as client,patch.object(client,'infer',return_value={'held_objects':[]}) as infer,patch('visual_inventory.subprocess.check_output',return_value=b'jpeg') as decode,patch('visual_inventory.subprocess.Popen') as launch:
    self.assertFalse(client.observe(source,10)['cache_hit']);self.assertTrue(client.observe(source,10)['cache_hit'])
    self.assertEqual(infer.call_count,1);self.assertEqual(decode.call_count,1);launch.assert_not_called()
 def test_unsorted_requested_frames_are_rejected_before_model_start(self):
  from visual_inventory import analyze_inventory
  with self.assertRaises(ValueError):analyze_inventory({'source':{},'frames':[20,10]})
 def test_host_owns_frame_identity_and_model_cannot_assign_a_person(self):
  from visual_inventory import normalize_inventory
  p=normalize_inventory({'frame_id':'invented','held_objects':[{'region':'foreground','type':'other','holder':'visible_woman','evidence':'blurred item'}]},123)
  self.assertEqual(p['frame'],123);self.assertEqual(p['objects'][0]['owner'],'unverified')
 def test_absence_does_not_mean_put_down(self):
  from visual_inventory import summarize
  s=summarize([{'frame':0,'objects':[{'type':'other'}]},{'frame':25,'objects':[]}])
  self.assertEqual(s['changes'][0]['kind'],'no_longer_visible');self.assertFalse(s['gesture_completion_verified'])
 def test_invalid_shape_is_not_cached_as_empty_inventory(self):
  from visual_inventory import normalize_inventory
  for p in ({},{'held_objects':None},{'held_objects':[{'region':'foreground','type':'invented'}]}):
   with self.assertRaises(ValueError):normalize_inventory(p,0)
 def test_all_samples_required_and_frames_are_source_bounds(self):
  from visual_inventory import sample_frames
  self.assertEqual(sample_frames(100,110,3),[100,104,109])
  with self.assertRaises(ValueError):sample_frames(100,100,3)
 def test_ambiguous_object_type_is_not_certified_as_known(self):
  from visual_inventory import summarize
  p=summarize([{'frame':0,'objects':[{'type':'uncertain'}]},{'frame':25,'objects':[{'type':'other'}]}])
  self.assertEqual(p['known_object_fraction'],0);self.assertEqual(p['presence_fraction'],1)
 def test_inventory_cannot_identify_speaker(self):
  from visual_inventory import summarize
  p=summarize([{'frame':0,'objects':[]}])
  self.assertFalse(p['speaker_verified']);self.assertFalse(p['owner_verified'])
