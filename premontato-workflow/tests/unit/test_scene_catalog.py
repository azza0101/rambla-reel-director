import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'worker'))
from scene_catalog import catalog_scenes
SCENES=[{'scene_id':'s1','heading':'INT CASA','beats':[{'beat_id':'b1','kind':'dialogue','text':'Ho nascosto le chiavi della macchina nel frigorifero.'}]},{'scene_id':'s2','heading':'EXT MARE','beats':[{'beat_id':'b2','kind':'dialogue','text':'La barca rossa sta affondando vicino al porto.'}]}]
def seg(text,start,end):return {'text':text,'start_frame':start,'end_frame':end,'words':[{'text':text,'start_frame':start,'end_frame':end}]}
def run(rows,scenes=SCENES):return catalog_scenes({'scenes':scenes,'sources':[{'media_id':'m','fps':25,'duration_frames':1000,'segments':rows}],'settings':{'semantic':False}})
class CatalogTest(unittest.TestCase):
 def test_two_scenes_inside_one_resolve_segment(self):
  words=[]
  for i,text in enumerate([SCENES[0]['beats'][0]['text'],SCENES[1]['beats'][0]['text']]):
   for j,w in enumerate(text.split()):words.append({'text':w,'start_frame':i*200+j*10,'end_frame':i*200+(j+1)*10})
  result=run([{'text':' '.join(w['text'] for w in words),'start_frame':0,'end_frame':400,'words':words}])
  self.assertEqual([m['scene_id'] for m in result['memberships']],['s1','s2'])
  self.assertEqual(result['memberships'][1]['source_start_frame'],200)
 def test_multi_scene_and_repeat_take(self):
  rows=[seg(SCENES[0]['beats'][0]['text'],10,90),seg(SCENES[0]['beats'][0]['text'],120,200),seg(SCENES[1]['beats'][0]['text'],250,350),seg(SCENES[0]['beats'][0]['text'],450,550)];r=run(rows)
  self.assertEqual([m['scene_id'] for m in r['memberships']],['s1','s1','s2','s1']);self.assertEqual(r['memberships'][2]['source_start_frame'],250);self.assertEqual(r,run(rows))
 def test_generic_empty_unassigned(self):
  self.assertEqual(run([seg('Ciao sì no Sandro azione',10,50)])['memberships'],[]);self.assertEqual(run([])['source_status']['m'],'missing')
 def test_shared_line_review(self):
  r=run([seg(SCENES[0]['beats'][0]['text'],10,100)],[SCENES[0],{**SCENES[1],'beats':SCENES[0]['beats']}]);self.assertNotEqual(r['memberships'][0]['status'],'auto_ready')
 def test_invalid_time_rejected(self):
  r=run([seg(SCENES[0]['beats'][0]['text'],-20,50)]);self.assertFalse(r['memberships']);self.assertTrue(r['warnings'])
 def test_overlapping_segments_never_produce_overlapping_memberships(self):
  result=run([seg(SCENES[0]['beats'][0]['text'],10,100),seg(SCENES[1]['beats'][0]['text'],80,180)])
  rows=result['memberships'];self.assertTrue(all(a['source_end_frame']<=b['source_start_frame'] for a,b in zip(rows,rows[1:])))
 def test_paraphrase_can_use_existing_encoder(self):
  import numpy as np
  class Encoder:
   def encode(self,texts):return np.array([[0.,1.] if 'barca' in t else [1.,0.] for t in texts])
  source={'media_id':'m','fps':25,'duration_frames':1000,'segments':[seg('Le chiavi sono state messe dentro al frigo per nasconderle.',10,80)]}
  r=catalog_scenes({'scenes':SCENES,'sources':[source]},encoder=Encoder());self.assertEqual(r['memberships'][0]['scene_id'],'s1');self.assertGreater(r['memberships'][0]['evidence'][0]['semantic_score'],.9)
 def test_shared_sentence_uses_neighboring_anchors_but_stays_review(self):
  shared='Questa situazione mi sembra davvero molto difficile.'
  scene={'scene_id':'s1','heading':'INT CASA','beats':[SCENES[0]['beats'][0],{'kind':'dialogue','beat_id':'shared1','text':shared},{'kind':'dialogue','beat_id':'last','text':'Adesso prendi il frigorifero e portalo in garage.'}]}
  other={'scene_id':'s2','heading':'EXT MARE','beats':[{'kind':'dialogue','beat_id':'shared2','text':shared}]}
  r=run([seg(scene['beats'][0]['text'],0,90),seg(shared,100,190),seg(scene['beats'][2]['text'],200,290)],[scene,other]);self.assertTrue(all(m['scene_id']=='s1' for m in r['memberships']));self.assertTrue(any(m['status']=='review' for m in r['memberships']))
 def test_context_keeps_the_score_of_the_selected_scene(self):
  shared='Questa situazione mi sembra davvero molto difficile oggi pomeriggio.'
  scenes=[{'scene_id':'s1','beats':[SCENES[0]['beats'][0],{'beat_id':'shared1','kind':'dialogue','text':shared.replace('situazione','situazione particolare')},{'beat_id':'last','kind':'dialogue','text':'Portiamo il frigorifero giallo dentro il garage.'}]},{'scene_id':'s2','beats':[{'beat_id':'shared2','kind':'dialogue','text':shared}]}]
  r=run([seg(scenes[0]['beats'][0]['text'],0,90),seg(shared,100,190),seg(scenes[0]['beats'][2]['text'],200,290)],scenes)
  evidence=next(e for m in r['memberships'] for e in m['evidence'] if e.get('beat_id')=='shared1');self.assertLess(evidence['score'],1)
if __name__=='__main__':unittest.main()
