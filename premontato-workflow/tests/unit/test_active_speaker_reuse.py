import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parents[2] / 'worker'))
import active_speaker as asd
from cache import cache_key, write_cache


def old_crop(frame, cx, cy, side):
    pad = round(side * 2)
    padded = cv2.copyMakeBorder(frame, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=(110, 110, 110))
    return padded[max(0, int(cy-side+pad)):int(cy+side*1.8+pad),
                  max(0, int(cx-side*1.4+pad)):int(cx+side*1.4+pad)]


class PreprocessingTests(unittest.TestCase):
    def test_crop_pixels_match_original_at_edges_fractional_and_outside_bounds(self):
        rng = np.random.default_rng(23)
        frame = rng.integers(0, 256, (83, 127, 3), dtype=np.uint8)
        cases = [(60, 40, 10), (0, 0, 15), (127, 83, 30), (-2.7, -5.2, 9.5),
                 (150, 100, 50), (-80, -60, 7), (60, 40, 200), (40, 20, 0)]
        cases += list(zip(rng.uniform(-160, 260, 150), rng.uniform(-130, 200, 150), rng.uniform(.1, 100, 150)))
        for coords in cases:
            with self.subTest(coords=coords):
                expected = old_crop(frame, *coords)
                actual = asd._crop_face(frame, *coords)
                np.testing.assert_array_equal(actual, expected)
                if actual.size:
                    np.testing.assert_array_equal(cv2.resize(actual, (224, 224)), cv2.resize(expected, (224, 224)))

    def test_internal_crop_can_reuse_frame_memory(self):
        frame = np.zeros((540, 960, 3), np.uint8)
        self.assertTrue(np.shares_memory(asd._crop_face(frame, 400, 250, 30), frame))

    def test_smoothing_matches_original_exactly_for_short_and_full_samples(self):
        rng = np.random.default_rng(5)
        for length in [1, 2, 12, 13, 25, 50]:
            coords = rng.normal(size=(length, 3)) * 300
            expected = np.stack([np.median(np.pad(coords[:, j], (6, 6), mode='edge')[k:k+13])
                                 for k in range(length) for j in range(3)]).reshape(length, 3)
            np.testing.assert_array_equal(asd._smooth_coords(coords), expected)


class Detector:
    def __init__(self):
        self.calls = 0
        self.has_face = True

    def detect(self, image):
        self.calls += 1
        return None, np.array([[220., 100., 100., 120.]], np.float32) if self.has_face else None


class Model:
    def __init__(self):
        self.calls = 0
        self.fail = False
        self.scores = np.array([3.] * 15 + [-2.] * 20 + [3.] * 15, dtype=np.float32)

    def run(self, outputs, inputs):
        if self.fail:
            raise RuntimeError('inference failed')
        position = self.calls % 3
        self.calls += 1
        return [self.scores.copy() if position == 0 else self.scores[(position-1)*25:position*25].copy()]


class SampleReuseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = np.zeros((50, 540, 960, 3), np.uint8).tobytes()

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.file = self.root / 'source.mp4'
        self.file.write_bytes(b'fixture')
        self.source = {'path': str(self.file), 'duration_frames': 1000, 'fps': 25}
        self.analyzer = self.new_analyzer()
        self.decoder = patch('active_speaker.subprocess.check_output', return_value=self.raw).start()
        patch('local_audio.load_pcm16', return_value=(np.zeros(640000, dtype=np.int16), {'cache_hit': True})).start()
        self.addCleanup(patch.stopall)

    def new_analyzer(self):
        value = asd.ActiveSpeaker.__new__(asd.ActiveSpeaker)
        value.ffmpeg = 'ffmpeg'
        value.cache = self.root / 'active-speaker'
        value.detector = Detector()
        value.session = Model()
        return value

    def test_equivalent_window_keeps_distinct_interval_classifications(self):
        first = self.analyzer.analyze(self.source, 100, 150)
        second = self.analyzer.analyze(self.source, 115, 135)
        self.assertEqual(first['status'], 'visible')
        self.assertEqual(second['status'], 'absent')
        self.assertEqual(self.decoder.call_count, 1)
        self.assertEqual(self.analyzer.detector.calls, 11)
        self.assertEqual(self.analyzer.session.calls, 3)
        self.assertFalse(second['cache_hit'])
        self.assertTrue(second['sample_cache_hit'])
        self.assertEqual(second['stage_seconds'], {})
        self.assertEqual(second['work']['inference_calls'], 0)
        self.assertEqual(first['work']['inference_calls'], 3)
        self.assertEqual(first['faces'][0]['mean'], 1.)
        self.assertEqual(second['faces'][0]['mean'], -2.)
        self.assertEqual(first['faces'][0]['box'], second['faces'][0]['box'])

    def test_persistent_sample_reuse_survives_new_analyzer_and_does_not_leak_mutations(self):
        result = self.analyzer.analyze(self.source, 100, 150)
        result['faces'][0]['box'][0] = -999
        result['faces'][0]['mean'] = -999
        other = self.new_analyzer()
        result = other.analyze(self.source, 115, 135)
        self.assertEqual(result['status'], 'absent')
        self.assertNotEqual(result['faces'][0]['box'][0], -999)
        self.assertEqual(other.session.calls, 0)
        self.assertEqual(other.detector.calls, 0)
        self.assertEqual(self.decoder.call_count, 1)

    def test_existing_v3_interval_cache_remains_usable_with_fresh_latency(self):
        stat = self.file.stat()
        fingerprint = {'path': str(self.file.resolve()), 'size': stat.st_size, 'mtime': stat.st_mtime_ns}
        options = {'offset': 100, 'duration': 2, 'start': 100, 'end': 150, 'fps': 25., 'model': asd.MODEL_SHA256}
        legacy = {'status': 'visible', 'faces': [], 'seconds': 99., 'method': 'light-asd-talkset-track5-pcm-v3'}
        write_cache(self.analyzer.cache, cache_key(fingerprint, 'light-asd-talkset-track5-pcm-v3', options), legacy)
        result = self.analyzer.analyze(self.source, 100, 150)
        self.assertTrue(result['cache_hit'])
        self.assertEqual(result['seconds'], 99.)
        self.assertIn('elapsed_seconds', result)
        self.assertEqual(result['stage_seconds'], {})
        self.assertEqual(result['work']['decoded_samples'], 0)
        self.assertEqual(self.decoder.call_count, 0)

    def test_source_change_and_different_window_require_new_inference(self):
        self.analyzer.analyze(self.source, 100, 150)
        self.analyzer.analyze(self.source, 200, 250)
        self.assertEqual(self.decoder.call_count, 2)
        self.file.write_bytes(b'changed source')
        self.analyzer.analyze(self.source, 115, 135)
        self.assertEqual(self.decoder.call_count, 3)
        self.assertEqual(self.analyzer.session.calls, 9)

    def test_bad_sample_scores_are_recomputed(self):
        self.analyzer.analyze(self.source, 100, 150)
        sample_file = next((self.analyzer.cache / 'samples').glob('*.json'))
        for i, scores in enumerate(([1.], [float('nan')] * 50)):
            with self.subTest(invalid='length' if i == 0 else 'finite'):
                record = json.loads(sample_file.read_text())
                record['value']['tracks'][0]['scores'] = scores
                sample_file.write_text(json.dumps(record))
                result = self.analyzer.analyze(self.source, 115+i, 135-i)
                self.assertEqual(result['status'], 'absent')
                self.assertFalse(result['sample_cache_hit'])
                self.assertEqual(self.decoder.call_count, 2+i)

    def test_inference_failure_is_retried_and_never_cached_as_unknown(self):
        self.analyzer.session.fail = True
        with self.assertRaisesRegex(RuntimeError, 'inference failed'):
            self.analyzer.analyze(self.source, 100, 150)
        self.assertEqual(list(self.analyzer.cache.rglob('*.json')), [])
        self.analyzer.session.fail = False
        self.assertEqual(self.analyzer.analyze(self.source, 100, 150)['status'], 'visible')
        self.assertEqual(self.decoder.call_count, 2)

    def test_rounded_empty_request_keeps_the_early_exit_before_inference(self):
        result = self.analyzer.analyze({**self.source, 'fps': 120}, 1, 2)
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(result['reason'], 'nessun campione nella battuta')
        self.assertEqual(self.analyzer.session.calls, 0)
        self.assertEqual(list((self.analyzer.cache / 'samples').glob('*.json')), [])

    def test_no_face_sample_can_be_reused_without_inference(self):
        self.analyzer.detector.has_face = False
        self.assertEqual(self.analyzer.analyze(self.source, 100, 150)['status'], 'unknown')
        self.assertEqual(self.analyzer.analyze(self.source, 115, 135)['status'], 'unknown')
        self.assertEqual(self.decoder.call_count, 1)
        self.assertEqual(self.analyzer.session.calls, 0)

    def test_warm_interval_reports_zero_new_work(self):
        self.analyzer.analyze(self.source, 100, 150)
        result = self.analyzer.analyze(self.source, 100, 150)
        self.assertTrue(result['cache_hit'])
        self.assertFalse(result['sample_cache_hit'])
        self.assertEqual(result['stage_seconds'], {})
        self.assertTrue(all(value == 0 for value in result['work'].values()))


if __name__ == '__main__':
    unittest.main()
