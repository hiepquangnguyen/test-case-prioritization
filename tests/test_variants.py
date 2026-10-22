"""Unit tests for Phase 3 improvement rankers in hc_falcon/variants.py."""
import math
import unittest
from dataclasses import dataclass
import numpy as np

from hc_falcon.variants import rank_cns, rank_knapsack, rank_tiered


@dataclass(frozen=True)
class MockFeature:
    test_id: str
    history_cost_score: float
    duration_estimate: float


@dataclass(frozen=True)
class MockSnapshot:
    features: tuple[MockFeature, ...]


class TestVariants(unittest.TestCase):
    def setUp(self):
        self.ids = ('test_a', 'test_b', 'test_c', 'test_d')
        self.features = (
            MockFeature('test_a', 0.8, 1.0),
            MockFeature('test_b', 0.2, 5.0),
            MockFeature('test_c', 0.0, 0.5),
            MockFeature('test_d', 0.5, 2.0),
        )
        self.snapshot = MockSnapshot(self.features)
        # Similarity kernel
        self.k = np.array([
            [1.0, 0.3, 0.1, 0.4],
            [0.3, 1.0, 0.2, 0.5],
            [0.1, 0.2, 1.0, 0.2],
            [0.4, 0.5, 0.2, 1.0],
        ], dtype=np.float32)

    def test_rank_cns_returns_exact_permutation(self):
        order = rank_cns(self.snapshot, self.ids, self.k, alpha=0.5)
        self.assertEqual(len(order), len(self.ids))
        self.assertEqual(set(order), set(self.ids))

    def test_rank_knapsack_returns_exact_permutation(self):
        order = rank_knapsack(self.snapshot, self.ids, self.k, alpha=0.5, gamma=0.5)
        self.assertEqual(len(order), len(self.ids))
        self.assertEqual(set(order), set(self.ids))

    def test_rank_tiered_returns_exact_permutation(self):
        order = rank_tiered(self.snapshot, self.ids, self.k)
        self.assertEqual(len(order), len(self.ids))
        self.assertEqual(set(order), set(self.ids))

    def test_deterministic_tie_breaking(self):
        order1 = rank_cns(self.snapshot, self.ids, self.k)
        order2 = rank_cns(self.snapshot, self.ids, self.k)
        self.assertEqual(order1, order2)

    def test_rejection_of_invalid_inputs(self):
        with self.assertRaises(ValueError):
            rank_cns(self.snapshot, ('test_a',), self.k)  # Length mismatch
        with self.assertRaises(ValueError):
            rank_cns(self.snapshot, self.ids, np.zeros((3, 3)))  # Shape mismatch


if __name__ == '__main__':
    unittest.main()
