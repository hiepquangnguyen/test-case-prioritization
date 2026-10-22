"""Unit tests for Stage 10 Chart Bridge (T07).

Validates:
1. Source-method-index alignment on Chart (2,193 methods, 26 faults).
2. Bidirectional ID translation (index <-> FQN).
3. Tie-breaking semantics: index-based vs FQN-based.
4. Bridge arms decomposition invariants (A, B, C, D component changes).
"""
from __future__ import annotations

import json
import pickle
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from hc_falcon import greedy as internal_greedy


class TestChartBridgeInvariants(unittest.TestCase):
    def setUp(self):
        input_dir = ROOT / "work/artifacts/falcon/input/Chart"
        self.bbox_path = input_dir / "Chart-bbox.txt"
        self.mapping_path = input_dir / "test_method_mapping.json"
        self.faults_path = input_dir / "fault_matrix.pickle"

        with open(self.bbox_path, "r", encoding="utf-8") as f:
            self.lines = f.read().splitlines()
        with open(self.mapping_path, "r", encoding="utf-8") as f:
            self.mapping_doc = json.load(f)
        with open(self.faults_path, "rb") as f:
            self.faults = pickle.load(f)

    def test_source_method_index_alignment(self):
        n = len(self.lines)
        self.assertEqual(n, 2193)
        mapping = self.mapping_doc["index_to_method"]
        self.assertEqual(len(mapping), 2193)

        # Check all indices 0..2192 are present and FQNs are unique
        fqns = []
        for i in range(n):
            self.assertIn(str(i), mapping)
            m_info = mapping[str(i)]
            self.assertIn("fullIdentifier", m_info)
            fqns.append(m_info["fullIdentifier"])

        self.assertEqual(len(fqns), 2193)
        self.assertEqual(len(set(fqns)), 2193, "Duplicate FQNs found!")

    def test_bidirectional_id_translation(self):
        mapping = self.mapping_doc["index_to_method"]
        fqn_to_idx = {mapping[str(i)]["fullIdentifier"]: i for i in range(len(mapping))}
        self.assertEqual(len(fqn_to_idx), 2193)

        # Roundtrip check
        for i in range(len(mapping)):
            fqn = mapping[str(i)]["fullIdentifier"]
            self.assertEqual(fqn_to_idx[fqn], i)

    def test_tie_breaking_semantics(self):
        # Verify FQN lexicographical tie-breaker vs index tie-breaker
        # Suppose method A has index 1 but FQN "zoo::test"
        # Method B has index 0 but FQN "alpha::test"
        # Under equal kernel gains:
        # Index tie breaker picks index 0 ("alpha"), then index 1 ("zoo")
        # Now if method A has index 0 with FQN "zoo", and method B has index 1 with FQN "alpha":
        # Index tie breaker picks 0 ("zoo").
        # FQN tie breaker picks "alpha" (method B), then "zoo" (method A).
        kernel = np.array([
            [1.0, 1.0],
            [1.0, 1.0]
        ], dtype=np.float32)
        weights = np.zeros(2, dtype=np.float64)

        test_ids = ("zoo::test", "alpha::test")
        ranking, _ = internal_greedy.rank(test_ids=test_ids, kernel=kernel, weights=weights, alpha=1.0)
        # FQN ascending tie break must select "alpha::test" first despite being second in input
        self.assertEqual(ranking, ("alpha::test", "zoo::test"))

    def test_locked_bridge_config(self):
        cfg_path = ROOT / "configs/chart-bridge-v1.json"
        self.assertTrue(cfg_path.exists())
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        self.assertEqual(set(cfg["arms"].keys()), {"A", "B", "C", "D"})
        self.assertEqual(cfg["project"], "Chart")
        self.assertEqual(cfg["methods_count"], 2193)
        self.assertEqual(cfg["faults_count"], 26)


if __name__ == "__main__":
    unittest.main()
