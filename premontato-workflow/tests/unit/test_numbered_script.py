import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[2]/'worker'))
from script_parser import parse_script
class NumberedScriptTests(unittest.TestCase):
 def test_period_numbered_scenes_skip_preamble_and_preserve_left_aligned_dialogue(self):
  text='TRAILER V2\n                              Versione 12 marzo\nProtagonisti\nAda e Bruno\n\nScena 1. Casa Ada. Interno Notte.\nAda cerca la chiave.\n\nLEI (preoccupata)\nHai trovato la chiave del laboratorio?\nServe subito.\n\nScena 2. Officina. Esterno Giorno.\nLUI\nLa chiave è sotto il vaso blu.\n'
  scenes=parse_script(text)['scenes'];self.assertEqual(len(scenes),2);self.assertEqual(scenes[0]['heading'],'Scena 1. Casa Ada. Interno Notte.');self.assertEqual([(b['character'],b['text']) for b in scenes[0]['beats'] if b['kind']=='dialogue'],[('LEI','Hai trovato la chiave del laboratorio? Serve subito.')]);self.assertFalse(any('Protagonisti' in b['text'] for s in scenes for b in s['beats']))
 def test_mixed_dialogue_alignment_uses_each_speaker_indent(self):
  scenes=parse_script('SCENA 1\n                              ADA\n                Arrivo dalla biblioteca.\n\nSCENA 2\nBRUNO\nIl cancello è ancora chiuso.')['scenes'];self.assertEqual(scenes[1]['beats'][0]['kind'],'dialogue');self.assertEqual(scenes[1]['beats'][0]['character'],'BRUNO')
 def test_supported_scene_number_punctuation(self):
  for punctuation in ['.',':',' -',' –',' —',')']:
   with self.subTest(punctuation=punctuation):self.assertEqual(len(parse_script('Scena 1'+punctuation+' Casa\nLUI\nPorta il quaderno verde.\nScena 2'+punctuation+' Bosco\nLEI\nLo zaino è vicino al fiume.')['scenes']),2)

class SpeakerTurnBoundaryTests(unittest.TestCase):
 def test_same_speaker_cue_starts_a_new_turn(self):
  beats=parse_script('SCENA 1\nADA\nUna frase.\nADA (sorridendo)\nUna seconda frase.')['scenes'][0]['beats']
  self.assertEqual([b['text'] for b in beats],['Una frase.','Una seconda frase.'])
