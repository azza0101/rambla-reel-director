import unittest
from protocol import dispatch
from edit_selector import pace_plan

class DirectionsTests(unittest.TestCase):
    def plan(self, close_visible=True, close_available=True, markers=None):
        beats=[{'beat_id':str(i),'kind':'dialogue','character':'LUI','text':text} for i,text in enumerate(['prima battuta','seconda battuta','terza battuta'])]
        sources=[{'take_id':name,'media_id':name,'take_index':n,'duration_frames':400,'segments':[{'start_frame':30+i*100,'end_frame':60+i*100,'text':b['text']} for i,b in enumerate(beats)]} for n,name in enumerate(['close','wide'],1)]
        shots=[{'media_id':name,'start_frame':0,'end_frame':400,'shot_size':name,'confidence':1,'reviewed':True,'visible_subjects':['LUI'] if name=='wide' or close_visible else ['LEI']} for name in ['close','wide'] if name!='close' or close_available]
        return dispatch({'protocol':1,'request_id':'d','action':'build_plan','payload':{'fps':25,'beats':beats,'sources':sources,'shots':shots,'directions':{'profile':'VIDEO COLICHE','notes':'Prima piano di reazione, poi aprire sul rifiuto','markers':markers or {'0':'tension','2':'resolution'}}}})['result'],sources,beats
    def test_holds_close_until_explicit_resolution_then_opens_wide(self):
        plan,_,_=self.plan()
        self.assertEqual([d['shot_size'] for d in plan['decisions']],['close','close','wide'])
        self.assertEqual([d['narrative_role'] for d in plan['decisions']],['tension','tension','resolution'])
    def test_style_does_not_choose_an_absent_speaker_to_get_a_close_shot(self):
        plan,_,_=self.plan(close_visible=False)
        self.assertEqual([d['media_id'] for d in plan['decisions']],['wide']*3)
        self.assertIn('STYLE_COVERAGE_UNAVAILABLE',plan['decisions'][0]['rationale_codes'])
    def test_unclassified_close_is_not_treated_as_verified_coverage(self):
        plan,_,_=self.plan(close_available=False)
        self.assertEqual(plan['decisions'][0]['shot_size'],'wide')
        self.assertTrue(plan['decisions'][0]['warnings'])
    def test_free_marker_ends_tension_without_forcing_a_release(self):
        plan,_,_=self.plan(markers={'0':'tension','1':'free'})
        self.assertEqual([d['narrative_role'] for d in plan['decisions']],['tension','free','free'])
    def test_pacing_does_not_replace_a_narrative_choice_with_an_alternative(self):
        plan,sources,beats=self.plan()
        paced=pace_plan(plan,sources,{},beats,25,{'minimum_shot_seconds':5})
        self.assertEqual([d['shot_size'] for d in paced['decisions']],['close','close','wide'])
    def test_tension_preserves_pauses_unless_manually_overridden(self):
        plan,sources,beats=self.plan()
        paced=pace_plan(plan,sources,{s['media_id']:{'status':'ok','silences':[]} for s in sources},beats,25)
        self.assertTrue(paced['decisions'][0]['pacing']['protected_pause'])
        plan['decisions'][0]['preserve_pause']=False
        self.assertFalse(pace_plan(plan,sources,{},beats,25)['decisions'][0]['pacing']['protected_pause'])
