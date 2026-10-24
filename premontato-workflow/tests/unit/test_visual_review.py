import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[2]/'worker'))
from shot_analyzer import cluster_faces, speaker_coverage

class VisualReviewTests(unittest.TestCase):
    def test_same_frame_faces_cannot_merge_and_weak_match_stays_unknown(self):
        observations=[{'observation_id':'a','still_id':'s1','embedding':[1.,0.,0.]},
          {'observation_id':'b','still_id':'s1','embedding':[.99,.01,0.]},
          {'observation_id':'c','still_id':'s2','embedding':[.99,0.,.01]},
          {'observation_id':'d','still_id':'s3','embedding':[0.,0.,1.]}]
        result=cluster_faces(observations)
        by_id={x['observation_id']:x for x in result}
        self.assertNotEqual(by_id['a']['person_id'],by_id['b']['person_id'])
        self.assertNotEqual(by_id['d']['person_id'],by_id['a']['person_id'])
        self.assertTrue(by_id['c']['ambiguous'])
        self.assertIsNone(by_id['c']['person_id'])
    def test_review_must_cover_entire_dialogue_to_assert_speaker(self):
        shots=[{'media_id':'m','start_frame':0,'end_frame':50,'reviewed':True,'visible_subjects':['LUCA']},
          {'media_id':'m','start_frame':50,'end_frame':100,'reviewed':True,'visible_subjects':['MARTA']}]
        self.assertEqual(speaker_coverage(shots,'m',10,40,'Luca'),'visible')
        self.assertEqual(speaker_coverage(shots,'m',10,60,'LUCA'),'unknown')
        self.assertEqual(speaker_coverage(shots,'m',60,90,'LUCA'),'absent')
        self.assertEqual(speaker_coverage([], 'm',0,10,'LUCA'),'unknown')

    def test_planner_prefers_confirmed_speaker_over_wrong_latest_reverse(self):
        from protocol import dispatch
        sources=[{'media_id':media,'take_id':media,'take_index':index,'duration_frames':200,'segments':[{'text':'ciao a tutti','start_frame':20,'end_frame':50}]} for media,index in [('man',1),('woman',3),('unknown',4)]]
        shots=[{'media_id':media,'start_frame':0,'end_frame':200,'reviewed':True,'visible_subjects':names,'shot_size':'close','confidence':1} for media,names in [('man',['LUCA']),('woman',['MARTA']),('unknown',[])]]
        request={'protocol':1,'request_id':'v','action':'build_plan','payload':{'fps':25,'beats':[{'beat_id':'a','kind':'dialogue','character':'LUCA','text':'ciao a tutti'}],'sources':sources,'shots':shots}}
        result=dispatch(request)['result']['decisions'][0]
        self.assertEqual(result['media_id'],'man')
        self.assertEqual(result['speaker_coverage'],'visible')
        request['payload']['sources']=sources[1:]
        result=dispatch(request)['result']['decisions'][0]
        self.assertEqual(result['media_id'],'unknown')
        self.assertEqual(result['speaker_coverage'],'unknown')

    def test_broken_recognizer_is_retried_after_model_repair(self):
        import tempfile,os,contextlib,io
        from unittest.mock import patch
        from protocol import dispatch
        with tempfile.TemporaryDirectory() as directory:
            media_path=Path(directory)/'clip.mp4';media_path.write_bytes(b'fixture')
            media={'media_id':'m','path':str(media_path),'duration_frames':100,'fps':25}
            failed={'intervals':[{'stills':[{}]}],'observations':[],'recognition_error':'model missing'}
            repaired={**failed,'recognition_error':None}
            with patch.dict(os.environ,{'PREMONTATO_CACHE_DIR':directory}),patch('shot_analyzer.visual_review_media',side_effect=[failed,repaired]) as analyze,contextlib.redirect_stdout(io.StringIO()):
                request={'protocol':1,'request_id':'repair','action':'visual_review','payload':{'media':[media],'shots':[]}}
                self.assertTrue(dispatch(request)['result']['warnings'])
                self.assertEqual(dispatch(request)['result']['warnings'],[])
                self.assertEqual(analyze.call_count,2)

    def test_confirmed_speaker_is_not_discarded_before_scoring_cleaner_offscreen_asr(self):
        from unittest.mock import patch
        from protocol import dispatch
        sources=[{'media_id':name,'take_id':name,'take_index':index,'duration_frames':200,'segments':[]} for index,name in enumerate(['visible','offscreen'],1)]
        shots=[{'media_id':name,'start_frame':0,'end_frame':200,'reviewed':True,'visible_subjects':names,'shot_size':'close','confidence':1} for name,names in [('visible',['MARTA']),('offscreen',['LUCA'])]]
        hits={(name,'ok'):[{'start_frame':20,'end_frame':50,'text':'ok','score':score,'semantic_score':.8,'coverage':1}] for name,score in [('visible',.57),('offscreen',.84)]}
        with patch('transcript_align.semantic_scene_hits',return_value=hits):
            result=dispatch({'protocol':1,'request_id':'visibility','action':'build_plan','payload':{'fps':25,'semantic':True,'beats':[{'beat_id':'ok','kind':'dialogue','character':'MARTA','text':'ok'}],'sources':sources,'shots':shots}})['result']['decisions'][0]
        self.assertEqual(result['media_id'],'visible');self.assertEqual(result['speaker_coverage'],'visible')
