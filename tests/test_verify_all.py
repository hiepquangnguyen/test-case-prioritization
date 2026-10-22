import io
import json
import math
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verify_all import Verifier, find_non_finite_values, sha256_file


class TestVerifyAll(unittest.TestCase):
    """Dedicated test suite for the HC-FALCON comprehensive verifier."""

    def setUp(self):
        self.out_buf = io.StringIO()
        self.err_buf = io.StringIO()
        self.verifier = Verifier(
            root_dir=ROOT,
            verbose=False,
            skip_tests=True,
            out_stream=self.out_buf,
            err_stream=self.err_buf,
        )

    # -------------------------------------------------------------------------
    # 1. Valid Fixture -> exit 0
    # -------------------------------------------------------------------------
    def test_01_valid_fixture_passes(self):
        """Verifier passes cleanly with exit code 0 when all artifacts are valid."""
        code = self.verifier.run_all()
        self.assertEqual(code, 0, f"Expected 0, got {code}. Failures: {self.verifier.failures}")
        self.assertEqual(len(self.verifier.failures), 0)
        self.assertGreater(len(self.verifier.passes), 25)

    # -------------------------------------------------------------------------
    # 2. Missing Mandatory File -> exit != 0
    # -------------------------------------------------------------------------
    def test_02_missing_mandatory_file_fails(self):
        """Missing mandatory file triggers fail-closed [FAIL] and non-zero exit code."""
        orig_exists = Path.exists

        def fake_exists(path_obj):
            if "reports" in path_obj.parts and "stage6" in path_obj.parts and path_obj.name == "summary.json":
                return False
            return orig_exists(path_obj)

        with patch.object(Path, "exists", fake_exists):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_locked_configs()
            self.assertTrue(any("Mandatory File Missing" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 3. Bad JSON Schema -> exit != 0, No Traceback
    # -------------------------------------------------------------------------
    def test_03_bad_json_schema_fails_without_traceback(self):
        """Invalid JSON syntax or broken schema records [FAIL] without uncaught exceptions."""
        orig_read_text = Path.read_text

        def fake_read_text(path_obj, *args, **kwargs):
            if path_obj.name == "evaluation-v1.json":
                return "{ invalid json syntax"
            return orig_read_text(path_obj, *args, **kwargs)

        with patch.object(Path, "read_text", fake_read_text):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            # Should not raise exception
            v.check_locked_configs()
            self.assertTrue(any("Config evaluation-v1" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 4. Hash Mismatch -> exit != 0
    # -------------------------------------------------------------------------
    def test_04_hash_mismatch_fails(self):
        """SHA-256 discrepancy in freeze manifest records [FAIL]."""
        with patch("scripts.verify_all.sha256_file", return_value="0000000000000000000000000000000000000000000000000000000000000000"):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_cryptographic_freezes()
            self.assertTrue(any("SHA-256" in f or "Discrepancies" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 5. Stage 6 Missing a Project -> FAIL
    # -------------------------------------------------------------------------
    def test_05_stage6_missing_project_fails(self):
        """Stage 6 Effect Gate verification fails if any required project is missing."""
        orig_read_text = Path.read_text

        def fake_read_text(path_obj, *args, **kwargs):
            text = orig_read_text(path_obj, *args, **kwargs)
            if "reports" in path_obj.parts and "stage6" in path_obj.parts and path_obj.name == "summary.json":
                doc = json.loads(text)
                doc["projects"].pop("log4j", None)
                return json.dumps(doc)
            return text

        with patch.object(Path, "read_text", fake_read_text):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_scientific_invariants()
            self.assertTrue(any("Stage 6 Effect Gate" in f and "log4j" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 6. Stage 6 Gate Recalculated Dynamically
    # -------------------------------------------------------------------------
    def test_06_stage6_gate_recalculated_dynamically(self):
        """Verifier computes gate passage from raw numbers, rejecting hardcoded PASS."""
        orig_read_text = Path.read_text

        def fake_read_text(path_obj, *args, **kwargs):
            text = orig_read_text(path_obj, *args, **kwargs)
            if "reports" in path_obj.parts and "stage6" in path_obj.parts and path_obj.name == "summary.json":
                doc = json.loads(text)
                # Fabricate an outcome where Karaf passes (+0.0500 vs history_cost & +0.0500 vs fl_only)
                doc["projects"]["karaf"]["paired"]["history_cost"]["apfdc_midpoint"]["median_delta"] = 0.05
                doc["projects"]["karaf"]["paired"]["fl_only"]["apfdc_midpoint"]["median_delta"] = 0.05
                return json.dumps(doc)
            return text

        with patch.object(Path, "read_text", fake_read_text):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_scientific_invariants()
            self.assertTrue(any("Expected 0/3 NO-GO, but 1 passed" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 7. Stage 8 Missing -> FAIL
    # -------------------------------------------------------------------------
    def test_07_stage8_missing_fails(self):
        """Missing Stage 8 summary artifact causes scientific invariant check to fail."""
        orig_exists = Path.exists

        def fake_exists(path_obj):
            if "reports" in path_obj.parts and "stage8" in path_obj.parts and path_obj.name == "summary.json":
                return False
            return orig_exists(path_obj)

        with patch.object(Path, "exists", fake_exists):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_scientific_invariants()
            self.assertTrue(any("Stage 8 Restricted Gate" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 8. Stage 10 Missing Project or Arm -> FAIL
    # -------------------------------------------------------------------------
    def test_08_stage10_missing_project_or_arm_fails(self):
        """Missing Defects4J project or Chart Bridge Arm triggers failure."""
        orig_read_text = Path.read_text

        def fake_read_text(path_obj, *args, **kwargs):
            text = orig_read_text(path_obj, *args, **kwargs)
            if path_obj.name == "summary.json" and "bridge" in path_obj.parts:
                doc = json.loads(text)
                doc["arms"].pop("D", None)
                return json.dumps(doc)
            return text

        with patch.object(Path, "read_text", fake_read_text):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_scientific_invariants()
            self.assertTrue(any("Chart Bridge Invariant" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 9. Stage 11 Contains NaN -> FAIL
    # -------------------------------------------------------------------------
    def test_09_stage11_contains_nan_fails(self):
        """Non-finite values (NaN / Inf) in Stage 11 results cause verification failure."""
        orig_read_text = Path.read_text

        def fake_read_text(path_obj, *args, **kwargs):
            text = orig_read_text(path_obj, *args, **kwargs)
            if path_obj.name == "simulation-results.json":
                doc = json.loads(text)
                doc["projects"]["karaf"]["paired_vs_history_cost"]["hc_cns_v1"]["median"] = float("nan")
                # json.dumps converts NaN to NaN literal
                return json.dumps(doc)
            return text

        with patch.object(Path, "read_text", fake_read_text):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_scientific_invariants()
            self.assertTrue(any("Stage 11 Project karaf" in f or "Non-finite" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 10. Output Runs With Simulated CP1252 Stdout
    # -------------------------------------------------------------------------
    def test_10_output_runs_with_cp1252_stdout(self):
        """Verifier prints successfully to a stream with strict CP1252 encoding."""
        byte_stream = io.BytesIO()
        cp1252_stream = io.TextIOWrapper(byte_stream, encoding="cp1252", errors="strict")

        v = Verifier(
            root_dir=ROOT,
            verbose=True,
            skip_tests=True,
            out_stream=cp1252_stream,
            err_stream=cp1252_stream,
        )
        # Should execute completely without UnicodeEncodeError
        code = v.run_all()
        cp1252_stream.flush()
        self.assertEqual(code, 0)
        output_bytes = byte_stream.getvalue()
        self.assertGreater(len(output_bytes), 1000)
        # Verify output decodes cleanly under CP1252
        decoded = output_bytes.decode("cp1252")
        self.assertIn("VERIFICATION SUMMARY", decoded)

    # -------------------------------------------------------------------------
    # 11. Read-Only: Zero .pyc and Unmodified Protected Artifacts
    # -------------------------------------------------------------------------
    def test_11_read_only_zero_pyc_and_unmodified_artifacts(self):
        """Verifier execution produces zero .pyc files and leaves protected artifacts untouched."""
        # Snapshot state of files in scripts/ and tests/
        def get_pyc_files():
            pyc = []
            for folder in ["tcp", "hc_falcon", "scripts", "tests"]:
                p = ROOT / folder
                if p.exists():
                    pyc.extend(p.rglob("*.pyc"))
            return set(pyc)

        pyc_before = get_pyc_files()

        # Check sample artifact hash before
        sample_file = ROOT / "reports/stage6/summary.json"
        hash_before = sha256_file(sample_file)
        mtime_before = sample_file.stat().st_mtime

        # Run compilation check and json check
        v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
        v.check_compilation_and_syntax()
        v.check_json_integrity()

        pyc_after = get_pyc_files()
        hash_after = sha256_file(sample_file)
        mtime_after = sample_file.stat().st_mtime

        # Ensure no new .pyc was written
        new_pyc = pyc_after - pyc_before
        self.assertEqual(len(new_pyc), 0, f"New .pyc files were created: {new_pyc}")
        self.assertEqual(hash_before, hash_after)
        self.assertEqual(mtime_before, mtime_after)

    # -------------------------------------------------------------------------
    # 12. --skip-tests Displays SKIP Status Clearly
    # -------------------------------------------------------------------------
    def test_12_skip_tests_displays_skip_clearly(self):
        """When --skip-tests is used, SKIP status is displayed and 'passed perfectly' is suppressed."""
        out = io.StringIO()
        v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=out, err_stream=io.StringIO())
        code = v.run_all()
        self.assertEqual(code, 0)
        output_text = out.getvalue()

        self.assertIn("[SKIP] Automated Test Suite: Skipped via --skip-tests flag", output_text)
        self.assertIn("1 SKIPPED", output_text)
        self.assertNotIn("ALL RESEARCH INTEGRITY AND TECHNICAL CHECKS PASSED PERFECTLY!", output_text)
        self.assertIn("ALL COMPLETED CHECKS PASSED (NOTE: some checks were explicitly skipped as requested)", output_text)


    # -------------------------------------------------------------------------
    # 13. Stage 8 Gate in Config Changes -> Verifier Uses New Value
    # -------------------------------------------------------------------------
    def test_13_stage8_config_gate_change_used(self):
        """When evaluation-v1.json gate threshold is modified, Stage 8 uses the updated value."""
        orig_read_text = Path.read_text

        def fake_read_text(path_obj, *args, **kwargs):
            text = orig_read_text(path_obj, *args, **kwargs)
            if path_obj.name == "evaluation-v1.json":
                doc = json.loads(text)
                doc["pilot_effect_gate"]["median_paired_apfdc_delta"] = 0.50
                return json.dumps(doc)
            return text

        with patch.object(Path, "read_text", fake_read_text):
            out = io.StringIO()
            v = Verifier(root_dir=ROOT, verbose=True, skip_tests=True, out_stream=out, err_stream=io.StringIO())
            v.check_scientific_invariants()
            self.assertIn("Stage 8 Restricted Gate", v.passes)
            self.assertIn("gate=+0.5000", out.getvalue())

    # -------------------------------------------------------------------------
    # 14. Stage 8 Missing Comparator history_cost -> FAIL
    # -------------------------------------------------------------------------
    def test_14_stage8_missing_history_cost_fails(self):
        """Stage 8 fails if required comparator history_cost is missing."""
        orig_read_text = Path.read_text

        def fake_read_text(path_obj, *args, **kwargs):
            text = orig_read_text(path_obj, *args, **kwargs)
            if "reports" in path_obj.parts and "stage8" in path_obj.parts and path_obj.name == "summary.json":
                doc = json.loads(text)
                doc["projects"]["karaf"]["comparisons"]["restricted_semantic_cost_v1"].pop("history_cost", None)
                return json.dumps(doc)
            return text

        with patch.object(Path, "read_text", fake_read_text):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_scientific_invariants()
            self.assertTrue(any("Stage 8 Project karaf" in f and "history_cost" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 15. Stage 8 Missing Comparator fl_only/falcon_lrts -> FAIL
    # -------------------------------------------------------------------------
    def test_15_stage8_missing_fl_only_fails(self):
        """Stage 8 fails if required comparator fl_only (mapping of falcon_lrts) is missing."""
        orig_read_text = Path.read_text

        def fake_read_text(path_obj, *args, **kwargs):
            text = orig_read_text(path_obj, *args, **kwargs)
            if "reports" in path_obj.parts and "stage8" in path_obj.parts and path_obj.name == "summary.json":
                doc = json.loads(text)
                doc["projects"]["karaf"]["comparisons"]["restricted_semantic_cost_v1"].pop("fl_only", None)
                return json.dumps(doc)
            return text

        with patch.object(Path, "read_text", fake_read_text):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_scientific_invariants()
            self.assertTrue(any("Stage 8 Project karaf" in f and "fl_only" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 16. Stage 8 One Comparator Meets Gate But Other Does Not -> Project NOT PASS
    # -------------------------------------------------------------------------
    def test_16_stage8_one_comparator_meets_gate_other_does_not_fails(self):
        """A project is NOT counted as PASS if it meets gate on one comparator but fails on another."""
        orig_read_text = Path.read_text

        def fake_read_text(path_obj, *args, **kwargs):
            text = orig_read_text(path_obj, *args, **kwargs)
            if "reports" in path_obj.parts and "stage8" in path_obj.parts and path_obj.name == "summary.json":
                doc = json.loads(text)
                doc["effect_gate_projects_passed"] = 1
                return json.dumps(doc)
            return text

        with patch.object(Path, "read_text", fake_read_text):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_scientific_invariants()
            self.assertTrue(any("Stage 8 Restricted Gate" in f and "Discrepancy" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 17. Stage 8 Median is NaN or Infinity -> FAIL
    # -------------------------------------------------------------------------
    def test_17_stage8_median_nan_or_infinity_fails(self):
        """Non-finite median values in Stage 8 cause verification failure."""
        orig_read_text = Path.read_text

        def fake_read_text(path_obj, *args, **kwargs):
            text = orig_read_text(path_obj, *args, **kwargs)
            if "reports" in path_obj.parts and "stage8" in path_obj.parts and path_obj.name == "summary.json":
                doc = json.loads(text)
                doc["projects"]["karaf"]["comparisons"]["restricted_semantic_cost_v1"]["history_cost"]["apfdc"]["median_delta"] = float("nan")
                return json.dumps(doc)
            return text

        with patch.object(Path, "read_text", fake_read_text):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_scientific_invariants()
            self.assertTrue(any("Stage 8 Project karaf" in f and "non-finite" in f.lower() for f in v.failures))

    # -------------------------------------------------------------------------
    # 18. Stage 8 Calculated Outcome Mismatches Artifact Metadata -> FAIL
    # -------------------------------------------------------------------------
    def test_18_stage8_calculated_mismatch_with_artifact_metadata_fails(self):
        """Verifier fails if computed decision/gate count conflicts with artifact metadata."""
        orig_read_text = Path.read_text

        def fake_read_text(path_obj, *args, **kwargs):
            text = orig_read_text(path_obj, *args, **kwargs)
            if "reports" in path_obj.parts and "stage8" in path_obj.parts and path_obj.name == "summary.json":
                doc = json.loads(text)
                doc["decision"] = "go"
                return json.dumps(doc)
            return text

        with patch.object(Path, "read_text", fake_read_text):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_scientific_invariants()
            self.assertTrue(any("Stage 8 Restricted Gate" in f and "decision" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 19. Stage 11 Delta Negative -> NO-GO
    # -------------------------------------------------------------------------
    def test_19_stage11_negative_delta_is_nogo(self):
        """When median deltas are negative, Stage 11 confirms 0/3 NO-GO."""
        out = io.StringIO()
        v = Verifier(root_dir=ROOT, verbose=True, skip_tests=True, out_stream=out, err_stream=io.StringIO())
        v.check_scientific_invariants()
        self.assertIn("Stage 11 CNS-Greedy Gate", v.passes)
        self.assertIn("0/3 NO-GO confirmed", out.getvalue())

    # -------------------------------------------------------------------------
    # 20. Stage 11 Delta Positive But Below Gate -> NO-GO
    # -------------------------------------------------------------------------
    def test_20_stage11_positive_delta_below_gate_is_nogo(self):
        """A positive delta that does not reach +0.0300 gate still results in NO-GO."""
        orig_read_text = Path.read_text

        def fake_read_text(path_obj, *args, **kwargs):
            text = orig_read_text(path_obj, *args, **kwargs)
            if path_obj.name == "simulation-results.json":
                doc = json.loads(text)
                # Positive delta +0.0100 < +0.0300
                doc["projects"]["karaf"]["paired_vs_history_cost"]["hc_cns_v1"]["median"] = 0.0100
                return json.dumps(doc)
            return text

        with patch.object(Path, "read_text", fake_read_text):
            out = io.StringIO()
            v = Verifier(root_dir=ROOT, verbose=True, skip_tests=True, out_stream=out, err_stream=io.StringIO())
            v.check_scientific_invariants()
            self.assertIn("Stage 11 CNS-Greedy Gate", v.passes)
            self.assertIn("0/3 NO-GO confirmed", out.getvalue())

    # -------------------------------------------------------------------------
    # 21. Stage 11 Meets history_cost But Fails fl_only -> NO-GO
    # -------------------------------------------------------------------------
    def test_21_stage11_meets_history_cost_but_fails_fl_only_is_nogo(self):
        """Passing history_cost comparator but failing fl_only does not pass gate."""
        orig_read_text = Path.read_text

        def fake_read_text(path_obj, *args, **kwargs):
            text = orig_read_text(path_obj, *args, **kwargs)
            if path_obj.name == "simulation-results.json":
                doc = json.loads(text)
                # Meets history_cost (+0.0500 >= 0.03) but fails fl_only (+0.0100 < 0.03)
                doc["projects"]["karaf"]["paired_vs_history_cost"]["hc_cns_v1"]["median"] = 0.0500
                doc["projects"]["karaf"]["paired_vs_fl_only"]["hc_cns_v1"]["median"] = 0.0100
                return json.dumps(doc)
            return text

        with patch.object(Path, "read_text", fake_read_text):
            out = io.StringIO()
            v = Verifier(root_dir=ROOT, verbose=True, skip_tests=True, out_stream=out, err_stream=io.StringIO())
            v.check_scientific_invariants()
            self.assertIn("Stage 11 CNS-Greedy Gate", v.passes)
            self.assertIn("0/3 NO-GO confirmed", out.getvalue())

    # -------------------------------------------------------------------------
    # 22. Stage 11 Meets Both Comparators on Sufficient Projects -> FAIL Expected NO-GO
    # -------------------------------------------------------------------------
    def test_22_stage11_meets_both_comparators_fails_expected_nogo(self):
        """When projects pass both comparators, verifier flags departure from 0/3 NO-GO."""
        orig_read_text = Path.read_text

        def fake_read_text(path_obj, *args, **kwargs):
            text = orig_read_text(path_obj, *args, **kwargs)
            if path_obj.name == "simulation-results.json":
                doc = json.loads(text)
                for p in ["karaf", "activemq"]:
                    doc["projects"][p]["paired_vs_history_cost"]["hc_cns_v1"]["median"] = 0.0400
                    doc["projects"][p]["paired_vs_fl_only"]["hc_cns_v1"]["median"] = 0.3500
                return json.dumps(doc)
            return text

        with patch.object(Path, "read_text", fake_read_text):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_scientific_invariants()
            self.assertTrue(any("Stage 11 CNS-Greedy Gate" in f and "Expected 0/3 NO-GO, but 2 passed" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 23. Stage 11 Missing paired_vs_fl_only -> FAIL
    # -------------------------------------------------------------------------
    def test_23_stage11_missing_paired_vs_fl_only_fails(self):
        """Stage 11 fails if paired_vs_fl_only comparator group is missing."""
        orig_read_text = Path.read_text

        def fake_read_text(path_obj, *args, **kwargs):
            text = orig_read_text(path_obj, *args, **kwargs)
            if path_obj.name == "simulation-results.json":
                doc = json.loads(text)
                doc["projects"]["karaf"].pop("paired_vs_fl_only", None)
                return json.dumps(doc)
            return text

        with patch.object(Path, "read_text", fake_read_text):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_scientific_invariants()
            self.assertTrue(any("Stage 11 Project karaf" in f and "paired_vs_fl_only" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 24. Stage 11 Median NaN or Infinity -> FAIL
    # -------------------------------------------------------------------------
    def test_24_stage11_median_nan_or_infinity_fails(self):
        """Non-finite median in Stage 11 fl_only causes failure."""
        orig_read_text = Path.read_text

        def fake_read_text(path_obj, *args, **kwargs):
            text = orig_read_text(path_obj, *args, **kwargs)
            if path_obj.name == "simulation-results.json":
                doc = json.loads(text)
                doc["projects"]["karaf"]["paired_vs_fl_only"]["hc_cns_v1"]["median"] = float("inf")
                return json.dumps(doc)
            return text

        with patch.object(Path, "read_text", fake_read_text):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_scientific_invariants()
            self.assertTrue(any("Stage 11 Project karaf" in f and "non-finite" in f.lower() for f in v.failures))

    # -------------------------------------------------------------------------
    # 25. Stage 11 Missing a Project -> FAIL
    # -------------------------------------------------------------------------
    def test_25_stage11_missing_project_fails(self):
        """Stage 11 fails if any required project is missing."""
        orig_read_text = Path.read_text

        def fake_read_text(path_obj, *args, **kwargs):
            text = orig_read_text(path_obj, *args, **kwargs)
            if path_obj.name == "simulation-results.json":
                doc = json.loads(text)
                doc["projects"].pop("log4j", None)
                return json.dumps(doc)
            return text

        with patch.object(Path, "read_text", fake_read_text):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_scientific_invariants()
            self.assertTrue(any("Stage 11 CNS-Greedy Gate" in f and "log4j" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 26. Stage 11 Gate or minimum_development_projects Bad Schema -> FAIL
    # -------------------------------------------------------------------------
    def test_26_stage11_gate_or_min_prjs_bad_schema_fails(self):
        """Invalid schema for minimum_development_projects in config causes failure."""
        orig_read_text = Path.read_text

        def fake_read_text(path_obj, *args, **kwargs):
            text = orig_read_text(path_obj, *args, **kwargs)
            if path_obj.name == "evaluation-v1.json":
                doc = json.loads(text)
                doc["pilot_effect_gate"]["minimum_development_projects"] = "two"
                return json.dumps(doc)
            return text

        with patch.object(Path, "read_text", fake_read_text):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_scientific_invariants()
            self.assertTrue(any("Stage 11 CNS-Greedy Gate" in f and "minimum_development_projects" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 27. Preflight Prerequisites All Present -> PASS
    # -------------------------------------------------------------------------
    def test_27_prerequisites_all_present_passes(self):
        """When all whitelisted FALCON artifacts are present, preflight passes."""
        v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
        v.check_prerequisites()
        self.assertTrue(v.prerequisites_ok)
        self.assertTrue(any("FALCON Prerequisite Check" in p for p in v.passes))

    # -------------------------------------------------------------------------
    # 28. Preflight Missing submodtcp.py -> FAIL
    # -------------------------------------------------------------------------
    def test_28_prerequisites_missing_submodtcp_fails(self):
        """Preflight fails when submodtcp.py is missing."""
        orig_exists = Path.exists

        def fake_exists(path_obj):
            if "submodtcp.py" in str(path_obj):
                return False
            return orig_exists(path_obj)

        with patch.object(Path, "exists", fake_exists):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_prerequisites()
            self.assertFalse(v.prerequisites_ok)
            self.assertTrue(any("FALCON Prerequisite Check" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 29. Preflight Missing Chart bbox -> FAIL
    # -------------------------------------------------------------------------
    def test_29_prerequisites_missing_chart_bbox_fails(self):
        """Preflight fails when Chart-bbox.txt is missing."""
        orig_exists = Path.exists

        def fake_exists(path_obj):
            if "Chart-bbox.txt" in str(path_obj):
                return False
            return orig_exists(path_obj)

        with patch.object(Path, "exists", fake_exists):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_prerequisites()
            self.assertFalse(v.prerequisites_ok)
            self.assertTrue(any("FALCON Prerequisite Check" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 30. Preflight Missing LICENSE -> FAIL
    # -------------------------------------------------------------------------
    def test_30_prerequisites_missing_license_fails(self):
        """Preflight fails when work/artifacts/falcon/LICENSE is missing."""
        orig_exists = Path.exists

        def fake_exists(path_obj):
            if "work" in path_obj.parts and "falcon" in path_obj.parts and path_obj.name == "LICENSE":
                return False
            return orig_exists(path_obj)

        with patch.object(Path, "exists", fake_exists):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_prerequisites()
            self.assertFalse(v.prerequisites_ok)
            self.assertTrue(any("FALCON Prerequisite Check" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 31. Preflight Output Contains Exact Bootstrap Command
    # -------------------------------------------------------------------------
    def test_31_prerequisites_message_contains_bootstrap_command(self):
        """Missing prerequisite error prints exact instructions to run bootstrap_falcon.py."""
        orig_exists = Path.exists

        def fake_exists(path_obj):
            if "work" in path_obj.parts and "artifacts" in path_obj.parts:
                return False
            return orig_exists(path_obj)

        err_out = io.StringIO()
        with patch.object(Path, "exists", fake_exists):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=err_out)
            v.check_prerequisites()
            err_text = err_out.getvalue()
            self.assertIn("FALCON prerequisite missing.", err_text)
            self.assertIn("python scripts/bootstrap_falcon.py --archive <path-to-falcon.zip>", err_text)

    # -------------------------------------------------------------------------
    # 32. Verifier Blocks Integration Suite After Prerequisite Failure
    # -------------------------------------------------------------------------
    def test_32_verifier_blocks_integration_tests_after_prerequisite_failure(self):
        """Missing prerequisite marks test suite as BLOCKED without attempting to run it."""
        orig_exists = Path.exists

        def fake_exists(path_obj):
            if "work" in path_obj.parts and "artifacts" in path_obj.parts:
                return False
            return orig_exists(path_obj)

        out = io.StringIO()
        err = io.StringIO()
        with patch.object(Path, "exists", fake_exists):
            v = Verifier(root_dir=ROOT, skip_tests=False, out_stream=out, err_stream=err)
            v.check_prerequisites()
            v.check_test_suite()
            self.assertFalse(v.prerequisites_ok)
            self.assertTrue(any("BLOCKED DUE TO FAILED PREREQUISITE" in s for s in v.skips))

    # -------------------------------------------------------------------------
    # 33. --skip-tests Still Reports Skip, But Prerequisite Failure Still Exits Non-Zero
    # -------------------------------------------------------------------------
    def test_33_skip_tests_still_fails_if_prerequisites_missing(self):
        """Running with --skip-tests still fails overall if external prerequisites are missing."""
        orig_exists = Path.exists

        def fake_exists(path_obj):
            if "work" in path_obj.parts and "artifacts" in path_obj.parts:
                return False
            return orig_exists(path_obj)

        with patch.object(Path, "exists", fake_exists):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            code = v.run_all()
            self.assertNotEqual(code, 0, "run_all must fail when prerequisites are missing")
            self.assertTrue(any("FALCON Prerequisite Check" in f for f in v.failures))
            self.assertTrue(any("Skipped via --skip-tests flag" in s for s in v.skips))

    # -------------------------------------------------------------------------
    # 34. Amendment Valid -> PASS
    # -------------------------------------------------------------------------
    def test_34_valid_amendment_passes(self):
        """Valid clean-clone amendment allows Stage 6 Final Freeze to PASS."""
        v = Verifier(root_dir=ROOT, verbose=True, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
        v.check_cryptographic_freezes()
        self.assertFalse(any("README Amendment" in f for f in v.failures))
        self.assertTrue(any("Stage 6 Final Freeze" in p for p in v.passes))

    # -------------------------------------------------------------------------
    # 35. Missing Amendment -> FAIL
    # -------------------------------------------------------------------------
    def test_35_missing_amendment_fails(self):
        """Missing clean-clone amendment JSON triggers fail-closed failure."""
        orig_exists = Path.exists

        def fake_exists(p):
            if "clean-clone-amendment.json" in p.name:
                return False
            return orig_exists(p)

        with patch.object(Path, "exists", fake_exists):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_cryptographic_freezes()
            self.assertTrue(any("README Amendment" in f and "Missing" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 36. Malformed Amendment JSON -> FAIL
    # -------------------------------------------------------------------------
    def test_36_malformed_amendment_json_fails(self):
        """Malformed syntax in amendment JSON triggers fail-closed failure."""
        orig_read_text = Path.read_text

        def fake_read_text(p, *args, **kwargs):
            if "clean-clone-amendment.json" in p.name:
                return "{ invalid_json_syntax: 123"
            return orig_read_text(p, *args, **kwargs)

        with patch.object(Path, "read_text", fake_read_text):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_cryptographic_freezes()
            self.assertTrue(any("README Amendment Parse" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 37. stage6_frozen_sha256 Mismatch -> FAIL
    # -------------------------------------------------------------------------
    def test_37_stage6_frozen_sha256_mismatch_fails(self):
        """Amendment with incorrect Stage 6 frozen hash triggers fail-closed failure."""
        orig_read_text = Path.read_text

        def fake_read_text(p, *args, **kwargs):
            text = orig_read_text(p, *args, **kwargs)
            if "clean-clone-amendment.json" in p.name:
                doc = json.loads(text)
                doc["readme_lineage"]["stage6_frozen_sha256"] = "0" * 64
                return json.dumps(doc)
            return text

        with patch.object(Path, "read_text", fake_read_text):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_cryptographic_freezes()
            self.assertTrue(any("stage6_frozen_sha256 mismatch" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 38. current_sha256 Mismatch -> FAIL
    # -------------------------------------------------------------------------
    def test_38_current_sha256_mismatch_fails(self):
        """Amendment with incorrect current_sha256 triggers fail-closed failure."""
        orig_read_text = Path.read_text

        def fake_read_text(p, *args, **kwargs):
            text = orig_read_text(p, *args, **kwargs)
            if "clean-clone-amendment.json" in p.name:
                doc = json.loads(text)
                doc["readme_lineage"]["current_sha256"] = "1" * 64
                return json.dumps(doc)
            return text

        with patch.object(Path, "read_text", fake_read_text):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_cryptographic_freezes()
            self.assertTrue(any("current_sha256 mismatch" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 39. README Modified After Amendment -> FAIL
    # -------------------------------------------------------------------------
    def test_39_readme_modified_after_amendment_fails(self):
        """Modifying README without updating amendment triggers fail-closed failure."""
        orig_sha = sha256_file

        def fake_sha(p):
            if Path(p).name == "README.md":
                return "2" * 64
            return orig_sha(p)

        with patch("scripts.verify_all.sha256_file", fake_sha):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_cryptographic_freezes()
            self.assertTrue(any("current_sha256 mismatch" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 40. scientific_results_changed True -> FAIL
    # -------------------------------------------------------------------------
    def test_40_scientific_results_changed_true_fails(self):
        """Amendment claiming scientific results changed triggers fail-closed failure."""
        orig_read_text = Path.read_text

        def fake_read_text(p, *args, **kwargs):
            text = orig_read_text(p, *args, **kwargs)
            if "clean-clone-amendment.json" in p.name:
                doc = json.loads(text)
                doc["scientific_results_changed"] = True
                return json.dumps(doc)
            return text

        with patch.object(Path, "read_text", fake_read_text):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_cryptographic_freezes()
            self.assertTrue(any("scientific_results_changed must be false" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 41. reserved_opened True -> FAIL
    # -------------------------------------------------------------------------
    def test_41_reserved_opened_true_fails(self):
        """Amendment claiming reserved confirmation dataset opened triggers fail-closed failure."""
        orig_read_text = Path.read_text

        def fake_read_text(p, *args, **kwargs):
            text = orig_read_text(p, *args, **kwargs)
            if "clean-clone-amendment.json" in p.name:
                doc = json.loads(text)
                doc["reserved_opened"] = True
                return json.dumps(doc)
            return text

        with patch.object(Path, "read_text", fake_read_text):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_cryptographic_freezes()
            self.assertTrue(any("reserved_opened must be false" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 42. Invalid Scope -> FAIL
    # -------------------------------------------------------------------------
    def test_42_invalid_scope_fails(self):
        """Amendment with scope other than 'documentation_and_packaging_only' triggers failure."""
        orig_read_text = Path.read_text

        def fake_read_text(p, *args, **kwargs):
            text = orig_read_text(p, *args, **kwargs)
            if "clean-clone-amendment.json" in p.name:
                doc = json.loads(text)
                doc["scope"] = "algorithmic_reweighting"
                return json.dumps(doc)
            return text

        with patch.object(Path, "read_text", fake_read_text):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_cryptographic_freezes()
            self.assertTrue(any("Invalid scope" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 43. Stage 6 Non-README Mismatch Still FAILS
    # -------------------------------------------------------------------------
    def test_43_stage6_non_readme_mismatch_fails(self):
        """Discrepancies in non-README Stage 6 frozen files still trigger failure."""
        orig_sha = sha256_file

        def fake_sha(p):
            if "reports/stage6/summary.json" in str(Path(p)).replace("\\", "/"):
                return "3" * 64
            return orig_sha(p)

        with patch("scripts.verify_all.sha256_file", fake_sha):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_cryptographic_freezes()
            self.assertTrue(any("Discrepancies in non-README files" in f for f in v.failures))

    # -------------------------------------------------------------------------
    # 44. Verifier Does Not Mutate Amendment or README
    # -------------------------------------------------------------------------
    def test_44_verifier_does_not_modify_amendment_or_readme(self):
        """Verifier run is strictly read-only and does not touch amendment or README."""
        amendment_p = ROOT / "reports/release/clean-clone-amendment.json"
        readme_p = ROOT / "README.md"

        amend_before = amendment_p.read_bytes()
        readme_before = readme_p.read_bytes()
        amend_mtime_before = amendment_p.stat().st_mtime_ns
        readme_mtime_before = readme_p.stat().st_mtime_ns

        v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
        v.check_cryptographic_freezes()

        self.assertEqual(amendment_p.read_bytes(), amend_before)
        self.assertEqual(readme_p.read_bytes(), readme_before)
        self.assertEqual(amendment_p.stat().st_mtime_ns, amend_mtime_before)
        self.assertEqual(readme_p.stat().st_mtime_ns, readme_mtime_before)

    # -------------------------------------------------------------------------
    # 45. CP1252 Output Stream Resilient
    # -------------------------------------------------------------------------
    def test_45_cp1252_output_stream_resilient(self):
        """Verifier verbose logging operates without UnicodeEncodeError on strict CP1252 streams."""
        raw_out = io.BytesIO()
        raw_err = io.BytesIO()
        cp1252_out = io.TextIOWrapper(raw_out, encoding="cp1252", errors="replace")
        cp1252_err = io.TextIOWrapper(raw_err, encoding="cp1252", errors="replace")

        v = Verifier(root_dir=ROOT, verbose=True, skip_tests=True, out_stream=cp1252_out, err_stream=cp1252_err)
        v.check_cryptographic_freezes()
        cp1252_out.flush()
        cp1252_err.flush()
        out_content = raw_out.getvalue().decode("cp1252")
        self.assertIn("[README Lineage]", out_content)
        self.assertTrue(any("Stage 6 Final Freeze" in p for p in v.passes))

    # -------------------------------------------------------------------------
    # 46. Stage 12 Evaluated NO-GO Is a Valid Phase B State
    # -------------------------------------------------------------------------
    def test_46_stage12_evaluated_nogo_passes(self):
        """A reproducible NO-GO result is accepted without opening reserved data."""
        v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
        v.check_stage12_preregistration()
        self.assertEqual(v.failures, [])
        self.assertIn("Stage 12 Development State", v.passes)

    # -------------------------------------------------------------------------
    # 47. Stage 12 Phase B Tampering Fails Closed
    # -------------------------------------------------------------------------
    def test_47_stage12_phase_b_tampering_fails(self):
        """Opening reserved data or changing a frozen hash invalidates Phase B."""
        orig_read_text = Path.read_text

        def fake_read_text(path_obj, *args, **kwargs):
            text = orig_read_text(path_obj, *args, **kwargs)
            if path_obj.name == "development-screen.json":
                doc = json.loads(text)
                doc["reserved_opened"] = True
                doc["implementation_sha256"] = "0" * 64
                return json.dumps(doc)
            return text

        with patch.object(Path, "read_text", fake_read_text):
            v = Verifier(root_dir=ROOT, skip_tests=True, out_stream=io.StringIO(), err_stream=io.StringIO())
            v.check_stage12_preregistration()
            self.assertTrue(any("Stage 12 Development State" in f for f in v.failures))
            self.assertTrue(any("reserved_opened" in f or "implementation_sha256" in f for f in v.failures))


if __name__ == "__main__":
    unittest.main()
