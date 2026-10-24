import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[2] / "worker"))
from shot_analyzer import apply_manual_overrides, classify_face_heights, classify_face_areas


class ShotAnalyzerTests(unittest.TestCase):
    def test_face_area_maps_to_advisory_shot_size(self):
        self.assertEqual(classify_face_areas([0.22])[0], "close")
        self.assertEqual(classify_face_areas([0.10])[0], "medium")
        self.assertEqual(classify_face_areas([])[0], "unknown")

    def test_face_height_provides_useful_scale_for_small_faces(self):
        # The user's cached sample had a face ~15% of frame height but only
        # ~1.25% of total frame area; it should not fall back to wide.
        self.assertEqual(classify_face_heights([0.149])[0], "medium")
        self.assertEqual(classify_face_heights([0.32])[0], "close")
        self.assertEqual(classify_face_heights([0.08])[0], "wide")

    def test_manual_override_wins_only_for_same_fingerprint(self):
        segment = {"media_id": "m", "start_frame": 0, "end_frame": 50, "shot_size": "unknown", "source": "automatic"}
        override = {"media_id": "m", "fingerprint": "fp", "start_frame": 10, "end_frame": 40, "shot_size": "detail", "visible_subjects": ["MARTA"]}
        self.assertEqual(apply_manual_overrides([segment], [override], "fp")[0]["shot_size"], "detail")
        self.assertEqual(apply_manual_overrides([segment], [override], "changed")[0]["shot_size"], "unknown")


if __name__ == "__main__": unittest.main()
