import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"worker"))
from transcript_align import select_scene
def scene(id,heading,lines):
 return {"scene_id":id,"heading":heading,"beats":[{"beat_id":id+str(i),"scene_id":id,"kind":"dialogue","character":"P","text":line,"order":i} for i,line in enumerate(lines)]}
class SequenceSelectionTests(unittest.TestCase):
 def test_repeated_intercut_locations_form_one_supported_sequence(self):
  scenes=[scene("a","INT. CASA UNO - GIORNO",["come procede il lavoro nuovo"]),scene("b","INT. CASA DUE - GIORNO",["ho trovato finalmente una casa"]),scene("c","INT. CASA UNO - GIORNO",["partiamo domani per la montagna"]),scene("d","INT. CASA DUE - GIORNO",["preparo subito tutte le valigie"]),scene("other","INT. UFFICIO - GIORNO",["oggi dobbiamo discutere il contratto"])]
  out=select_scene(scenes,[{"text":line,"segment_id":str(i)} for i,line in enumerate(["come procede il lavoro nuovo","ho trovato finalmente una casa","partiamo domani per la montagna","preparo subito tutte le valigie"])])
  self.assertEqual(out["scene"]["source_scene_ids"],["a","b","c","d"])
  self.assertEqual(len(out["scene"]["beats"]),4)
 def test_unrelated_locations_are_not_merged(self):
  out=select_scene([scene("a","INT. UFFICIO - GIORNO",["restiamo qui fino a domani"]),scene("b","EST. MARE - GIORNO",["restiamo qui fino a domani"])],[{"text":"restiamo qui fino a domani"}])
  self.assertIsNone(out["scene"])
if __name__=="__main__":unittest.main()
