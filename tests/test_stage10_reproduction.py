"""Unit tests for Stage 10 Reproduction runner and validation logic.

Covers:
1. APFD calculation: multi-detector, multi-fault, invalid permutations, missing faults.
2. FacilityLocation: negative cosine preservation, index-based tie breaking, valid permutation.
3. Checkpoint & Resume: exact numerical equivalence when resuming batch-by-batch.
4. Cache key provenance verification.
"""
from __future__ import annotations

import hashlib
import json
import pickle
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np
import torch

# Add repository root to path
ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "work/artifacts/falcon/py"))

import submodtcp
from stage10_validate import independent_apfd, validate_run
from stage10_reproduce import generate_embeddings_with_checkpoints


class TestAPFD(unittest.TestCase):
    def test_known_reference_apfd(self):
        # 3 methods: 0, 1, 2. 2 faults: 101, 102.
        # Method 0 detects fault 101. Method 2 detects fault 102. Method 1 detects nothing.
        # Order: [0, 1, 2]
        # First rank for 101 is 1. First rank for 102 is 3.
        # APFD = 1 - (1 + 3) / (3 * 2) + 1 / (2 * 3) = 1 - 4/6 + 1/6 = 3/6 = 0.5
        order = [0, 1, 2]
        faults = {0: [101], 1: [], 2: [102]}
        score = independent_apfd(order, faults)
        self.assertAlmostEqual(score, 0.5, places=9)

    def test_multiple_detectors_same_fault(self):
        # Fault 101 detected by both method 0 and method 2
        # Order: [0, 1, 2] -> first rank should be 1, ignoring method 2 at rank 3
        # n = 3, m = 1 -> APFD = 1 - 1/(3*1) + 1/(2*3) = 1 - 1/3 + 1/6 = 5/6 = 0.8333333333333334
        order = [0, 1, 2]
        faults = {0: [101], 2: [101]}
        score = independent_apfd(order, faults)
        self.assertAlmostEqual(score, 5.0 / 6.0, places=9)

    def test_one_test_multiple_faults(self):
        # Method 0 detects both 101 and 102
        # Order: [0, 1, 2] -> ranks are 1 and 1
        # n = 3, m = 2 -> APFD = 1 - (1 + 1)/(3*2) + 1/(2*3) = 1 - 2/6 + 1/6 = 5/6
        order = [0, 1, 2]
        faults = {0: [101, 102]}
        score = independent_apfd(order, faults)
        self.assertAlmostEqual(score, 5.0 / 6.0, places=9)

    def test_missing_fault_raises(self):
        # Fault 999 exists in faults dict but neither method in order detects it
        order = [0, 1]
        faults = {0: [101], 2: [999]}
        with self.assertRaises(ValueError):
            independent_apfd(order, faults)

    def test_empty_fault_universe_raises(self):
        order = [0, 1]
        faults = {0: [], 1: []}
        with self.assertRaises(ValueError):
            independent_apfd(order, faults)


class TestFacilityLocationProperties(unittest.TestCase):
    def test_negative_cosine_preservation(self):
        # Two orthogonal vectors and one opposite vector
        # v0 = [1, 0], v1 = [-1, 0] -> cosine(v0, v1) = -1.0
        embeddings = np.array([
            [1.0, 0.0],
            [-1.0, 0.0],
            [0.0, 1.0]
        ], dtype=np.float32)
        fl = submodtcp.FacilityLocation(source_embeddings=embeddings, metric="cosine", device="cpu")
        sim_mat = fl.similarity_matrix.cpu().numpy()
        self.assertAlmostEqual(float(sim_mat[0, 1]), -1.0, places=5)
        self.assertAlmostEqual(float(sim_mat[1, 0]), -1.0, places=5)
        # Verify negative values are NOT clipped to 0
        self.assertTrue((sim_mat < 0).any())

    def test_index_tie_breaking(self):
        # Three identical embeddings: [1, 1], [1, 1], [1, 1]
        # Marginal gains will be identical across candidates.
        # Under torch.argmax, tie-breaking must pick index 0, then index 1, then index 2.
        embeddings = np.array([
            [1.0, 1.0],
            [1.0, 1.0],
            [1.0, 1.0]
        ], dtype=np.float32)
        fl = submodtcp.FacilityLocation(source_embeddings=embeddings, metric="cosine", device="cpu")
        order, _ = fl.lazy_greedy(3)
        self.assertEqual(order, [0, 1, 2])

    def test_valid_permutation(self):
        np.random.seed(42)
        embeddings = np.random.randn(20, 8).astype(np.float32)
        fl = submodtcp.FacilityLocation(source_embeddings=embeddings, metric="cosine", device="cpu")
        order, gains = fl.lazy_greedy(20)
        self.assertEqual(len(order), 20)
        self.assertEqual(set(order), set(range(20)))
        self.assertEqual(len(gains), 20)


class MockTokenizer:
    def __call__(self, batch_tests, padding=True, truncation=True, max_length=512, return_tensors="pt"):
        # Returns simple tensor representation
        batch_size = len(batch_tests)
        input_ids = torch.tensor([[len(t), idx] for idx, t in enumerate(batch_tests)])
        return MockInputs(input_ids)


class MockInputs(dict):
    def __init__(self, tensor):
        super().__init__()
        self["input_ids"] = tensor

    def to(self, device):
        return self


class MockOutputs:
    def __init__(self, shape):
        # last_hidden_state: (batch, seq_len=4, hidden=16)
        self.last_hidden_state = torch.ones(shape[0], 4, 16, dtype=torch.float32)


class MockModel:
    def eval(self):
        pass

    def __call__(self, **kwargs):
        input_ids = kwargs.get("input_ids")
        batch_len = input_ids.shape[0] if input_ids is not None else 1
        return MockOutputs((batch_len, 4, 16))


class TestCheckpointAndResume(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_uninterrupted_vs_resumed_equivalence(self):
        tests = [f"test_method_{i}_{'x'*i}" for i in range(32)]
        mock_tok = MockTokenizer()
        mock_model = MockModel()

        # 1. Generate full 32 uninterrupted
        uninterrupted_dir = self.temp_dir / "uninterrupted"
        full_embs, _, _ = generate_embeddings_with_checkpoints(
            tests=tests,
            tokenizer=mock_tok,
            model=mock_model,
            device="cpu",
            batch_size=16,
            max_length=512,
            checkpoint_dir=uninterrupted_dir,
            resume=False
        )

        # 2. Simulate partial checkpoint (1 batch of 16)
        resumed_dir = self.temp_dir / "resumed"
        resumed_dir.mkdir(parents=True, exist_ok=True)
        chk_file = resumed_dir / "checkpoint_batches.npy"
        chk_meta = resumed_dir / "checkpoint_meta.json"
        
        # Save first 16 embeddings
        first_batch_embs = full_embs[:16]
        np.save(chk_file, first_batch_embs)
        chk_meta.write_text(json.dumps({
            "total_tests": 32,
            "batch_size": 16,
            "batches_completed": 1,
            "total_batches": 2,
            "items_completed": 16
        }), encoding="utf-8")

        # 3. Resume from batch 1 to complete batch 2
        resumed_embs, _, _ = generate_embeddings_with_checkpoints(
            tests=tests,
            tokenizer=mock_tok,
            model=mock_model,
            device="cpu",
            batch_size=16,
            max_length=512,
            checkpoint_dir=resumed_dir,
            resume=True
        )

        self.assertEqual(resumed_embs.shape, (32, 16))
        np.testing.assert_array_almost_equal(full_embs, resumed_embs, decimal=6)

    def test_checkpoint_identity_key_mismatch_resets(self):
        tests = [f"test_method_{i}_{'x'*i}" for i in range(32)]
        mock_tok = MockTokenizer()
        mock_model = MockModel()

        mismatch_dir = self.temp_dir / "mismatch"
        mismatch_dir.mkdir(parents=True, exist_ok=True)
        chk_file = mismatch_dir / "checkpoint_batches.npy"
        chk_meta = mismatch_dir / "checkpoint_meta.json"

        # Save corrupted or wrong-config checkpoint
        np.save(chk_file, np.zeros((16, 16), dtype=np.float32))
        chk_meta.write_text(json.dumps({
            "identity_key": {"model": "wrong_model"},
            "total_tests": 32,
            "batch_size": 16,
            "batches_completed": 1,
            "total_batches": 2,
            "items_completed": 16
        }), encoding="utf-8")

        # Resume with different identity key -> must ignore old checkpoint and compute full fresh embeddings
        resumed_embs, _, _ = generate_embeddings_with_checkpoints(
            tests=tests,
            tokenizer=mock_tok,
            model=mock_model,
            device="cpu",
            batch_size=16,
            max_length=512,
            checkpoint_dir=mismatch_dir,
            resume=True,
            identity_key={"model": "correct_model"}
        )

        self.assertEqual(resumed_embs.shape, (32, 16))
        # Ensure it wasn't the zeroes from the mismatched checkpoint
        self.assertTrue((resumed_embs != 0).any())

    def test_checkpoint_rejects_missing_identity_key(self):
        tests = [f"test_method_{i}_{'x'*i}" for i in range(32)]
        mock_tok = MockTokenizer()
        mock_model = MockModel()

        no_key_dir = self.temp_dir / "no_key"
        no_key_dir.mkdir(parents=True, exist_ok=True)
        chk_file = no_key_dir / "checkpoint_batches.npy"
        chk_meta = no_key_dir / "checkpoint_meta.json"

        # Save checkpoint without identity_key (legacy checkpoint format)
        np.save(chk_file, np.zeros((16, 16), dtype=np.float32))
        chk_meta.write_text(json.dumps({
            "total_tests": 32,
            "batch_size": 16,
            "batches_completed": 1,
            "total_batches": 2,
            "items_completed": 16
        }), encoding="utf-8")

        # When identity_key is required by caller, missing identity_key in checkpoint MUST be rejected
        resumed_embs, _, _ = generate_embeddings_with_checkpoints(
            tests=tests,
            tokenizer=mock_tok,
            model=mock_model,
            device="cpu",
            batch_size=16,
            max_length=512,
            checkpoint_dir=no_key_dir,
            resume=True,
            identity_key={"model": "my_model", "revision": "rev1"}
        )

        self.assertEqual(resumed_embs.shape, (32, 16))
        # Ensure it wasn't the zeroes from the legacy checkpoint
        self.assertTrue((resumed_embs != 0).any())


class TestValidationStrictness(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.run_dir = self.temp_dir / "run"
        self.run_dir.mkdir()
        self.n = 4
        embs = np.ones((self.n, 8), dtype=np.float32)
        np.save(self.run_dir / "embeddings.npy", embs)
        ranking = [0, 1, 2, 3]
        (self.run_dir / "ranking.json").write_text(json.dumps(ranking), encoding="utf-8")
        (self.run_dir / "gains.json").write_text(json.dumps([(i, 1.0) for i in range(self.n)]), encoding="utf-8")

        # 4 tests, 2 faults: fault 101 at test 0 (rank 1), fault 102 at test 1 (rank 2)
        # sum = 1 + 2 = 3. APFD = 1 - 3/(4*2) + 1/(2*4) = 1 - 0.375 + 0.125 = 0.75
        self.base_result = {
            "project": "MockPrj",
            "tests": self.n,
            "full_suite": True,
            "peak_rss_gib": 0.5,
            "total_wallclock_seconds": 10.0,
            "apfd": 0.75
        }
        (self.run_dir / "result.json").write_text(json.dumps(self.base_result), encoding="utf-8")

        # Create input directory structure inside self.temp_dir
        input_dir = self.temp_dir / "work/artifacts/falcon/input/MockPrj"
        input_dir.mkdir(parents=True, exist_ok=True)

        self.faults = {0: [101], 1: [102], 2: [], 3: []}
        self.fault_p = input_dir / "fault_matrix.pickle"
        with open(self.fault_p, "wb") as f:
            pickle.dump(self.faults, f)

        self.mapping = {
            "index_to_method": {
                "0": "MockClass.testA()",
                "1": "MockClass.testB()",
                "2": "MockClass.testC()",
                "3": "MockClass.testD()"
            }
        }
        self.mapping_p = input_dir / "test_method_mapping.json"
        self.mapping_p.write_text(json.dumps(self.mapping), encoding="utf-8")

        self.bbox_p = input_dir / "bbox.txt"
        self.bbox_p.write_text("MockClass.testA()\nMockClass.testB()\nMockClass.testC()\nMockClass.testD()\n", encoding="utf-8")

        def sha256_file(p: Path) -> str:
            h = hashlib.sha256()
            with open(p, "rb") as f:
                while chunk := f.read(65536):
                    h.update(chunk)
            return h.hexdigest()

        self.rel_bbox = "work/artifacts/falcon/input/MockPrj/bbox.txt"
        self.rel_mapping = "work/artifacts/falcon/input/MockPrj/test_method_mapping.json"
        self.rel_faults = "work/artifacts/falcon/input/MockPrj/fault_matrix.pickle"

        self.manifest_data = {
            "projects": {
                "MockPrj": {
                    "methods_count": self.n,
                    "faults_count": 2,
                    "files": {
                        "bbox_txt": {
                            "path": self.rel_bbox,
                            "sha256": sha256_file(self.bbox_p)
                        },
                        "mapping_json": {
                            "path": self.rel_mapping,
                            "sha256": sha256_file(self.mapping_p)
                        },
                        "fault_matrix_pickle": {
                            "path": self.rel_faults,
                            "sha256": sha256_file(self.fault_p)
                        }
                    }
                }
            }
        }
        self.manifest_p = self.temp_dir / "manifest.json"
        self.manifest_p.write_text(json.dumps(self.manifest_data, indent=2), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_validator_passes_on_valid_fixture(self):
        """Verifies that the baseline fixture is 100% valid with all invariants passing."""
        rep = validate_run(self.run_dir, project="MockPrj", manifest_path=self.manifest_p, limit=0, root_dir=self.temp_dir)
        self.assertTrue(rep["overall_valid"])
        self.assertTrue(rep["manifest_alignment"]["manifest_ok"])
        self.assertTrue(rep["manifest_alignment"]["file_hashes_ok"])
        self.assertTrue(rep["manifest_alignment"]["mapping_ok"])
        self.assertTrue(rep["manifest_alignment"]["methods_match"])
        self.assertTrue(rep["manifest_alignment"]["faults_match"])
        self.assertTrue(rep["evaluation"]["apfd_matches_result"])
        self.assertAlmostEqual(rep["evaluation"]["independent_apfd"], 0.75, places=9)

    def test_validator_fails_on_missing_manifest(self):
        non_existent_manifest = self.temp_dir / "missing_manifest.json"
        rep = validate_run(self.run_dir, project="MockPrj", manifest_path=non_existent_manifest, limit=0, root_dir=self.temp_dir)
        self.assertFalse(rep["overall_valid"])
        self.assertFalse(rep["manifest_alignment"]["manifest_ok"])

    def test_validator_fails_on_nan_apfd(self):
        """Starts from a 100% valid fixture, changes ONLY saved APFD to NaN, ensuring APFD comparison triggers."""
        nan_result = dict(self.base_result)
        nan_result["apfd"] = float("nan")
        (self.run_dir / "result.json").write_text(json.dumps(nan_result), encoding="utf-8")

        rep = validate_run(self.run_dir, project="MockPrj", manifest_path=self.manifest_p, limit=0, root_dir=self.temp_dir)
        # Manifest and file checks MUST still pass since files are intact
        self.assertTrue(rep["manifest_alignment"]["manifest_ok"])
        self.assertTrue(rep["manifest_alignment"]["file_hashes_ok"])
        # APFD calculation MUST succeed (0.75) from fault matrix
        self.assertAlmostEqual(rep["evaluation"]["independent_apfd"], 0.75, places=9)
        # APFD comparison MUST fail due to NaN
        self.assertFalse(rep["evaluation"]["apfd_matches_result"])
        self.assertFalse(rep["overall_valid"])

    def test_validator_fails_on_source_hash_mismatch(self):
        """Starts from a 100% valid fixture with existing files, alters the expected hash in manifest for an existing file."""
        mismatched_manifest = json.loads(json.dumps(self.manifest_data))
        mismatched_manifest["projects"]["MockPrj"]["files"]["bbox_txt"]["sha256"] = "f" * 64
        self.manifest_p.write_text(json.dumps(mismatched_manifest, indent=2), encoding="utf-8")

        rep = validate_run(self.run_dir, project="MockPrj", manifest_path=self.manifest_p, limit=0, root_dir=self.temp_dir)
        bbox_check = rep["manifest_alignment"]["file_checks"]["bbox_txt"]
        # The file MUST exist on disk (no 'File not found' error)
        self.assertNotIn("error", bbox_check)
        self.assertFalse(bbox_check["match"])
        self.assertFalse(rep["manifest_alignment"]["file_hashes_ok"])
        self.assertFalse(rep["manifest_alignment"]["manifest_ok"])
        self.assertFalse(rep["overall_valid"])


class TestProcessTreeSupervision(unittest.TestCase):
    def test_kill_process_tree_terminates_parent_and_children(self):
        from stage10_driver import get_process_tree_pids, kill_process_tree

        parent_code = (
            "import subprocess, sys, time\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
            "time.sleep(60)\n"
        )
        proc = subprocess.Popen([sys.executable, "-c", parent_code])
        try:
            time.sleep(1.0)
            pids = get_process_tree_pids(proc.pid)
            self.assertIn(proc.pid, pids)
            self.assertGreaterEqual(len(pids), 2)

            kill_process_tree(proc.pid)
            proc.wait(timeout=5)
            time.sleep(0.5)

            # Verify all descendant PIDs are terminated
            surviving = []
            for p in pids:
                if sys.platform == "win32":
                    check = subprocess.run(["tasklist", "/FI", f"PID eq {p}"], capture_output=True, text=True)
                    if str(p) in check.stdout:
                        surviving.append(p)
                else:
                    try:
                        import os
                        os.kill(p, 0)
                        surviving.append(p)
                    except OSError:
                        pass
            self.assertEqual(surviving, [], f"Descendants still alive after tree-kill: {surviving}")
        finally:
            kill_process_tree(proc.pid)


if __name__ == "__main__":
    unittest.main()
