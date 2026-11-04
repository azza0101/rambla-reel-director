import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))

class UpstreamVisualTests(unittest.TestCase):
 def test_dominant_listener_does_not_veto_verified_speaking_face(self):
  from unittest.mock import patch,MagicMock
  import numpy as np
  from observed_editor import build_observed_excerpt
  source={'media_id':'m','name':'source','path':'unused-source.mp4','duration_frames':100,'fps':25}
  candidate={**source,'media_id':'c','name':'alternative'}
  unit={'id':'u','voice':'a','start':0,'end':100,'text':'These are enough words for a complete turn.'}
  encoder=MagicMock();encoder.encode.side_effect=lambda texts:np.ones((len(texts),2))
  prepared={s['media_id']:{'units':[unit],'gallery':[]} for s in (source,candidate)}
  with patch('observed_editor.prepare_voice_data',return_value=prepared),patch('active_speaker.analyze_candidate',return_value={'status':'visible','faces':[{'mean':1.,'positive':1.}]}),patch('speaker_identity.face_vector',side_effect=lambda s,*args,**kwargs:[1.] if s['media_id']=='c' else None),patch('speaker_identity.match_role',return_value='a'),patch('transcript_align.get_semantic_encoder',return_value=encoder),patch('upstream_visual.UpstreamVisual') as factory:
   factory.return_value.__enter__.return_value.observe.return_value={'visible_role':'b','objects_requested':False}
   result=build_observed_excerpt({'sources':[source,candidate],'units':{},'reference':{'media_id':'m','start_frame':0,'end_frame':100},'fps':25,'inventory_config':{'configured':True}})
   self.assertEqual(result['decisions'][0]['media_id'],'c')
   self.assertTrue(result['decisions'][0]['speaker_visible'])
 def test_editor_propagates_requested_zero_object_budget(self):
  from unittest.mock import patch,MagicMock
  import numpy as np
  from observed_editor import build_observed_excerpt
  source={'media_id':'m','name':'source','path':'unused-source.mp4','duration_frames':100,'fps':25}
  unit={'id':'u','voice':'a','start':0,'end':100,'text':'These are enough words for a complete turn.'}
  encoder=MagicMock();encoder.encode.side_effect=lambda texts:np.ones((len(texts),2))
  with patch('observed_editor.prepare_voice_data',return_value={'m':{'units':[unit],'gallery':[]}}),patch('active_speaker.analyze_candidate',return_value={'status':'unknown'}),patch('speaker_identity.face_vector',return_value=None),patch('transcript_align.get_semantic_encoder',return_value=encoder),patch('upstream_visual.UpstreamVisual') as factory:
   factory.return_value.__enter__.return_value.observe.return_value={'visible_role':None}
   build_observed_excerpt({'sources':[source],'units':{'m':[unit]},'reference':{'media_id':'m','start_frame':0,'end_frame':100},'fps':25,'inventory_config':{'configured':True},'inventory_frame_budget':0})
   self.assertEqual(factory.call_args.kwargs['object_budget'],0)
   factory.return_value.__exit__.assert_called_once()
 def test_object_request_enriches_previously_identity_only_interval(self):
  from unittest.mock import patch
  from upstream_visual import UpstreamVisual
  with patch('upstream_visual.LocalInventory') as client,patch('upstream_visual.direct_face',return_value=([1.],False)) as read,patch('speaker_identity.match_role',return_value='a'):
   client.return_value.observe.return_value={'objects':[]}
   with UpstreamVisual({'configured':True},'unused',[],face_budget=3,object_budget=3) as index:
    first=index.observe({'media_id':'m'},0,100)
    second=index.observe({'media_id':'m'},0,100,objects=True)
    self.assertFalse(first['inventory']['complete'])
    self.assertTrue(second['inventory']['complete'])
    self.assertEqual(client.return_value.observe.call_count,3)
    self.assertEqual(read.call_count,3)
 def test_zero_object_budget_never_invokes_model(self):
  from unittest.mock import patch
  from upstream_visual import UpstreamVisual
  with patch('upstream_visual.LocalInventory') as client,patch('upstream_visual.direct_face',return_value=(None,False)):
   with UpstreamVisual({'configured':True},'unused',[],face_budget=3,object_budget=0) as index:
    self.assertFalse(index.observe({'media_id':'m'},0,100,objects=True)['inventory']['complete'])
    client.return_value.observe.assert_not_called()
 def test_frame_budget_is_enforced_and_unknown_is_not_promoted(self):
  from unittest.mock import patch
  from upstream_visual import UpstreamVisual
  with UpstreamVisual(None,'unused',[],face_budget=3,object_budget=0) as index,patch('upstream_visual.direct_face',return_value=([1.],False)) as read,patch('speaker_identity.match_role',return_value='a'):
   self.assertEqual(index.observe({'media_id':'m'},0,100)['visible_role'],'a')
   self.assertIsNone(index.observe({'media_id':'m'},100,200)['visible_role'])
   self.assertEqual(read.call_count,3)
 def test_disagreeing_frames_are_not_outvoted_by_extra_samples(self):
  from unittest.mock import patch
  from upstream_visual import UpstreamVisual
  with UpstreamVisual(None,'unused',[],face_budget=10) as index,patch('upstream_visual.direct_face',return_value=([1.],False)) as read,patch('speaker_identity.match_role',side_effect=['a','b','a']):
   self.assertIsNone(index.observe({'media_id':'m'},0,100)['visible_role']);self.assertEqual(read.call_count,3)
 def test_two_consistent_independent_frames_required(self):
  from upstream_visual import consensus_role
  self.assertEqual(consensus_role(['a',None,'a']),'a')
  self.assertIsNone(consensus_role(['a',None,None]))
  self.assertIsNone(consensus_role(['a','b','a']))
 def test_a_small_secondary_face_does_not_hide_dominant_subject(self):
  from upstream_visual import dominant_face
  a=[0,0,200,200];b=[200,0,30,30]
  self.assertEqual(dominant_face([a,b]),a)
  self.assertIsNone(dominant_face([a,[200,0,150,180]]))
 def test_visuals_alone_do_not_override_content_or_voice(self):
  from upstream_visual import may_rescue_question
  self.assertFalse(may_rescue_question('Che cosa vuoi?','Non voglio niente.',.99,.99,'a','a','a'))
  self.assertFalse(may_rescue_question("E questo che cos'è?","Che cos'è questo?",.9,.9,'a','b','a'))
  self.assertTrue(may_rescue_question("E questo che cos'è?","Che cos'è questo?",.9,.9,'a','a','a'))
