import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "worker"))
from cache import cache_key, get_cache, get_or_compute, write_cache


class CacheTests(unittest.TestCase):
    def test_cache_invalidates_when_options_change(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            key = cache_key("media", "v1", {"fps": 25})
            write_cache(directory, key, {"ok": True})
            self.assertEqual(get_cache(directory, "media", "v1", {"fps": 25}), {"ok": True})
            self.assertIsNone(get_cache(directory, "media", "v1", {"fps": 24}))

    def test_get_or_compute_reuses_cached_analysis(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            calls = []
            first, hit1 = get_or_compute(directory, "media-fingerprint", "vision-1", {}, lambda: calls.append(1) or ["close"])
            second, hit2 = get_or_compute(directory, "media-fingerprint", "vision-1", {}, lambda: calls.append(2) or ["wide"])
            self.assertEqual(first, second)
            self.assertFalse(hit1)
            self.assertTrue(hit2)
            self.assertEqual(calls, [1])


if __name__ == "__main__":
    unittest.main()
