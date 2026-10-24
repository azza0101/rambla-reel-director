import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[2]/'worker'))
from shot_analyzer import summarize_samples
from transcript_align import complete_beat_candidates

class AdvancedTests(unittest.TestCase):
    def test_one_bad_face_sample_does_not_change_segment(self):
        rows=[{'shot_size':s,'confidence':.7,'face_boxes':[]} for s in ['medium','medium','wide','unknown','medium']]
        self.assertEqual(summarize_samples(rows)['shot_size'],'medium')
    def test_complete_line_spans_asr_segments(self):
        words=[{'text':w,'start_frame':i*10,'end_frame':i*10+8} for i,w in enumerate('Ma che entra guarda il povero ingegnere che dobbiamo fare'.split())]
        segs=[{'text':'Ma che entra guarda il povero ingegnere','words':words[:7],'start_frame':0,'end_frame':68}, {'text':'che dobbiamo fare','words':words[7:],'start_frame':70,'end_frame':98}]
        hits=complete_beat_candidates({'text':"Ma che entra? Guarda il povero ingegnere. Che dobbiamo fare?"},segs,25)
        self.assertTrue(hits)
        self.assertEqual(hits[0]['start_frame'],0)
        self.assertEqual(hits[0]['end_frame'],98)
        self.assertGreater(hits[0]['coverage'],.9)
    def test_partial_line_is_not_reported_complete(self):
        hits=complete_beat_candidates({'text':'Guarda il povero ingegnere. Mi ha confidato di essere solo. Che dobbiamo fare?'},[{'text':'Guarda il povero ingegnere','start_frame':10,'end_frame':50}],25)
        self.assertTrue(not hits or hits[0]['coverage']<.6)
    def test_repeated_take_not_joined(self):
        segs=[{'text':'guarda il povero ingegnere','start_frame':i*200,'end_frame':i*200+40} for i in range(2)]
        hits=complete_beat_candidates({'text':'guarda il povero ingegnere'},segs,25)
        self.assertTrue(hits)
        self.assertTrue(all(h['end_frame']-h['start_frame']<100 for h in hits))
