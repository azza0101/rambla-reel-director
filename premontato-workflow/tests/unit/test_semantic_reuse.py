import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[2] / 'worker'))
import transcript_align
from staged_dialogue import build_staged


class SemanticReuseTests(unittest.TestCase):
    def setUp(self):
        text = 'Aspettami qui prima di uscire.'
        words = [{'text': word, 'start_frame': 10 + i * 10, 'end_frame': 19 + i * 10}
                 for i, word in enumerate(text.split())]
        self.payload = {
            'fps': 25,
            'beats': [{'beat_id': 'b', 'kind': 'dialogue', 'character': 'ALICE', 'text': text}],
            'sources': [{'media_id': 'm', 'take_id': 't', 'duration_frames': 100,
                         'segments': [{'text': text, 'start_frame': 10, 'end_frame': 59, 'words': words}]}],
            'shots': [{'media_id': 'm', 'start_frame': 0, 'end_frame': 100,
                       'shot_size': 'wide', 'confidence': 1}],
            'classifications': {'t': {'S0': '1/P1'}},
        }
        self.encoder_class = transcript_align.LocalSemanticEncoder
        self.encoders = []

    def encoder(self):
        # Replace model loading/inference only; use the real embedding cache and planners.
        encoder = self.encoder_class.__new__(self.encoder_class)
        encoder.cache = {}
        token = SimpleNamespace(ids=[1], attention_mask=[1], type_ids=[0])
        encoder.tokenizer = SimpleNamespace(encode_batch=lambda texts: [token for _ in texts])
        encoder.model = Mock()
        encoder.model.get_inputs.return_value = [SimpleNamespace(name='input_ids')]
        encoder.model.run.side_effect = lambda _, inputs: [
            np.tile(np.array([[1., 0.]], dtype=np.float32), (len(inputs['input_ids']), 1))]
        self.encoders.append(encoder)
        return encoder

    def local_hits(self):
        return transcript_align.semantic_scene_hits(self.payload['beats'], self.payload['sources'], 25)

    def test_local_and_staged_plans_share_encoder_and_cached_embeddings(self):
        original = copy.deepcopy(self.payload)
        with patch.object(transcript_align, '_SEMANTIC_ENCODER', None), \
                patch.object(transcript_align, 'LocalSemanticEncoder', side_effect=self.encoder) as factory:
            hits = self.local_hits()
            first = build_staged(self.payload)
            inference_count = sum(encoder.model.run.call_count for encoder in self.encoders)
            second = build_staged(self.payload)
            self.assertEqual(factory.call_count, 1)
            self.assertEqual(sum(encoder.model.run.call_count for encoder in self.encoders), inference_count)
        self.assertIn(('t', 'b'), hits)
        self.assertEqual({k:v for k,v in first.items() if k!='performance'}, {k:v for k,v in second.items() if k!='performance'})
        self.assertEqual(first['decisions'][0]['matched_start_frame'], 10)
        self.assertEqual(first['decisions'][0]['matched_end_frame'], 59)
        self.assertEqual(self.payload, original)

    def test_initialization_failure_is_not_cached_and_other_planner_can_retry(self):
        attempts = 0

        def initialize():
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError('Modello semantico danneggiato')
            return self.encoder()

        with patch.object(transcript_align, '_SEMANTIC_ENCODER', None), \
                patch.object(transcript_align, 'LocalSemanticEncoder', side_effect=initialize):
            with self.assertRaisesRegex(RuntimeError, 'danneggiato'):
                self.local_hits()
            self.assertIsNone(transcript_align._SEMANTIC_ENCODER)
            self.assertEqual(build_staged(self.payload)['engine'], 'groq_staged_v1')
            self.assertIn(('t', 'b'), self.local_hits())
            self.assertEqual(attempts, 2)


if __name__ == '__main__':
    unittest.main()
