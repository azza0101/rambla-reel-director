import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[2]


class ProtocolTests(unittest.TestCase):
    def test_worker_answers_ping_and_reports_unknown_actions_as_jsonl(self):
        requests = [
            {"protocol": 1, "request_id": "one", "action": "ping", "payload": {}},
            {"protocol": 1, "request_id": "two", "action": "shell", "payload": {}},
        ]
        run = subprocess.run([sys.executable, str(ROOT / "worker" / "protocol.py")],
                             input="\n".join(map(json.dumps, requests)) + "\n", text=True, capture_output=True, check=True)
        rows = [json.loads(line) for line in run.stdout.splitlines()]
        self.assertEqual(rows[0]["result"], {"ready": True})
        self.assertEqual(rows[1]["status"], "error")
        self.assertEqual(len(rows), 2)

    def test_scene_plan_uses_latest_take_per_line_and_keeps_earlier_alternatives(self):
        request = {"protocol": 1, "request_id": "plan", "action": "build_plan", "payload": {
            "fps": 25,
            "beats": [{"beat_id": "a", "scene_id": "s", "kind": "dialogue", "text": "primo"}, {"beat_id": "b", "scene_id": "s", "kind": "dialogue", "text": "secondo"}],
            "sources": [
                {"take_id": "take1", "media_id": "m1", "take_index": 1, "duration_frames": 500,
                 "segments": [{"start_frame": 30, "end_frame": 50, "text": "primo"}, {"start_frame": 90, "end_frame": 120, "text": "secondo"}]},
                {"take_id": "take2", "media_id": "m2", "take_index": 2, "duration_frames": 500,
                 "segments": [{"start_frame": 10, "end_frame": 30, "text": "primo"}]},
            ]}}
        from protocol import dispatch
        plan = dispatch(request)["result"]
        self.assertEqual([row["take_id"] for row in plan["decisions"]], ["take2", "take1"])
        self.assertTrue(plan["decisions"][0]["alternatives"])

    def test_matches_script_line_inside_long_resolve_turn_and_uses_word_timecodes(self):
        request = {"protocol": 1, "request_id": "phrase", "action": "build_plan", "payload": {
            "fps": 25,
            "beats": [{"beat_id": "cafone", "scene_id": "s", "kind": "dialogue", "text": "Fabri, ma sei un cafone maleducato?"}],
            "sources": [{"take_id": "take1", "media_id": "m1", "take_index": 1, "duration_frames": 500,
                         "segments": [{"start_frame": 10, "end_frame": 210, "text": "Tu sei veramente un cafone maleducato e non ascolti mai nessuno.",
                                       "words": [
                                           {"text": "Tu", "start_frame": 10, "end_frame": 13},
                                           {"text": "sei", "start_frame": 14, "end_frame": 18},
                                           {"text": "veramente", "start_frame": 19, "end_frame": 30},
                                           {"text": "un", "start_frame": 31, "end_frame": 34},
                                           {"text": "cafone", "start_frame": 35, "end_frame": 46},
                                           {"text": "maleducato", "start_frame": 47, "end_frame": 64},
                                           {"text": "e", "start_frame": 65, "end_frame": 67},
                                           {"text": "non", "start_frame": 68, "end_frame": 72},
                                           {"text": "ascolti", "start_frame": 73, "end_frame": 82},
                                           {"text": "mai", "start_frame": 83, "end_frame": 87},
                                           {"text": "nessuno", "start_frame": 88, "end_frame": 100}
                                       ]}]}]}}
        from protocol import dispatch
        plan = dispatch(request)["result"]
        self.assertEqual(plan["unmatched_beats"], [])
        match = plan["decisions"][0]
        self.assertEqual(match["matched_text"], "sei veramente un cafone maleducato")
        # Handles stop before adjacent words ("Tu" and "e non"), rather than repeating them.
        self.assertEqual((match["start_frame"], match["end_frame"]), (13, 65))

    def test_plan_alternates_verified_scales_when_phrase_scores_are_equivalent(self):
        from protocol import dispatch
        request = {"protocol": 1, "request_id": "coverage", "action": "build_plan", "payload": {
            "fps": 25,
            "beats": [{"beat_id": "a", "scene_id": "s", "kind": "dialogue", "text": "prima battuta"},
                      {"beat_id": "b", "scene_id": "s", "kind": "dialogue", "text": "seconda battuta"}],
            "sources": [
                {"take_id": "close", "media_id": "m1", "take_index": 1, "duration_frames": 300,
                 "segments": [{"start_frame": 10, "end_frame": 20, "text": "prima battuta"}, {"start_frame": 50, "end_frame": 60, "text": "seconda battuta"}]},
                {"take_id": "master", "media_id": "m2", "take_index": 2, "duration_frames": 300,
                 "segments": [{"start_frame": 10, "end_frame": 20, "text": "prima battuta"}, {"start_frame": 50, "end_frame": 60, "text": "seconda battuta"}]},
                {"take_id": "unknown", "media_id": "m3", "take_index": 3, "duration_frames": 300,
                 "segments": [{"start_frame": 10, "end_frame": 20, "text": "prima battuta"}, {"start_frame": 50, "end_frame": 60, "text": "seconda battuta"}]}
            ],
            "shots": [{"media_id": "m1", "start_frame": 0, "end_frame": 300, "shot_size": "close", "confidence": 0.8},
                      {"media_id": "m2", "start_frame": 0, "end_frame": 300, "shot_size": "wide", "confidence": 0.7},
                      {"media_id": "m3", "start_frame": 0, "end_frame": 300, "shot_size": "unknown", "confidence": 0.0}]
        }}
        plan = dispatch(request)["result"]
        self.assertEqual([row["take_id"] for row in plan["decisions"]], ["master", "close"])
        self.assertEqual([row["shot_size"] for row in plan["decisions"]], ["wide", "close"])

    def test_parenthetical_is_not_treated_as_unmatched_spoken_line(self):
        request = {"protocol": 1, "request_id": "direction", "action": "build_plan", "payload": {
            "fps": 25, "beats": [{"beat_id": "a", "scene_id": "s", "kind": "dialogue", "text": "ciao"},
                                   {"beat_id": "b", "scene_id": "s", "kind": "parenthetical", "text": "(pausa)"}],
            "sources": [{"take_id": "t", "media_id": "m", "take_index": 1, "duration_frames": 300,
                         "segments": [{"start_frame": 20, "end_frame": 30, "text": "ciao"}]}]}}
        from protocol import dispatch
        plan = dispatch(request)["result"]
        self.assertEqual(plan["unmatched_beats"], [])
        self.assertEqual([row["beat_id"] for row in plan["decisions"]], ["a"])

    def test_plan_warning_matches_whether_shots_were_analyzed(self):
        from protocol import dispatch
        base = {"protocol": 1, "request_id": "shots", "action": "build_plan", "payload": {
            "fps": 25,
            "beats": [{"beat_id": "a", "scene_id": "s", "kind": "dialogue", "text": "primo"}],
            "sources": [{"take_id": "t", "media_id": "m", "take_index": 1, "duration_frames": 100,
                         "segments": [{"start_frame": 20, "end_frame": 30, "text": "primo"}]}]}}
        without_shots = dispatch(base)["result"]
        self.assertTrue(any("inquadratura" in warning.lower() and "nessuna" in warning.lower()
                            for warning in without_shots["warnings"]))
        with_shots = {**base, "request_id": "shots-done", "payload": {**base["payload"], "shots": [
            {"media_id": "m", "start_frame": 0, "end_frame": 100, "shot_size": "close", "confidence": 0.8}]}}
        result = dispatch(with_shots)["result"]
        self.assertEqual(result["decisions"][0]["shot_size"], "close")
        self.assertTrue(any("stime automatiche" in warning.lower() for warning in result["warnings"]))
        self.assertFalse(any("non sono ancora state analizzate" in warning.lower() for warning in result["warnings"]))


if __name__ == "__main__":
    unittest.main()
