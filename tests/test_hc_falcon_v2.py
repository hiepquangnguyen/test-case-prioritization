"""Unit and property tests for HC-FALCON v2: Uncertainty-Guarded Cost-aware Semantic ranking.

Verifies the 10 required invariants:
1. Full deterministic permutation.
2. Exact FQN tie-breaking.
3. Reference/vectorized equivalence on deterministic randomized fixtures.
4. A zero kernel produces exactly tcp.baselines.rank(snapshot, "history_cost").
5. If all history_cost scores are zero, semantic density determines the order, with FQN tie-breaking.
6. A semantically attractive heavy test cannot overtake a clearly separated history anchor
   when its upper risk bound is below the anchor lower bound.
7. Invalid kernels, NaN, Inf, negative values, duplicate IDs, and inventory mismatch fail closed.
8. The ranker accepts Snapshot only and never current-build Outcome.
9. Input Snapshot and kernel are not mutated.
10. Comprehensive property checks across edge cases (empty inventory, single item, disconnected graphs).
"""
from __future__ import annotations

import copy
import inspect
import json
import math
from pathlib import Path
import random
import tempfile
import unittest
from dataclasses import dataclass
from typing import Tuple
from unittest.mock import patch

import numpy as np

from hc_falcon.v2 import rank_ugcs, rank_ugcs_reference
from scripts.stage12_evaluate import (
    compute_stage_predecessor_delay,
    evaluate_decision,
    validate_delta_summary,
    validate_preregistered_config,
)
from scripts.stage12_freeze import (
    PREREGISTRATION_FILES,
    run_pre_evaluation,
    sha256_file,
    validate_pre_evaluation_manifest,
)
from tcp.baselines import rank as baseline_rank
from tcp.domain import BuildKey, Outcome, RankingInput, TestInput as DomainTestInput
from tcp.history import Feature, HistoryConfig, RollingHistory, Snapshot

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class MockFeature:
    test_id: str
    observations: int
    failures: int
    confidence: float
    history_cost_score: float
    normalized_duration: float


@dataclass(frozen=True)
class MockSnapshot:
    features: Tuple[MockFeature, ...]
    key: BuildKey = BuildKey("proj", "pr1", "1", "stage1")
    cutoff: float = 100.0
    context: Tuple[str, str, str] = ("proj", "main", "stage1")
    eligible_builds: Tuple[BuildKey, ...] = ()
    latest_evidence_available_at: float | None = 50.0
    duration_reference: float = 1.0


class TestHCFalconV2(unittest.TestCase):
    def setUp(self):
        self.test_ids = ("com.example.TestA", "com.example.TestB", "com.example.TestC", "com.example.TestD")
        self.mock_features = (
            MockFeature("com.example.TestA", 10, 4, 10 / 15, 0.45, 1.2),
            MockFeature("com.example.TestB", 5, 1, 5 / 10, 0.20, 0.8),
            MockFeature("com.example.TestC", 0, 0, 0.0, 0.0, 1.0),
            MockFeature("com.example.TestD", 20, 12, 20 / 25, 0.85, 2.5),
        )
        self.snapshot = MockSnapshot(self.mock_features)
        self.kernel = np.array(
            [
                [1.0, 0.4, 0.2, 0.1],
                [0.4, 1.0, 0.5, 0.3],
                [0.2, 0.5, 1.0, 0.6],
                [0.1, 0.3, 0.6, 1.0],
            ],
            dtype=np.float64,
        )

    # =========================================================================
    # Invariant 1: Full deterministic permutation
    # =========================================================================
    def test_invariant_1_full_deterministic_permutation(self):
        order1 = rank_ugcs(self.snapshot, self.test_ids, self.kernel)
        order2 = rank_ugcs(self.snapshot, self.test_ids, self.kernel)
        order_ref = rank_ugcs_reference(self.snapshot, self.test_ids, self.kernel)

        self.assertEqual(order1, order2, "Ranker must be strictly deterministic across calls")
        self.assertEqual(order1, order_ref, "Vectorized and reference must match")
        self.assertIsInstance(order1, tuple, "Output must be a tuple")
        self.assertEqual(len(order1), len(self.test_ids), "Output length must match input inventory")
        self.assertEqual(set(order1), set(self.test_ids), "Output must be a permutation of inputs")
        self.assertEqual(len(set(order1)), len(order1), "Permutation must contain no duplicates")

    # =========================================================================
    # Invariant 2: Exact FQN tie-breaking
    # =========================================================================
    def test_invariant_2_exact_fqn_tie_breaking(self):
        # Create candidates with identical features and identical kernel similarities
        ids = ("pkg.ZebraTest", "pkg.AlphaTest", "pkg.BetaTest")
        feats = tuple(MockFeature(t, 5, 2, 0.5, 0.3, 1.0) for t in ids)
        snap = MockSnapshot(feats)
        # Uniform similarity matrix
        uniform_k = np.ones((3, 3), dtype=np.float64) * 0.5
        np.fill_diagonal(uniform_k, 1.0)

        order = rank_ugcs(snap, ids, uniform_k)
        order_ref = rank_ugcs_reference(snap, ids, uniform_k)

        expected = ("pkg.AlphaTest", "pkg.BetaTest", "pkg.ZebraTest")
        self.assertEqual(order, expected, "Ties must be broken strictly by ascending FQN")
        self.assertEqual(order_ref, expected, "Reference must also break ties by ascending FQN")

    # =========================================================================
    # Invariant 3: Reference/vectorized equivalence on randomized fixtures
    # =========================================================================
    def test_invariant_3_reference_vectorized_equivalence_randomized(self):
        rng = random.Random(42)
        np_rng = np.random.default_rng(42)

        for case_idx in range(40):
            n = rng.randint(2, 25)
            ids = tuple(f"test.case.T{i:03d}" for i in range(n))
            features = []
            for i in range(n):
                obs = rng.randint(0, 30)
                fails = rng.randint(0, obs) if obs > 0 else 0
                conf = obs / (obs + 5.0)
                dur = rng.uniform(0.01, 10.0)
                # history_cost_score calculation
                q = (conf * (fails + 1) / (obs + 2)) / (math.sqrt(dur) + 1e-8)
                features.append(MockFeature(ids[i], obs, fails, conf, q, dur))

            snap = MockSnapshot(tuple(features))
            # Generate random symmetric PSD-like kernel with values in [0, 1]
            raw_vecs = np_rng.uniform(0, 1, size=(n, 8))
            norms = np.linalg.norm(raw_vecs, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            norm_vecs = raw_vecs / norms
            k = np.clip(norm_vecs @ norm_vecs.T, 0.0, 1.0)
            np.fill_diagonal(k, 1.0)

            sem_weight = rng.choice([0.0, 0.1, 0.25, 0.5, 0.75, 1.0])
            z_val = rng.choice([1.0, 1.645, 1.96, 2.576])

            order_vec = rank_ugcs(snap, ids, k, semantic_weight=sem_weight, z_value=z_val)
            order_ref = rank_ugcs_reference(snap, ids, k, semantic_weight=sem_weight, z_value=z_val)

            self.assertEqual(
                order_vec,
                order_ref,
                f"Mismatch between vectorized and reference on fixture {case_idx} (n={n}, weight={sem_weight}, z={z_val})",
            )

    # =========================================================================
    # Invariant 4: Zero kernel produces exactly tcp.baselines.rank("history_cost")
    # =========================================================================
    def test_invariant_4_zero_kernel_produces_history_cost(self):
        zero_k = np.zeros((len(self.test_ids), len(self.test_ids)), dtype=np.float64)

        # Baseline rank expectation: sorted by (-f.history_cost_score, f.test_id)
        expected_hc = baseline_rank(self.snapshot, "history_cost")

        order_ugcs = rank_ugcs(self.snapshot, self.test_ids, zero_k)
        order_ref = rank_ugcs_reference(self.snapshot, self.test_ids, zero_k)

        self.assertEqual(order_ugcs, expected_hc, "Zero kernel must identically match history_cost baseline")
        self.assertEqual(order_ref, expected_hc, "Reference ranker with zero kernel must match history_cost")

        # Randomized test of Invariant 4
        rng = random.Random(1337)
        for _ in range(10):
            n = rng.randint(3, 15)
            ids = tuple(f"org.sample.Test{i}" for i in range(n))
            feats = []
            for t in ids:
                obs = rng.randint(0, 20)
                fails = rng.randint(0, obs) if obs > 0 else 0
                feats.append(MockFeature(t, obs, fails, rng.random(), rng.uniform(0, 2), rng.uniform(0.1, 5)))
            snap = MockSnapshot(tuple(feats))
            k_zeros = np.zeros((n, n), dtype=np.float64)

            expected = baseline_rank(snap, "history_cost")
            self.assertEqual(rank_ugcs(snap, ids, k_zeros), expected)
            self.assertEqual(rank_ugcs_reference(snap, ids, k_zeros), expected)

    # =========================================================================
    # Invariant 5: Zero history_cost scores -> semantic density determines order
    # =========================================================================
    def test_invariant_5_zero_history_scores_governed_by_semantic_density(self):
        # All tests have 0 history (confidence=0, failures=0, observations=0, history_cost_score=0)
        ids = ("tA", "tB", "tC")
        # Costs: tA=1.0, tB=4.0, tC=0.25 (sqrt_costs: tA=1.0, tB=2.0, tC=0.5)
        feats = (
            MockFeature("tA", 0, 0, 0.0, 0.0, 1.0),
            MockFeature("tB", 0, 0, 0.0, 0.0, 4.0),
            MockFeature("tC", 0, 0, 0.0, 0.0, 0.25),
        )
        snap = MockSnapshot(feats)

        # Kernel where all tests have diagonal=1, but tA has high coverage to others
        # k:
        # tA connects to tA(1.0), tB(0.8), tC(0.8) -> marginal sum = 2.6 / 3 ~ 0.8667
        # tC connects to tC(1.0), tA(0.4), tB(0.4) -> marginal sum = 1.8 / 3 ~ 0.6000
        # But density for tC = 0.6000 / sqrt(0.25) = 0.6 / 0.5 = 1.2000
        # Density for tA = 0.8667 / sqrt(1.0) = 0.8667
        # So tC should have higher initial density than tA despite lower absolute coverage!
        k = np.array(
            [
                [1.0, 0.8, 0.4],
                [0.8, 1.0, 0.4],
                [0.4, 0.4, 1.0],
            ],
            dtype=np.float64,
        )

        order_vec = rank_ugcs(snap, ids, k, semantic_weight=1.0)
        order_ref = rank_ugcs_reference(snap, ids, k, semantic_weight=1.0)

        self.assertEqual(order_vec, order_ref)
        self.assertEqual(order_vec[0], "tC", "Highest cost-aware density candidate tC must be chosen first")

    # =========================================================================
    # Invariant 6: Heavy test cannot overtake clearly separated history anchor
    # =========================================================================
    def test_invariant_6_heavy_test_cannot_overtake_separated_anchor(self):
        # Anchor A: 20 observations, 18 failures, cost 0.5s -> strong lower bound
        # Heavy test B: 20 observations, 0 failures, cost 150.0s -> very low upper bound
        ids = ("anchor_A", "heavy_B")
        anchor_feat = MockFeature("anchor_A", observations=20, failures=18, confidence=20 / 25, history_cost_score=0.9, normalized_duration=0.5)
        heavy_feat = MockFeature("heavy_B", observations=20, failures=0, confidence=20 / 25, history_cost_score=0.01, normalized_duration=150.0)
        snap = MockSnapshot((anchor_feat, heavy_feat))

        # Even with B having perfect coverage to everything (kernel = 1.0)
        # and A having zero similarity to B
        k = np.array(
            [
                [1.0, 0.0],
                [1.0, 1.0],
            ],
            dtype=np.float64,
        )

        # Check bounds directly first
        # A: F=18, N=20 -> a=19, b=3 -> mu=19/22 ~ 0.8636, sigma ~ 0.0722, lower bound >> 0.5
        # B: F=0, N=20 -> a=1, b=21 -> mu=1/22 ~ 0.0455, sigma ~ 0.0433, denom ~ sqrt(150) ~ 12.25
        # B upper bound is tiny (< 0.02)
        order = rank_ugcs(snap, ids, k, semantic_weight=0.5)
        order_ref = rank_ugcs_reference(snap, ids, k, semantic_weight=0.5)

        self.assertEqual(order, ("anchor_A", "heavy_B"), "Heavy test B must NOT overtake anchor_A")
        self.assertEqual(order_ref, ("anchor_A", "heavy_B"), "Reference must also block heavy_B")

    # =========================================================================
    # Invariant 7: Fail-closed on invalid inputs
    # =========================================================================
    def test_invariant_7_fail_closed_validations(self):
        n = len(self.test_ids)
        # 1. Duplicate IDs
        with self.assertRaises(ValueError):
            rank_ugcs(self.snapshot, ("com.example.TestA", "com.example.TestA", "com.example.TestC", "com.example.TestD"), self.kernel)

        # 2. Inventory mismatch (missing ID)
        with self.assertRaises(ValueError):
            rank_ugcs(self.snapshot, ("com.example.TestA", "com.example.TestB"), self.kernel[:2, :2])

        # 3. Kernel shape mismatch
        with self.assertRaises(ValueError):
            rank_ugcs(self.snapshot, self.test_ids, np.zeros((n, n + 1)))

        # 4. Kernel NaN
        nan_k = self.kernel.copy()
        nan_k[0, 1] = float("nan")
        with self.assertRaises(ValueError):
            rank_ugcs(self.snapshot, self.test_ids, nan_k)

        # 5. Kernel Inf
        inf_k = self.kernel.copy()
        inf_k[0, 1] = float("inf")
        with self.assertRaises(ValueError):
            rank_ugcs(self.snapshot, self.test_ids, inf_k)

        # 6. Kernel negative values
        neg_k = self.kernel.copy()
        neg_k[0, 1] = -0.1
        with self.assertRaises(ValueError):
            rank_ugcs(self.snapshot, self.test_ids, neg_k)

        # 7. Kernel > 1.0
        large_k = self.kernel.copy()
        large_k[0, 1] = 1.01
        with self.assertRaises(ValueError):
            rank_ugcs(self.snapshot, self.test_ids, large_k)

        # 8. Negative observations
        bad_feats = list(self.mock_features)
        bad_feats[0] = MockFeature("com.example.TestA", -1, 0, 0.5, 0.5, 1.0)
        with self.assertRaises(ValueError):
            rank_ugcs(MockSnapshot(tuple(bad_feats)), self.test_ids, self.kernel)

        # 9. Failures > observations
        bad_feats = list(self.mock_features)
        bad_feats[0] = MockFeature("com.example.TestA", 5, 6, 0.5, 0.5, 1.0)
        with self.assertRaises(ValueError):
            rank_ugcs(MockSnapshot(tuple(bad_feats)), self.test_ids, self.kernel)

        # 10. Negative normalized duration
        bad_feats = list(self.mock_features)
        bad_feats[0] = MockFeature("com.example.TestA", 5, 2, 0.5, 0.5, -1.0)
        with self.assertRaises(ValueError):
            rank_ugcs(MockSnapshot(tuple(bad_feats)), self.test_ids, self.kernel)

        # 11. Invalid semantic_weight (< 0 or > 1 or NaN)
        with self.assertRaises(ValueError):
            rank_ugcs(self.snapshot, self.test_ids, self.kernel, semantic_weight=-0.1)
        with self.assertRaises(ValueError):
            rank_ugcs(self.snapshot, self.test_ids, self.kernel, semantic_weight=1.1)
        with self.assertRaises(ValueError):
            rank_ugcs(self.snapshot, self.test_ids, self.kernel, semantic_weight=float("nan"))

        # 12. Invalid z_value (<= 0 or NaN)
        with self.assertRaises(ValueError):
            rank_ugcs(self.snapshot, self.test_ids, self.kernel, z_value=0.0)
        with self.assertRaises(ValueError):
            rank_ugcs(self.snapshot, self.test_ids, self.kernel, z_value=-1.0)
        with self.assertRaises(ValueError):
            rank_ugcs(self.snapshot, self.test_ids, self.kernel, z_value=float("nan"))

    # =========================================================================
    # Invariant 8: Ranker accepts Snapshot only and never Outcome
    # =========================================================================
    def test_invariant_8_signature_and_ground_truth_boundary(self):
        sig_ugcs = inspect.signature(rank_ugcs)
        sig_ref = inspect.signature(rank_ugcs_reference)

        param_names = list(sig_ugcs.parameters.keys())
        self.assertEqual(param_names, ["snapshot", "test_ids", "kernel", "semantic_weight", "z_value"])
        self.assertEqual(list(sig_ref.parameters.keys()), param_names)

        # Assert Outcome cannot be passed as snapshot
        outcome = Outcome("com.example.TestA", True, 1.5)
        with self.assertRaises(ValueError):
            rank_ugcs(outcome, self.test_ids, self.kernel)

    # =========================================================================
    # Invariant 9: Inputs snapshot and kernel are not mutated
    # =========================================================================
    def test_invariant_9_input_immutability(self):
        k_before = self.kernel.copy()
        snap_features_before = [(f.test_id, f.observations, f.failures, f.confidence, f.history_cost_score, f.normalized_duration) for f in self.snapshot.features]

        _ = rank_ugcs(self.snapshot, self.test_ids, self.kernel)

        np.testing.assert_array_equal(self.kernel, k_before, "Kernel array must not be mutated")
        snap_features_after = [(f.test_id, f.observations, f.failures, f.confidence, f.history_cost_score, f.normalized_duration) for f in self.snapshot.features]
        self.assertEqual(snap_features_before, snap_features_after, "Snapshot features must not be mutated")

    # =========================================================================
    # Invariant 10: Edge cases (empty inventory, single test)
    # =========================================================================
    def test_invariant_10_edge_cases(self):
        # Empty inventory
        empty_snap = MockSnapshot(())
        empty_k = np.zeros((0, 0), dtype=np.float64)
        self.assertEqual(rank_ugcs(empty_snap, (), empty_k), ())
        self.assertEqual(rank_ugcs_reference(empty_snap, (), empty_k), ())

        # Single test
        single_feat = (MockFeature("only.Test", 10, 2, 0.6, 0.3, 1.0),)
        single_snap = MockSnapshot(single_feat)
        single_k = np.ones((1, 1), dtype=np.float64)
        self.assertEqual(rank_ugcs(single_snap, ("only.Test",), single_k), ("only.Test",))
        self.assertEqual(rank_ugcs_reference(single_snap, ("only.Test",), single_k), ("only.Test",))



class TestStage12Governance(unittest.TestCase):
    """Rigorous fail-closed governance and verification tests for Stage 12 Phase A."""

    def setUp(self):
        # Build clean baseline manifest dictionary
        self.valid_manifest = {
            "created_at": "2026-09-21T12:00:00Z",
            "stage": "12",
            "scope": "stage12_pre_evaluation_freeze",
            "parent_release": "v0.1.1",
            "primary_method": "hc_ugcs_v2",
            "reserved_opened": False,
            "development_evaluated": False,
            "files_count": len(PREREGISTRATION_FILES),
            "files_sha256": {rel: sha256_file(ROOT / rel) for rel in PREREGISTRATION_FILES},
        }

        with open(ROOT / "configs" / "hc-falcon-v2-preregistered.json", "r", encoding="utf-8") as f:
            self.config = json.load(f)

        # Baseline project reports fixture with all passing effect gates and complete metrics
        self.mock_project_reports = {
            "karaf": {
                "physical_builds": 79,
                "stages": 149,
                "paired_vs_history_cost": {
                    "hc_ugcs_v2": {"median": 0.045, "mean": 0.042, "count": 79, "pos": 50, "tie": 10, "neg": 19}
                },
                "paired_vs_fl_only": {
                    "hc_ugcs_v2": {"median": 0.350, "mean": 0.320, "count": 79, "pos": 70, "tie": 5, "neg": 4}
                },
                "paired_ttff_vs_history_cost": {
                    "hc_ugcs_v2": {"median": -12.5, "mean": -10.2, "count": 79, "pos": 20, "tie": 10, "neg": 49}
                },
                "paired_recall10_vs_history_cost": {
                    "hc_ugcs_v2": {"median": 0.08, "mean": 0.075, "count": 79, "pos": 55, "tie": 10, "neg": 14}
                },
                "cumulative_predecessor_seconds": 150.0,
            },
            "activemq": {
                "physical_builds": 57,
                "stages": 224,
                "paired_vs_history_cost": {
                    "hc_ugcs_v2": {"median": 0.038, "mean": 0.035, "count": 57, "pos": 38, "tie": 8, "neg": 11}
                },
                "paired_vs_fl_only": {
                    "hc_ugcs_v2": {"median": 0.280, "mean": 0.260, "count": 57, "pos": 52, "tie": 2, "neg": 3}
                },
                "paired_ttff_vs_history_cost": {
                    "hc_ugcs_v2": {"median": -8.0, "mean": -7.5, "count": 57, "pos": 15, "tie": 8, "neg": 34}
                },
                "paired_recall10_vs_history_cost": {
                    "hc_ugcs_v2": {"median": 0.05, "mean": 0.048, "count": 57, "pos": 40, "tie": 5, "neg": 12}
                },
                "cumulative_predecessor_seconds": 80.0,
            },
            "log4j": {
                "physical_builds": 25,
                "stages": 223,
                "paired_vs_history_cost": {
                    "hc_ugcs_v2": {"median": 0.015, "mean": 0.012, "count": 25, "pos": 14, "tie": 3, "neg": 8}
                },
                "paired_vs_fl_only": {
                    "hc_ugcs_v2": {"median": 0.150, "mean": 0.140, "count": 25, "pos": 20, "tie": 1, "neg": 4}
                },
                "paired_ttff_vs_history_cost": {
                    "hc_ugcs_v2": {"median": -2.0, "mean": -1.8, "count": 25, "pos": 8, "tie": 4, "neg": 13}
                },
                "paired_recall10_vs_history_cost": {
                    "hc_ugcs_v2": {"median": 0.02, "mean": 0.019, "count": 25, "pos": 16, "tie": 3, "neg": 6}
                },
                "cumulative_predecessor_seconds": 25.0,
            },
        }

        self.mock_eng_metrics = {
            "p95_warm_overhead_fraction": 0.045,  # <= 0.10 threshold
            "peak_rss_bytes": 1024 * 1024 * 500,  # 500 MB <= 8 GiB threshold
            "median_latency_ugcs_seconds": 0.005,
            "median_latency_hc_seconds": 0.004,
            "scored_stages_total": 596,
        }

    # =========================================================================
    # Tests 1-10: Strict Fail-Closed Manifest Validation
    # =========================================================================
    def test_01_manifest_valid_accepted(self):
        """A properly formatted pre-evaluation manifest with valid hashes is accepted."""
        is_valid, errors = validate_pre_evaluation_manifest(self.valid_manifest, ROOT)
        self.assertTrue(is_valid, f"Expected valid manifest, got errors: {errors}")
        self.assertEqual(len(errors), 0)

    def test_02_manifest_missing_file_rejected(self):
        """Manifest missing any one of the 8 required files is rejected fail-closed."""
        bad_manifest = copy.deepcopy(self.valid_manifest)
        bad_manifest["files_sha256"].pop("hc_falcon/v2.py")
        bad_manifest["files_count"] = len(bad_manifest["files_sha256"])

        is_valid, errors = validate_pre_evaluation_manifest(bad_manifest, ROOT)
        self.assertFalse(is_valid)
        self.assertTrue(any("Missing required" in e for e in errors))

    def test_03_manifest_extra_file_rejected(self):
        """Manifest containing any undeclared extra file is rejected fail-closed."""
        bad_manifest = copy.deepcopy(self.valid_manifest)
        bad_manifest["files_sha256"]["unexpected/extra.py"] = "0" * 64
        bad_manifest["files_count"] = len(bad_manifest["files_sha256"])

        is_valid, errors = validate_pre_evaluation_manifest(bad_manifest, ROOT)
        self.assertFalse(is_valid)
        self.assertTrue(any("Unexpected extra" in e for e in errors))

    def test_04_manifest_files_count_mismatch_rejected(self):
        """Manifest with files_count != 8 or != len(files_sha256) is rejected."""
        bad_manifest = copy.deepcopy(self.valid_manifest)
        bad_manifest["files_count"] = 7

        is_valid, errors = validate_pre_evaluation_manifest(bad_manifest, ROOT)
        self.assertFalse(is_valid)
        self.assertTrue(any("files_count" in e for e in errors))

    def test_05_manifest_bad_hash_rejected(self):
        """Manifest with invalid hash format or hash mismatch against disk is rejected."""
        # Non-hex format
        bad_manifest = copy.deepcopy(self.valid_manifest)
        bad_manifest["files_sha256"]["hc_falcon/v2.py"] = "NOT_HEX_HASH_VALUE"
        is_valid, errors = validate_pre_evaluation_manifest(bad_manifest, ROOT)
        self.assertFalse(is_valid)
        self.assertTrue(any("Invalid SHA-256 format" in e for e in errors))

        # Hex format but mismatched hash
        bad_manifest2 = copy.deepcopy(self.valid_manifest)
        bad_manifest2["files_sha256"]["hc_falcon/v2.py"] = "0" * 64
        is_valid2, errors2 = validate_pre_evaluation_manifest(bad_manifest2, ROOT)
        self.assertFalse(is_valid2)
        self.assertTrue(any("Hash mismatch" in e for e in errors2))

    def test_06_manifest_empty_rejected(self):
        """Empty manifest or non-dictionary data is rejected fail-closed."""
        is_valid, errors = validate_pre_evaluation_manifest({}, ROOT)
        self.assertFalse(is_valid)
        self.assertTrue(any("non-empty dictionary" in e for e in errors))

        is_valid2, errors2 = validate_pre_evaluation_manifest(None, ROOT)
        self.assertFalse(is_valid2)

    def test_07_manifest_wrong_metadata_rejected(self):
        """Manifest with altered stage, scope, parent_release, or primary_method is rejected."""
        for field, bad_val in [
            ("stage", "11"),
            ("scope", "wrong_scope"),
            ("parent_release", "v0.1.0"),
            ("primary_method", "fl_only"),
        ]:
            bad = copy.deepcopy(self.valid_manifest)
            bad[field] = bad_val
            is_valid, errors = validate_pre_evaluation_manifest(bad, ROOT)
            self.assertFalse(is_valid, f"Expected rejection for {field}={bad_val}")
            self.assertTrue(any(field in e for e in errors))

    def test_08_manifest_reserved_opened_not_false_rejected(self):
        """Manifest with reserved_opened != False is strictly rejected."""
        for bad_val in [True, None, "false", 0]:
            bad = copy.deepcopy(self.valid_manifest)
            bad["reserved_opened"] = bad_val
            is_valid, errors = validate_pre_evaluation_manifest(bad, ROOT)
            self.assertFalse(is_valid, f"Expected rejection for reserved_opened={bad_val}")
            self.assertTrue(any("reserved_opened" in e for e in errors))

    def test_09_manifest_development_evaluated_not_false_rejected(self):
        """Manifest with development_evaluated != False is strictly rejected."""
        for bad_val in [True, None, "false", 0]:
            bad = copy.deepcopy(self.valid_manifest)
            bad["development_evaluated"] = bad_val
            is_valid, errors = validate_pre_evaluation_manifest(bad, ROOT)
            self.assertFalse(is_valid, f"Expected rejection for development_evaluated={bad_val}")
            self.assertTrue(any("development_evaluated" in e for e in errors))

    def test_10_manifest_path_hygiene_rejected(self):
        """Manifest with absolute paths, Windows drive paths, or parent traversal ('..') is rejected."""
        # Absolute path
        bad_abs = copy.deepcopy(self.valid_manifest)
        bad_abs["files_sha256"].pop("hc_falcon/v2.py")
        bad_abs["files_sha256"]["/etc/passwd"] = "0" * 64
        is_valid_abs, errors_abs = validate_pre_evaluation_manifest(bad_abs, ROOT)
        self.assertFalse(is_valid_abs)
        self.assertTrue(any("Path must not be absolute" in e for e in errors_abs))

        # Windows drive path
        bad_win = copy.deepcopy(self.valid_manifest)
        bad_win["files_sha256"].pop("hc_falcon/v2.py")
        bad_win["files_sha256"]["C:\\windows\\system32\\cmd.exe"] = "0" * 64
        is_valid_win, errors_win = validate_pre_evaluation_manifest(bad_win, ROOT)
        self.assertFalse(is_valid_win)
        self.assertTrue(any("Path must not be absolute" in e for e in errors_win))

        # Traversal with ..
        bad_traversal = copy.deepcopy(self.valid_manifest)
        bad_traversal["files_sha256"].pop("hc_falcon/v2.py")
        bad_traversal["files_sha256"]["configs/../hc_falcon/v2.py"] = "0" * 64
        is_valid_trav, errors_trav = validate_pre_evaluation_manifest(bad_traversal, ROOT)
        self.assertFalse(is_valid_trav)
        self.assertTrue(any("Path must not contain '..'" in e for e in errors_trav))

    # =========================================================================
    # Part C Tests: Manifest Validator Safe Path Isolation (Mocking)
    # =========================================================================
    def test_10b_manifest_validator_does_not_hash_or_access_unsafe_paths(self):
        """Proves validator never invokes sha256_file or disk access on unsafe/unallowlisted paths."""
        # 1. Absolute path: sha256_file and exists must NOT be called on absolute path
        bad_abs = copy.deepcopy(self.valid_manifest)
        bad_abs["files_sha256"].pop("hc_falcon/v2.py")
        bad_abs["files_sha256"]["/etc/passwd"] = "0" * 64
        with patch("scripts.stage12_freeze.sha256_file") as mock_sha:
            is_valid, errors = validate_pre_evaluation_manifest(bad_abs, ROOT)
            self.assertFalse(is_valid)
            self.assertTrue(any("Path must not be absolute" in e for e in errors))
            for call_item in mock_sha.call_args_list:
                self.assertNotIn("passwd", str(call_item[0][0]))

        solo_bad_abs = dict(self.valid_manifest, files_sha256={"/etc/passwd": "0" * 64}, files_count=1)
        with patch("scripts.stage12_freeze.sha256_file") as mock_sha, patch.object(Path, "exists", autospec=True) as mock_exists:
            validate_pre_evaluation_manifest(solo_bad_abs, ROOT)
            mock_sha.assert_not_called()
            for call_item in mock_exists.call_args_list:
                self.assertNotIn("passwd", str(call_item[0][0]))

        # 2. Directory traversal path: sha256_file and exists must NOT be called on traversal path
        bad_trav = copy.deepcopy(self.valid_manifest)
        bad_trav["files_sha256"].pop("hc_falcon/v2.py")
        bad_trav["files_sha256"]["configs/../hc_falcon/v2.py"] = "0" * 64
        with patch("scripts.stage12_freeze.sha256_file") as mock_sha:
            is_valid, errors = validate_pre_evaluation_manifest(bad_trav, ROOT)
            self.assertFalse(is_valid)
            self.assertTrue(any("Path must not contain '..'" in e for e in errors))
            for call_item in mock_sha.call_args_list:
                self.assertNotIn("..", str(call_item[0][0]))

        solo_bad_trav = dict(self.valid_manifest, files_sha256={"configs/../hc_falcon/v2.py": "0" * 64}, files_count=1)
        with patch("scripts.stage12_freeze.sha256_file") as mock_sha, patch.object(Path, "exists", autospec=True) as mock_exists:
            validate_pre_evaluation_manifest(solo_bad_trav, ROOT)
            mock_sha.assert_not_called()
            for call_item in mock_exists.call_args_list:
                self.assertNotIn("..", str(call_item[0][0]))

        # 3. Extra path syntactically valid but outside allowlist: must NOT be hashed
        bad_extra = copy.deepcopy(self.valid_manifest)
        bad_extra["files_sha256"].pop("hc_falcon/v2.py")
        bad_extra["files_sha256"]["scripts/stage10_driver.py"] = "0" * 64
        with patch("scripts.stage12_freeze.sha256_file") as mock_sha:
            is_valid, errors = validate_pre_evaluation_manifest(bad_extra, ROOT)
            self.assertFalse(is_valid)
            self.assertTrue(any("preregistration allowlist" in e for e in errors))
            for call_item in mock_sha.call_args_list:
                self.assertNotIn("stage10_driver", str(call_item[0][0]))

        solo_bad_extra = dict(self.valid_manifest, files_sha256={"scripts/stage10_driver.py": "0" * 64}, files_count=1)
        with patch("scripts.stage12_freeze.sha256_file") as mock_sha, patch.object(Path, "exists", autospec=True) as mock_exists:
            validate_pre_evaluation_manifest(solo_bad_extra, ROOT)
            mock_sha.assert_not_called()
            for call_item in mock_exists.call_args_list:
                self.assertNotIn("stage10_driver", str(call_item[0][0]))

        # 4. Simulated reserved/confirmation path: must NOT be read or hashed
        bad_res = copy.deepcopy(self.valid_manifest)
        bad_res["files_sha256"].pop("hc_falcon/v2.py")
        bad_res["files_sha256"]["data/simulated_reserved_confirmation.csv"] = "0" * 64
        with patch("scripts.stage12_freeze.sha256_file") as mock_sha:
            is_valid, errors = validate_pre_evaluation_manifest(bad_res, ROOT)
            self.assertFalse(is_valid)
            for call_item in mock_sha.call_args_list:
                self.assertNotIn("simulated_reserved", str(call_item[0][0]))

        solo_bad_res = dict(self.valid_manifest, files_sha256={"data/simulated_reserved_confirmation.csv": "0" * 64}, files_count=1)
        with patch("scripts.stage12_freeze.sha256_file") as mock_sha, patch.object(Path, "exists", autospec=True) as mock_exists:
            validate_pre_evaluation_manifest(solo_bad_res, ROOT)
            mock_sha.assert_not_called()
            for call_item in mock_exists.call_args_list:
                self.assertNotIn("simulated_reserved", str(call_item[0][0]))

    # =========================================================================
    # Part D Tests: Anti-Tamper Pre-Freeze in Isolated Temp Directory
    # =========================================================================
    def test_11_pre_freeze_refused_when_development_screen_exists_in_temp(self):
        """Pre-freeze in temporary directory is strictly refused if development-screen.json exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            temp_out = temp_root / "reports" / "stage12"
            temp_out.mkdir(parents=True, exist_ok=True)
            temp_manifest = temp_out / "pre-evaluation-manifest.json"

            # Create dummy pre-existing manifest to verify it is NOT overwritten
            sentinel_content = '{"sentinel": "do_not_overwrite"}'
            temp_manifest.write_text(sentinel_content, encoding="utf-8")

            # Create post-observation evidence in temp_out
            (temp_out / "development-screen.json").write_text('{"status": "observed"}', encoding="utf-8")

            # Create the 8 preregistration files in temp_root
            for rel in PREREGISTRATION_FILES:
                p = temp_root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(f"# dummy {rel}\n", encoding="utf-8")

            with self.assertRaises(RuntimeError) as ctx:
                run_pre_evaluation(
                    root_dir=temp_root,
                    out_dir=temp_out,
                    manifest_path=temp_manifest,
                )
            self.assertIn("post-observation evidence already exists", str(ctx.exception))
            # Verify existing manifest was preserved
            self.assertEqual(temp_manifest.read_text(encoding="utf-8"), sentinel_content)

    def test_12_pre_freeze_in_temp_directory_creates_exact_manifest(self):
        """Pre-freeze executes in temporary directory, creating manifest with 8 entries matching temp files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            temp_out = temp_root / "reports" / "stage12"
            temp_manifest = temp_out / "pre-evaluation-manifest.json"

            # Create 8 dummy preregistration files
            dummy_hashes = {}
            for rel in PREREGISTRATION_FILES:
                p = temp_root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                content = f"dummy content for {rel}\n".encode("utf-8")
                p.write_bytes(content)
                dummy_hashes[rel] = sha256_file(p)

            # Record state of real workspace manifest before running
            real_manifest_path = ROOT / "reports" / "stage12" / "pre-evaluation-manifest.json"
            real_manifest_mtime = real_manifest_path.stat().st_mtime if real_manifest_path.exists() else None

            # Execute real pre-freeze in temp directory
            created_path = run_pre_evaluation(
                root_dir=temp_root,
                out_dir=temp_out,
                manifest_path=temp_manifest,
            )

            self.assertEqual(created_path, temp_manifest)
            self.assertTrue(temp_manifest.exists())

            with open(temp_manifest, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)

            self.assertEqual(manifest_data["files_count"], 8)
            self.assertEqual(len(manifest_data["files_sha256"]), 8)
            self.assertEqual(manifest_data["stage"], "12")
            self.assertFalse(manifest_data["reserved_opened"])
            self.assertFalse(manifest_data["development_evaluated"])

            for rel in PREREGISTRATION_FILES:
                self.assertIn(rel, manifest_data["files_sha256"])
                self.assertEqual(manifest_data["files_sha256"][rel], dummy_hashes[rel])

            # Confirm real workspace was untouched
            if real_manifest_path.exists():
                self.assertEqual(real_manifest_path.stat().st_mtime, real_manifest_mtime)

    # =========================================================================
    # Tests 13-15: Evaluator Decision Governance & Gates
    # =========================================================================
    def test_13_final_decision_nogo_if_engineering_gate_fails(self):
        """Decision cannot be GO if any engineering gate threshold is breached."""
        # Baseline passes: 2 of 3 projects pass effect gate (Karaf +0.045, ActiveMQ +0.038)
        base_decision = evaluate_decision(self.mock_project_reports, self.config, self.mock_eng_metrics)
        self.assertEqual(base_decision["final_decision"], "GO")
        self.assertTrue(base_decision["effect_gate"]["passed"])
        self.assertTrue(base_decision["engineering_gates"]["all_passed"])

        # Case A: P95 warm overhead exceeds 0.10 (e.g. 0.125)
        bad_overhead_metrics = dict(self.mock_eng_metrics, p95_warm_overhead_fraction=0.125)
        decision_bad_overhead = evaluate_decision(self.mock_project_reports, self.config, bad_overhead_metrics)
        self.assertEqual(decision_bad_overhead["final_decision"], "NO-GO")
        self.assertFalse(decision_bad_overhead["engineering_gates"]["all_passed"])
        self.assertFalse(decision_bad_overhead["engineering_gates"]["overhead_gate"]["passed"])

        # Case B: Peak RSS exceeds 8 GiB (8,589,934,592 bytes)
        bad_rss_metrics = dict(self.mock_eng_metrics, peak_rss_bytes=9_000_000_000)
        decision_bad_rss = evaluate_decision(self.mock_project_reports, self.config, bad_rss_metrics)
        self.assertEqual(decision_bad_rss["final_decision"], "NO-GO")
        self.assertFalse(decision_bad_rss["engineering_gates"]["all_passed"])
        self.assertFalse(decision_bad_rss["engineering_gates"]["memory_gate"]["passed"])

    def test_14_final_decision_nogo_if_engineering_metrics_missing(self):
        """Decision cannot be GO if any required engineering metric is missing."""
        # Missing P95 overhead
        missing_overhead = dict(self.mock_eng_metrics, p95_warm_overhead_fraction=None)
        dec_no_overhead = evaluate_decision(self.mock_project_reports, self.config, missing_overhead)
        self.assertEqual(dec_no_overhead["final_decision"], "NO-GO")
        self.assertFalse(dec_no_overhead["engineering_gates"]["all_passed"])
        self.assertTrue(len(dec_no_overhead["audit_errors"]) > 0)

        # Missing peak RSS
        missing_rss = dict(self.mock_eng_metrics, peak_rss_bytes=None)
        dec_no_rss = evaluate_decision(self.mock_project_reports, self.config, missing_rss)
        self.assertEqual(dec_no_rss["final_decision"], "NO-GO")

        # Missing project-level secondary metric (e.g. cumulative predecessor seconds)
        bad_proj_reports = copy.deepcopy(self.mock_project_reports)
        bad_proj_reports["karaf"].pop("cumulative_predecessor_seconds", None)
        dec_no_pred = evaluate_decision(bad_proj_reports, self.config, self.mock_eng_metrics)
        self.assertEqual(dec_no_pred["final_decision"], "NO-GO")
        self.assertFalse(dec_no_pred["engineering_gates"]["all_passed"])
        self.assertFalse(dec_no_pred["engineering_gates"]["completeness_gate"]["passed"])

    def test_15_tampered_threshold_or_project_count_rejected(self):
        """Tampering with preregistered threshold or project counts produces fail-closed NO-GO."""
        # Altered threshold (e.g. 0.040 != 0.03) must be rejected fail-closed
        custom_config = copy.deepcopy(self.config)
        custom_config["effect_gate"]["threshold"] = 0.040
        dec_custom = evaluate_decision(self.mock_project_reports, custom_config, self.mock_eng_metrics)
        self.assertEqual(dec_custom["final_decision"], "NO-GO")
        self.assertTrue(any("effect_gate" in e and "threshold" in e for e in dec_custom["audit_errors"]))

        # Altered minimum development projects (e.g. 1 != 2) must be rejected fail-closed
        custom_config2 = copy.deepcopy(self.config)
        custom_config2["effect_gate"]["minimum_development_projects"] = 1
        dec_custom2 = evaluate_decision(self.mock_project_reports, custom_config2, self.mock_eng_metrics)
        self.assertEqual(dec_custom2["final_decision"], "NO-GO")
        self.assertTrue(any("minimum_development_projects" in e for e in dec_custom2["audit_errors"]))


    # =========================================================================
    # Test 16: Reserved Data Leakage Boundary
    # =========================================================================
    def test_16_no_reserved_data_accessed(self):
        """Confirms that no Stage 12 code references or opens reserved confirmation splits."""
        for fpath in ["scripts/stage12_evaluate.py", "scripts/stage12_freeze.py", "hc_falcon/v2.py"]:
            text = (ROOT / fpath).read_text(encoding="utf-8")
            self.assertNotIn("reserved_splits", text)
            self.assertNotIn("confirmation_split", text)
            self.assertNotIn("stage12/confirmation", text)

    # =========================================================================
    # Test 17: Predecessor Delay Calculation
    # =========================================================================
    def test_17_predecessor_delay_calculation(self):
        """Verifies predecessor delay calculation matches standard Stage 7 / 11 formula."""
        outcomes = (
            Outcome("t1", False, 10.0),
            Outcome("t2", True, 20.0),  # failing
            Outcome("t3", False, 30.0),
        )
        # In history_cost: order is (t2, t1, t3) -> before t2 is empty set
        hc_order = ("t2", "t1", "t3")
        # In candidate: order is (t1, t2, t3) -> before t2 is {t1}
        cand_order = ("t1", "t2", "t3")

        delay = compute_stage_predecessor_delay(cand_order, hc_order, outcomes)
        # Added predecessor is {t1} with duration 10.0; removed is empty. Net delay = +10.0s
        self.assertAlmostEqual(delay, 10.0, places=5)

    # =========================================================================
    # Part A Tests: Development Projects Exact Set
    # =========================================================================
    def test_18_dev_projects_exact_three_can_go(self):
        """Exact 3 projects with passing gates produces GO."""
        decision = evaluate_decision(self.mock_project_reports, self.config, self.mock_eng_metrics)
        self.assertEqual(decision["final_decision"], "GO")
        self.assertEqual(decision["expected_projects"], ["karaf", "activemq", "log4j"])
        self.assertEqual(decision["observed_projects"], ["activemq", "karaf", "log4j"])
        self.assertEqual(len(decision["audit_errors"]), 0)

    def test_19_dev_projects_missing_log4j_nogo(self):
        """Missing log4j project produces fail-closed NO-GO with explicit audit error."""
        reports_without_log4j = {k: v for k, v in self.mock_project_reports.items() if k != "log4j"}
        decision = evaluate_decision(reports_without_log4j, self.config, self.mock_eng_metrics)
        self.assertEqual(decision["final_decision"], "NO-GO")
        self.assertFalse(decision["effect_gate"]["passed"])
        self.assertTrue(
            any("Missing required development project reports" in e and "log4j" in e for e in decision["audit_errors"])
        )

    def test_20_dev_projects_extra_project_nogo(self):
        """Extra project in reports produces fail-closed NO-GO with explicit audit error."""
        reports_with_extra = copy.deepcopy(self.mock_project_reports)
        reports_with_extra["extra_project"] = copy.deepcopy(self.mock_project_reports["karaf"])
        decision = evaluate_decision(reports_with_extra, self.config, self.mock_eng_metrics)
        self.assertEqual(decision["final_decision"], "NO-GO")
        self.assertFalse(decision["effect_gate"]["passed"])
        self.assertTrue(
            any("Unexpected extra project reports" in e and "extra_project" in e for e in decision["audit_errors"])
        )

    def test_21_dev_projects_substituted_project_nogo(self):
        """3 projects but substituting log4j with another name produces fail-closed NO-GO."""
        reports_sub = {k: v for k, v in self.mock_project_reports.items() if k != "log4j"}
        reports_sub["spark"] = copy.deepcopy(self.mock_project_reports["log4j"])
        decision = evaluate_decision(reports_sub, self.config, self.mock_eng_metrics)
        self.assertEqual(decision["final_decision"], "NO-GO")
        self.assertTrue(any("Missing required development project reports" in e for e in decision["audit_errors"]))
        self.assertTrue(any("Unexpected extra project reports" in e for e in decision["audit_errors"]))

    def test_22_dev_projects_total_mismatch_nogo(self):
        """total_development_projects mismatching project count in config produces NO-GO."""
        bad_cfg = copy.deepcopy(self.config)
        bad_cfg["effect_gate"]["total_development_projects"] = 4
        decision = evaluate_decision(self.mock_project_reports, bad_cfg, self.mock_eng_metrics)
        self.assertEqual(decision["final_decision"], "NO-GO")
        self.assertTrue(any("Config mismatch: development_projects count" in e for e in decision["audit_errors"]))

    def test_23_dev_projects_minimum_greater_than_total_nogo(self):
        """minimum_development_projects > total_development_projects produces NO-GO."""
        bad_cfg = copy.deepcopy(self.config)
        bad_cfg["effect_gate"]["minimum_development_projects"] = 4
        bad_cfg["effect_gate"]["total_development_projects"] = 3
        decision = evaluate_decision(self.mock_project_reports, bad_cfg, self.mock_eng_metrics)
        self.assertEqual(decision["final_decision"], "NO-GO")
        self.assertTrue(
            any(
                "minimum_development_projects (4) > total_development_projects (3)" in e
                for e in decision["audit_errors"]
            )
        )

    def test_24_dev_projects_missing_in_config_nogo(self):
        """Missing development_projects field in config produces NO-GO."""
        bad_cfg = copy.deepcopy(self.config)
        bad_cfg.pop("development_projects", None)
        bad_cfg["effect_gate"].pop("development_projects", None)
        decision = evaluate_decision(self.mock_project_reports, bad_cfg, self.mock_eng_metrics)
        self.assertEqual(decision["final_decision"], "NO-GO")
        self.assertTrue(any("Invalid or missing 'development_projects'" in e for e in decision["audit_errors"]))

    # =========================================================================
    # Part B Tests: Fail-Closed Metric Validation
    # =========================================================================
    def test_25_metric_apfdc_median_nan_nogo(self):
        """APFDc median delta NaN produces fail-closed NO-GO."""
        bad_reports = copy.deepcopy(self.mock_project_reports)
        bad_reports["karaf"]["paired_vs_history_cost"]["hc_ugcs_v2"]["median"] = float("nan")
        decision = evaluate_decision(bad_reports, self.config, self.mock_eng_metrics)
        self.assertEqual(decision["final_decision"], "NO-GO")
        self.assertFalse(decision["effect_gate"]["passed"])
        self.assertTrue(any("non-finite or missing median delta" in e for e in decision["audit_errors"]))

    def test_26_metric_apfdc_mean_inf_nogo(self):
        """APFDc mean delta Inf produces fail-closed NO-GO."""
        bad_reports = copy.deepcopy(self.mock_project_reports)
        bad_reports["karaf"]["paired_vs_history_cost"]["hc_ugcs_v2"]["mean"] = float("inf")
        decision = evaluate_decision(bad_reports, self.config, self.mock_eng_metrics)
        self.assertEqual(decision["final_decision"], "NO-GO")
        self.assertTrue(any("non-finite or missing mean delta" in e for e in decision["audit_errors"]))

    def test_27_metric_ttff_nan_nogo(self):
        """TTFF median delta NaN produces fail-closed NO-GO."""
        bad_reports = copy.deepcopy(self.mock_project_reports)
        bad_reports["karaf"]["paired_ttff_vs_history_cost"]["hc_ugcs_v2"]["median"] = float("nan")
        decision = evaluate_decision(bad_reports, self.config, self.mock_eng_metrics)
        self.assertEqual(decision["final_decision"], "NO-GO")
        self.assertTrue(any("TTFF median delta" in e for e in decision["audit_errors"]))

    def test_28_metric_recall10_inf_nogo(self):
        """Recall@10% median delta Inf produces fail-closed NO-GO."""
        bad_reports = copy.deepcopy(self.mock_project_reports)
        bad_reports["karaf"]["paired_recall10_vs_history_cost"]["hc_ugcs_v2"]["median"] = float("inf")
        decision = evaluate_decision(bad_reports, self.config, self.mock_eng_metrics)
        self.assertEqual(decision["final_decision"], "NO-GO")
        self.assertTrue(any("Recall@10% median delta" in e for e in decision["audit_errors"]))

    def test_29_metric_predecessor_seconds_nan_nogo(self):
        """Cumulative predecessor seconds NaN produces fail-closed NO-GO."""
        bad_reports = copy.deepcopy(self.mock_project_reports)
        bad_reports["karaf"]["cumulative_predecessor_seconds"] = float("nan")
        decision = evaluate_decision(bad_reports, self.config, self.mock_eng_metrics)
        self.assertEqual(decision["final_decision"], "NO-GO")
        self.assertTrue(any("cumulative_predecessor_seconds" in e for e in decision["audit_errors"]))

    def test_30_metric_runtime_overhead_nan_nogo(self):
        """P95 runtime overhead NaN produces fail-closed NO-GO."""
        bad_eng = dict(self.mock_eng_metrics, p95_warm_overhead_fraction=float("nan"))
        decision = evaluate_decision(self.mock_project_reports, self.config, bad_eng)
        self.assertEqual(decision["final_decision"], "NO-GO")
        self.assertFalse(decision["engineering_gates"]["all_passed"])
        self.assertTrue(any("p95_warm_overhead_fraction" in e for e in decision["audit_errors"]))

    def test_31_metric_peak_rss_inf_nogo(self):
        """Peak RSS bytes Inf produces fail-closed NO-GO."""
        bad_eng = dict(self.mock_eng_metrics, peak_rss_bytes=float("inf"))
        decision = evaluate_decision(self.mock_project_reports, self.config, bad_eng)
        self.assertEqual(decision["final_decision"], "NO-GO")
        self.assertFalse(decision["engineering_gates"]["all_passed"])
        self.assertTrue(any("Peak RSS bytes" in e for e in decision["audit_errors"]))

    def test_32_metric_count_zero_nogo(self):
        """Sample count = 0 produces fail-closed NO-GO."""
        bad_reports = copy.deepcopy(self.mock_project_reports)
        bad_reports["karaf"]["paired_vs_history_cost"]["hc_ugcs_v2"]["count"] = 0
        decision = evaluate_decision(bad_reports, self.config, self.mock_eng_metrics)
        self.assertEqual(decision["final_decision"], "NO-GO")
        self.assertTrue(any("count must be positive int" in e for e in decision["audit_errors"]))

    def test_33_metric_pos_neg_tie_mismatch_count_nogo(self):
        """pos + neg + tie != count produces fail-closed NO-GO."""
        bad_reports = copy.deepcopy(self.mock_project_reports)
        # count is 79, but 50 + 10 + 20 = 80 != 79
        bad_reports["karaf"]["paired_vs_history_cost"]["hc_ugcs_v2"]["neg"] = 20
        decision = evaluate_decision(bad_reports, self.config, self.mock_eng_metrics)
        self.assertEqual(decision["final_decision"], "NO-GO")
        self.assertTrue(any("pos+tie+neg" in e and "!= count" in e for e in decision["audit_errors"]))

    def test_34_metric_latency_missing_or_non_positive_nogo(self):
        """Latency missing or <= 0 produces fail-closed NO-GO."""
        # Non-positive latency
        bad_eng1 = dict(self.mock_eng_metrics, median_latency_ugcs_seconds=0.0)
        decision1 = evaluate_decision(self.mock_project_reports, self.config, bad_eng1)
        self.assertEqual(decision1["final_decision"], "NO-GO")
        self.assertTrue(any("median_latency_ugcs_seconds" in e for e in decision1["audit_errors"]))

        # Missing latency
        bad_eng2 = dict(self.mock_eng_metrics, median_latency_hc_seconds=None)
        decision2 = evaluate_decision(self.mock_project_reports, self.config, bad_eng2)
        self.assertEqual(decision2["final_decision"], "NO-GO")
        self.assertTrue(any("median_latency_hc_seconds" in e for e in decision2["audit_errors"]))

    def test_35_metric_scored_stages_total_zero_nogo(self):
        """scored_stages_total = 0 produces fail-closed NO-GO."""
        bad_eng = dict(self.mock_eng_metrics, scored_stages_total=0)
        decision = evaluate_decision(self.mock_project_reports, self.config, bad_eng)
        self.assertEqual(decision["final_decision"], "NO-GO")
        self.assertTrue(any("scored_stages_total" in e for e in decision["audit_errors"]))

    def test_36_fail_closed_probes_from_specification(self):
        """Verifies both specific fail-closed probes from the specification."""
        # Probe 1: Missing log4j project
        reports_without_log4j = {k: v for k, v in self.mock_project_reports.items() if k != "log4j"}
        self.assertEqual(
            evaluate_decision(
                reports_without_log4j,
                self.config,
                self.mock_eng_metrics,
            )["final_decision"],
            "NO-GO",
        )

        # Probe 2: Non-finite TTFF and predecessor seconds
        reports_nan = copy.deepcopy(self.mock_project_reports)
        reports_nan["karaf"]["paired_ttff_vs_history_cost"]["hc_ugcs_v2"]["median"] = float("nan")
        reports_nan["karaf"]["cumulative_predecessor_seconds"] = float("nan")

        self.assertEqual(
            evaluate_decision(
                reports_nan,
                self.config,
                self.mock_eng_metrics,
            )["final_decision"],
            "NO-GO",
        )

    # =========================================================================
    # Part E Tests: Fail-Closed Secondary Summaries & Locked Config Validation
    # =========================================================================
    def test_37_secondary_ttff_validation(self):
        """TTFF count=0, mean=NaN, median=Inf, or W/T/L mismatch forces NO-GO."""
        # TTFF count = 0 -> NO-GO
        r_zero = copy.deepcopy(self.mock_project_reports)
        r_zero["karaf"]["paired_ttff_vs_history_cost"]["hc_ugcs_v2"]["count"] = 0
        dec_zero = evaluate_decision(r_zero, self.config, self.mock_eng_metrics)
        self.assertEqual(dec_zero["final_decision"], "NO-GO")
        self.assertTrue(any("TTFF" in e and "count must be positive int" in e for e in dec_zero["audit_errors"]))

        # TTFF mean = NaN -> NO-GO
        r_nan = copy.deepcopy(self.mock_project_reports)
        r_nan["karaf"]["paired_ttff_vs_history_cost"]["hc_ugcs_v2"]["mean"] = float("nan")
        dec_nan = evaluate_decision(r_nan, self.config, self.mock_eng_metrics)
        self.assertEqual(dec_nan["final_decision"], "NO-GO")
        self.assertTrue(any("TTFF" in e and "non-finite or missing mean" in e for e in dec_nan["audit_errors"]))

        # TTFF median = Inf -> NO-GO
        r_inf = copy.deepcopy(self.mock_project_reports)
        r_inf["karaf"]["paired_ttff_vs_history_cost"]["hc_ugcs_v2"]["median"] = float("inf")
        dec_inf = evaluate_decision(r_inf, self.config, self.mock_eng_metrics)
        self.assertEqual(dec_inf["final_decision"], "NO-GO")
        self.assertTrue(any("TTFF" in e and "non-finite or missing median" in e for e in dec_inf["audit_errors"]))

        # TTFF W/T/L mismatch -> NO-GO
        r_wtl = copy.deepcopy(self.mock_project_reports)
        # count is 79, set pos=20, tie=10, neg=50 -> sum is 80 != 79
        r_wtl["karaf"]["paired_ttff_vs_history_cost"]["hc_ugcs_v2"]["neg"] = 50
        dec_wtl = evaluate_decision(r_wtl, self.config, self.mock_eng_metrics)
        self.assertEqual(dec_wtl["final_decision"], "NO-GO")
        self.assertTrue(any("TTFF" in e and "pos+tie+neg" in e for e in dec_wtl["audit_errors"]))

    def test_38_secondary_recall10_validation(self):
        """Recall@10% count=0, mean=NaN, median=Inf, or W/T/L mismatch forces NO-GO."""
        # Recall count = 0 -> NO-GO
        r_zero = copy.deepcopy(self.mock_project_reports)
        r_zero["karaf"]["paired_recall10_vs_history_cost"]["hc_ugcs_v2"]["count"] = 0
        dec_zero = evaluate_decision(r_zero, self.config, self.mock_eng_metrics)
        self.assertEqual(dec_zero["final_decision"], "NO-GO")
        self.assertTrue(any("Recall@10%" in e and "count must be positive int" in e for e in dec_zero["audit_errors"]))

        # Recall mean = NaN -> NO-GO
        r_nan = copy.deepcopy(self.mock_project_reports)
        r_nan["karaf"]["paired_recall10_vs_history_cost"]["hc_ugcs_v2"]["mean"] = float("nan")
        dec_nan = evaluate_decision(r_nan, self.config, self.mock_eng_metrics)
        self.assertEqual(dec_nan["final_decision"], "NO-GO")
        self.assertTrue(any("Recall@10%" in e and "non-finite or missing mean" in e for e in dec_nan["audit_errors"]))

        # Recall median = Inf -> NO-GO
        r_inf = copy.deepcopy(self.mock_project_reports)
        r_inf["karaf"]["paired_recall10_vs_history_cost"]["hc_ugcs_v2"]["median"] = float("inf")
        dec_inf = evaluate_decision(r_inf, self.config, self.mock_eng_metrics)
        self.assertEqual(dec_inf["final_decision"], "NO-GO")
        self.assertTrue(any("Recall@10%" in e and "non-finite or missing median" in e for e in dec_inf["audit_errors"]))

        # Recall W/T/L mismatch -> NO-GO
        r_wtl = copy.deepcopy(self.mock_project_reports)
        # count is 79, set pos=55, tie=10, neg=20 -> sum is 85 != 79
        r_wtl["karaf"]["paired_recall10_vs_history_cost"]["hc_ugcs_v2"]["neg"] = 20
        dec_wtl = evaluate_decision(r_wtl, self.config, self.mock_eng_metrics)
        self.assertEqual(dec_wtl["final_decision"], "NO-GO")
        self.assertTrue(any("Recall@10%" in e and "pos+tie+neg" in e for e in dec_wtl["audit_errors"]))

    def test_39_secondary_summary_type_and_bool_rejection(self):
        """Non-dict secondary summary or boolean count produces fail-closed NO-GO."""
        # Non-dict summary
        r_nondict = copy.deepcopy(self.mock_project_reports)
        r_nondict["karaf"]["paired_ttff_vs_history_cost"]["hc_ugcs_v2"] = "not_a_dict"
        dec_nondict = evaluate_decision(r_nondict, self.config, self.mock_eng_metrics)
        self.assertEqual(dec_nondict["final_decision"], "NO-GO")
        self.assertTrue(any("must be a dictionary" in e for e in dec_nondict["audit_errors"]))

        # count = True (boolean masquerading as int)
        r_bool = copy.deepcopy(self.mock_project_reports)
        r_bool["karaf"]["paired_ttff_vs_history_cost"]["hc_ugcs_v2"]["count"] = True
        dec_bool = evaluate_decision(r_bool, self.config, self.mock_eng_metrics)
        self.assertEqual(dec_bool["final_decision"], "NO-GO")
        self.assertTrue(any("count must be positive int" in e for e in dec_bool["audit_errors"]))

    def test_40_missing_locked_config_fields_force_nogo(self):
        """Deleting any locked configuration field forces fail-closed NO-GO."""
        probes = [
            ("primary_method", lambda c: c.pop("primary_method", None)),
            ("threshold", lambda c: c["effect_gate"].pop("threshold", None)),
            ("comparators", lambda c: c["effect_gate"].pop("comparators", None)),
            ("p95_warm_overhead_fraction", lambda c: c["engineering_gates"].pop("p95_warm_overhead_fraction", None)),
            ("peak_rss_bytes", lambda c: c["engineering_gates"].pop("peak_rss_bytes", None)),
            ("warmup_runs", lambda c: c["runtime_protocol"].pop("warmup_runs", None)),
            ("repetitions", lambda c: c["runtime_protocol"].pop("repetitions", None)),
            ("reserved_opened", lambda c: c["governance"].pop("reserved_opened", None)),
        ]
        for name, mutate_fn in probes:
            cfg = copy.deepcopy(self.config)
            mutate_fn(cfg)
            decision = evaluate_decision(self.mock_project_reports, cfg, self.mock_eng_metrics)
            self.assertEqual(decision["final_decision"], "NO-GO", f"Expected NO-GO when deleting {name}")
            self.assertTrue(len(decision["audit_errors"]) > 0, f"Expected audit error when deleting {name}")

    def test_41_comparator_validation_probes_force_nogo(self):
        """Missing, extra, or duplicated comparators in config force fail-closed NO-GO."""
        comparator_variants = [
            (["history_cost"], "missing fl_only"),
            (["history_cost", "fl_only", "extra"], "extra comparator"),
            (["history_cost", "history_cost"], "duplicated comparator"),
        ]
        for comps, label in comparator_variants:
            cfg = copy.deepcopy(self.config)
            cfg["effect_gate"]["comparators"] = comps
            decision = evaluate_decision(self.mock_project_reports, cfg, self.mock_eng_metrics)
            self.assertEqual(decision["final_decision"], "NO-GO", f"Expected NO-GO for comparators={comps} ({label})")
            self.assertTrue(any("comparators" in e for e in decision["audit_errors"]))

    def test_42_protocol_and_governance_tamper_forces_nogo(self):
        """Tampering with repetitions or opening reserved data forces fail-closed NO-GO."""
        # repetitions = 0 -> NO-GO
        cfg_rep0 = copy.deepcopy(self.config)
        cfg_rep0["runtime_protocol"]["repetitions"] = 0
        dec_rep0 = evaluate_decision(self.mock_project_reports, cfg_rep0, self.mock_eng_metrics)
        self.assertEqual(dec_rep0["final_decision"], "NO-GO")
        self.assertTrue(any("repetitions" in e for e in dec_rep0["audit_errors"]))

        # reserved_opened = True -> NO-GO
        cfg_res = copy.deepcopy(self.config)
        cfg_res["governance"]["reserved_opened"] = True
        dec_res = evaluate_decision(self.mock_project_reports, cfg_res, self.mock_eng_metrics)
        self.assertEqual(dec_res["final_decision"], "NO-GO")
        self.assertTrue(any("reserved_opened" in e for e in dec_res["audit_errors"]))

    def test_43_valid_fixture_returns_go(self):
        """A fully valid baseline fixture passes all gates and returns GO."""
        decision = evaluate_decision(self.mock_project_reports, self.config, self.mock_eng_metrics)
        self.assertEqual(decision["final_decision"], "GO")
        self.assertTrue(decision["effect_gate"]["passed"])
        self.assertTrue(decision["engineering_gates"]["all_passed"])
        self.assertEqual(len(decision["audit_errors"]), 0)


if __name__ == "__main__":
    unittest.main()
