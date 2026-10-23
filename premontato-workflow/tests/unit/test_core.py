import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "worker"))

from script_parser import parse_script
from transcript_align import align_occurrences, propose_take_segments, propose_take_segments_for_beats
from edit_selector import choose_latest_complete


class CoreTests(unittest.TestCase):
    def test_parser_reads_pdf_layout_scene_headings_and_joins_wrapped_dialogue(self):
        parsed = parse_script(
            "PARE BRUTTO\nCopyright 2026\n"
            "SCENA 01 INT. SALOTTO DI CASA - SERA\n\n"
            "CLAUDIO e FABRIZIO sono sul divano\n\n"
            "                               CLAUDIO\n"
            "                Zenzero e limone o cannella e frutti\n"
            "                rossi?\n\n"
            "                               FABRIZIO\n"
            "                Cannella e frutti rossi\n\n"
            "SCENA 01 BIS INT. SALOTTO - SERA\n"
            "                               FABRIZIO\n"
            "                Nooooo!"
        )
        self.assertEqual([scene["heading"] for scene in parsed["scenes"]], [
            "SCENA 01 INT. SALOTTO DI CASA - SERA", "SCENA 01 BIS INT. SALOTTO - SERA"
        ])
        first = parsed["scenes"][0]["beats"]
        self.assertEqual([(beat["kind"], beat["character"], beat["text"]) for beat in first], [
            ("action", None, "CLAUDIO e FABRIZIO sono sul divano"),
            ("dialogue", "CLAUDIO", "Zenzero e limone o cannella e frutti rossi?"),
            ("dialogue", "FABRIZIO", "Cannella e frutti rossi"),
        ])

    def test_scene_selector_uses_multiple_distinct_script_lines_and_rejects_generic_match(self):
        from transcript_align import select_scene
        scenes = [
            {"scene_id": "scene-a", "heading": "SCENA 01", "beats": [
                {"kind": "dialogue", "text": "Zenzero e limone o cannella e frutti rossi?"},
                {"kind": "dialogue", "text": "Lilly e il vagabondo o Oliver e company?"},
                {"kind": "dialogue", "text": "Non possiamo non andare, pare brutto!"},
            ]},
            {"scene_id": "scene-b", "heading": "SCENA 04", "beats": [
                {"kind": "dialogue", "text": "Pare brutto"},
                {"kind": "dialogue", "text": "Pare brutto"},
            ]},
        ]
        transcript = [
            {"text": "zenzero e limone o cannella e frutti rossi"},
            {"text": "Lilly e il vagabondo o Oliver e company"},
            {"text": "non possiamo non andare, pare brutto"},
        ]
        result = select_scene(scenes, transcript)
        self.assertEqual(result["scene"]["scene_id"], "scene-a")
        ambiguous = select_scene(scenes, [{"text": "pare brutto"}])
        self.assertIsNone(ambiguous["scene"])

    def test_scene_selector_handles_resolve_long_transcription_segments(self):
        from transcript_align import select_scene
        scenes = [
            {"scene_id": "salotto", "heading": "SCENA 01", "beats": [
                {"kind": "dialogue", "text": "Zenzero e limone o cannella e frutti rossi?"},
                {"kind": "dialogue", "text": "Oliver e company?"},
            ]},
            {"scene_id": "casa", "heading": "SCENA 05 INT. CASA RAGAZZA", "beats": [
                {"kind": "dialogue", "text": "Grazie eh, mi avete salvato."},
                {"kind": "dialogue", "text": "Per me potete stare quanto volete."},
                {"kind": "dialogue", "text": "Il divano letto è pieno, c'è rimasto solo il mio letto matrimoniale."},
                {"kind": "dialogue", "text": "Io posso dormire anche per terra."},
            ]},
        ]
        transcript = [
            {"text": "Grazie, mi avete salvata. Che scherzi, grazie a te. Tranquillo davvero. A me fa super piacere, potete rimanere quanto volete. Unica cosa, come vedrai, il divano letto è pieno."},
            {"text": "È rimasto solo il mio letto in camera mia, dove magari potremmo dormire insieme."},
            {"text": "Ma io dormo tranquillamente anche sul tavolo. Ok, buonanotte."},
        ]
        result = select_scene(scenes, transcript)
        self.assertEqual(result["scene"]["scene_id"], "casa")
        self.assertGreaterEqual(result["confidence"], 0.6)

    def test_fountain_parser_keeps_beats_and_parentheticals(self):
        parsed = parse_script("INT. CUCINA - GIORNO\n\nLUCA\nNon dovevi farlo.\n\n(Micro pausa)\n\nMARTA\nL'ho già fatto.")
        self.assertEqual(len(parsed["scenes"]), 1)
        beats = parsed["scenes"][0]["beats"]
        self.assertEqual([b["kind"] for b in beats], ["dialogue", "parenthetical", "dialogue"])
        self.assertEqual(beats[0]["character"], "LUCA")


    def test_alignment_keeps_repeated_occurrences_and_only_suggests_unconfirmed_splits(self):
        beats = [{"beat_id": "b1", "order": 0, "text": "ciao"}, {"beat_id": "b2", "order": 1, "text": "come va"}]
        segments = [
            {"segment_id": "a", "start_frame": 10, "end_frame": 20, "text": "ciao"},
            {"segment_id": "b", "start_frame": 30, "end_frame": 40, "text": "come va"},
            {"segment_id": "c", "start_frame": 100, "end_frame": 110, "text": "ciao"},
            {"segment_id": "d", "start_frame": 120, "end_frame": 130, "text": "come va"},
        ]
        aligned = align_occurrences(beats, segments)
        self.assertEqual(len(aligned["matches"]), 4)
        takes = propose_take_segments({"media_id": "m1", "duration_frames": 200}, segments, 25, gap_seconds=1)
        self.assertEqual(len(takes), 2)
        self.assertTrue(all(not take["confirmed"] and take["boundary_source"] == "suggested" for take in takes))


    def test_latest_complete_take_wins_and_fallback_is_explicit(self):
        takes = [
            {"take_id": "t1", "take_index": 1, "complete": True, "score": 0.7},
            {"take_id": "t2", "take_index": 2, "complete": False, "score": 1.0},
            {"take_id": "t3", "take_index": 3, "complete": True, "score": 0.6},
        ]
        result = choose_latest_complete(takes)
        self.assertEqual(result["selected"]["take_id"], "t3")
        self.assertFalse(result["fallback"])
        self.assertEqual(len(result["alternatives"]), 2)

    def test_multiple_performances_in_one_file_only_split_when_script_order_restarts(self):
        beats = [{"beat_id": f"b{i}", "order": i, "kind": "dialogue", "text": text} for i, text in enumerate(["ciao", "come stai", "bene"])]
        transcript = [
            {"segment_id": str(i), "start_frame": i * 20, "end_frame": i * 20 + 10, "text": text}
            for i, text in enumerate(["ciao", "come stai", "bene", "ciao", "come stai", "bene"])
        ]
        takes = propose_take_segments_for_beats({"media_id": "m", "duration_frames": 200}, beats, transcript, 25)
        self.assertEqual(len(takes), 2)
        self.assertFalse(any(take["confirmed"] for take in takes))
        self.assertLess(takes[0]["end_frame"], takes[1]["start_frame"] + 1)


if __name__ == "__main__":
    unittest.main()

