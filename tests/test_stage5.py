import unittest
import tempfile
from dataclasses import replace
from pathlib import Path
import numpy as np
from hc_falcon.greedy import rank, normalize
from hc_falcon.preprocess import preprocess
from hc_falcon.semantic import kernel, masked_mean
from hc_falcon.semantic import cached_kernel
from hc_falcon.semantic import Encoder
from hc_falcon.methods import prioritize, SEMANTIC_METHODS
from hc_falcon.dante import history_features, prioritize as dante
from tcp.history import RollingHistory
from test_tcp import build


class Stage5Tests(unittest.TestCase):
    def test_hand_computed(self):
        k = np.array([[1, .5], [.5, 1]], dtype=np.float32)
        order, trace = rank(('b', 'a'), k, [.25, .75])
        self.assertEqual(order, ('a', 'b'))
        self.assertEqual(trace[0].total_gain, .75)
        self.assertEqual(trace[1].total_gain, .25)

    def test_lazy_matches_standard(self):
        rng = np.random.default_rng(17)
        for n in (0, 1, 2, 7, 31):
            for _ in range(12):
                k = kernel(rng.normal(size=(n, 8)), rng.random(n) > .2)
                w = normalize(rng.integers(0, 4, n))
                ids = tuple(f't{j:03}' for j in reversed(range(n)))
                for alpha in (0, .25, .5, .75, 1):
                    self.assertEqual(rank(ids, k, w, alpha, True), rank(ids, k, w, alpha, False))

    def test_zero_ties_and_duplicate_vectors(self):
        for k in (np.zeros((3, 3)), np.ones((3, 3))):
            self.assertEqual(rank(('c', 'a', 'b'), k, [0, 0, 0])[0], ('a', 'b', 'c'))

    def test_kernel_negative_and_invalid(self):
        k = kernel([[1, 0], [-1, 0], [0, 0], [1, 0]], [True, True, True, False])
        np.testing.assert_array_equal(k, np.diag([1, 1, 0, 0]))

    def test_comments_preserve_literals(self):
        source = b'\xef\xbb\xbfclass/*x*/A { String s="https://a/*b*/";\r\n//gone\r\nchar c=\'/\'; }'
        self.assertEqual(preprocess(source), 'class A { String s="https://a/*b*/";\n \nchar c=\'/\'; }')
        self.assertEqual(preprocess(b'"""\n//literal /*yes*/\n"""/*gone*/'), '"""\n//literal /*yes*/\n""" ')
        with self.assertRaises(UnicodeError):
            preprocess(b'\xff')
        with self.assertRaises(ValueError):
            preprocess(b'/*')

    def test_padding_invariance(self):
        import torch
        hidden = torch.tensor([[[1., 2.], [3., 4.], [999., 999.]]])
        np.testing.assert_array_equal(masked_mean(hidden, torch.tensor([[1, 1, 0]])).numpy(), [[2, 3]])
        np.testing.assert_array_equal(masked_mean(hidden[:, :2], torch.ones(1, 2)).numpy(), [[2, 3]])

    def test_invalid_objective(self):
        for weights in ([float('nan')], [-1]):
            with self.assertRaises(ValueError):
                rank(('a',), [[1]], weights)
        with self.assertRaises(ValueError):
            rank(('a', 'a'), np.eye(2), [0, 0])

    def test_kernel_cache_invalidation(self):
        with tempfile.TemporaryDirectory() as directory:
            args = (directory, ('a', 'b'), [[1, 0], [0, 1]], [True, True], {'revision': 'one'})
            first, key, hit = cached_kernel(*args)
            self.assertFalse(hit)
            second, same, hit = cached_kernel(*args)
            self.assertTrue(hit)
            self.assertEqual(key, same)
            np.testing.assert_array_equal(first, second)
            for changed in ((directory, ('b', 'a'), args[2], args[3], args[4]),
                            (directory, args[1], [[1, 1], [0, 1]], args[3], args[4]),
                            (directory, args[1], args[2], [False, True], args[4]),
                            (directory, args[1], args[2], args[3], {'revision': 'two'})):
                self.assertNotEqual(key, cached_kernel(*changed)[1])

    def test_semantic_and_dante_current_future_leakage(self):
        old = build('old', 0, 1, [('a', True, 2), ('b', False, 4)])
        current = build('now', 10, 11, [('a', False, 100), ('b', True, 200)])
        future = build('future', 20, 21, [('a', True, 900), ('b', False, 800)])
        history = RollingHistory()
        history.observe(old)
        before = history.snapshot(current.inputs)
        history.observe(current)
        history.observe(future)
        after = history.snapshot(current.inputs)
        self.assertEqual(before, after)
        for method in SEMANTIC_METHODS:
            self.assertEqual(prioritize(before, ('a', 'b'), np.eye(2), method),
                             prioritize(after, ('a', 'b'), np.eye(2), method))
        sources = {'a': 'class A alpha', 'b': 'class B beta'}
        expected = dante(current.inputs, before, [old], sources, ['alpha'])
        mutated = replace(current, outcomes=tuple(replace(o, failed=not o.failed, duration=1e9) for o in current.outcomes))
        self.assertEqual(expected, dante(current.inputs, after, [old, mutated, future], sources, ['alpha']))
        self.assertIsNone(dante(current.inputs, after, [old], sources, None).order)

    def test_dante_windows_do_not_cross_tests_or_missing_slots(self):
        records = [build('0', 0, 1, [('a', True, 1), ('b', False, 1)])]
        records += [build(str(i), i * 2, i * 2 + 1, [('b', False, 1)]) for i in range(1, 17)]
        current = build('now', 100, 101, [('a', False, 1), ('b', True, 1)])
        self.assertEqual(history_features(current.inputs, records), {'a': (0, 0), 'b': (0, 0)})

    def test_dante_conditional_probability_threshold(self):
        records = [build(str(i), i * 2, i * 2 + 1, [('a', True, 1), ('b', False, 1)]) for i in range(21)]
        current = build('now', 100, 101, [('a', False, 1), ('b', False, 1)])
        self.assertAlmostEqual(history_features(current.inputs, records)['a'][0], 1 + 1 + 1/3 + 1/5)
        self.assertEqual(history_features(current.inputs, records[:20])['a'], (1, 15))

    def test_chunk_cap_weighted_pooling_and_vector_cache(self):
        import torch
        from types import SimpleNamespace
        from tokenizers import Tokenizer, models, pre_tokenizers, processors
        backend = Tokenizer(models.WordLevel({'[UNK]': 0, 'x': 1, 'y': 2, '[CLS]': 3, '[SEP]': 4, '[PAD]': 5}, unk_token='[UNK]'))
        backend.pre_tokenizer = pre_tokenizers.Whitespace()
        backend.post_processor = processors.TemplateProcessing(single='[CLS] $A [SEP]', special_tokens=[('[CLS]', 3), ('[SEP]', 4)])
        class FakeModel:
            config = SimpleNamespace(hidden_size=2)
            def __call__(self, input_ids, attention_mask):
                return SimpleNamespace(last_hidden_state=torch.stack((input_ids.float(), torch.ones_like(input_ids).float()), dim=-1))
        with tempfile.TemporaryDirectory() as directory:
            encoder = Encoder.__new__(Encoder)
            encoder.torch, encoder.model = torch, FakeModel()
            encoder.cache = Path(directory)
            encoder.config = {'max_length': 4, 'max_chunks': 2}
            encoder.identity = {'config': encoder.config, 'revision': 'fixture'}
            encoder.tokenizer = SimpleNamespace(backend_tokenizer=backend, pad_token_id=5, pad_token='[PAD]', num_special_tokens_to_add=lambda pair: 2)
            vector, meta = encoder.encode(b'x y x')
            # Chunks [CLS,x,y,SEP] and [CLS,x,SEP], weighted by 2 and 1 payload tokens.
            expected = np.array([(2 * 2.5 + 8/3) / 3, 1], dtype=np.float32)
            expected /= np.linalg.norm(expected)
            np.testing.assert_allclose(vector, expected, rtol=1e-6)
            self.assertEqual((meta['token_count'], meta['chunks'], meta['truncation_fraction']), (3, 2, 0))
            self.assertTrue(encoder.encode(b'x y x')[1]['cache_hit'])
            _, capped = encoder.encode(b'x y x y x')
            self.assertEqual(capped['truncation_fraction'], .2)
            self.assertNotEqual(meta['cache_key'], capped['cache_key'])
            encoder.identity = dict(encoder.identity, revision='changed')
            self.assertNotEqual(meta['cache_key'], encoder.encode(b'x y x')[1]['cache_key'])
            self.assertFalse(encoder.encode(b'/* comments only */')[1]['valid'])


if __name__ == '__main__':
    unittest.main()
