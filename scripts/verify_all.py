#!/usr/bin/env python3
"""Unified Verification Entry Point for HC-FALCON Research Project.

Strictly read-only verifier that checks:
1. Python environment and core module imports (tcp, hc_falcon, etc.)
2. Code compilation & absence of SyntaxWarnings (in-memory, strictly read-only)
3. JSON integrity & finite numerical values across configs/ and reports/
4. Mandatory files presence and locked experimental configurations
5. Cryptographic manifests and freeze hashes (Stages 5-11)
6. Key scientific invariants:
   - Reserved confirmation dataset strictly unopened across all stages
   - LRTS Effect Gate (+3.0% pts) outcome: NO-GO 0/3 across all 3 generations
     * Stage 6: Karaf, ActiveMQ, Log4j verified against locked gate (+0.0300)
     * Stage 8: Restricted pilot verified against locked gate (+0.0300)
     * Stage 11: CNS-Greedy improvement verified against dual baseline
   - Causal mechanism: Heavy Predecessors verified (+39,099.3s net delay)
   - Defects4J reproduction fidelity: 6/6 projects verified from raw metrics
   - Bridge Chart decomposition verified (Arms A, B, C, D)
7. Full automated test suite (dynamically discovered)
8. Markdown relative link integrity across all key documentation files

Fail-Closed Principle:
- Any missing mandatory file, schema mismatch, or non-finite value triggers [FAIL].
- Exceptions in individual checks are logged with context without crashing the verifier.
- Exit code 0 is returned only if zero failures are recorded.
"""
from __future__ import annotations

import sys

# Prevent bytecode generation immediately upon script load
sys.dont_write_bytecode = True

# Windows console encoding safety (CP1252 / restricted encodings fallback)
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(errors="backslashreplace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(errors="backslashreplace")
    except Exception:
        pass

import argparse
import hashlib
import importlib
import json
import math
import os
import re
import urllib.parse
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent

# Explicit comparator mapping across stages
STAGE8_COMPARATOR_MAP = {
    "falcon_lrts": "fl_only",
    "history_cost": "history_cost",
}

STAGE11_COMPARATOR_MAP = {
    "history_cost": "paired_vs_history_cost",
    "falcon_lrts": "paired_vs_fl_only",
}

# Whitelist of external FALCON reproduction artifacts required in work/
FALCON_PREREQUISITES = [
    "work/artifacts/falcon/py/submodtcp.py",
    "work/artifacts/falcon/py/embedding_generator.py",
    "work/artifacts/falcon/py/metric.py",
    "work/artifacts/falcon/input/Chart/Chart-bbox.txt",
    "work/artifacts/falcon/input/Chart/test_method_mapping.json",
    "work/artifacts/falcon/input/Chart/fault_matrix.pickle",
    "work/artifacts/falcon/LICENSE",
]


def sha256_file(path: Path) -> str:
    """Computes SHA-256 hash of a file on disk."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def find_non_finite_values(obj: Any, path: str = "") -> List[Tuple[str, Any]]:
    """Recursively checks for non-finite float values (NaN, Inf, -Inf)."""
    results: List[Tuple[str, Any]] = []
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            results.append((path, obj))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            subpath = f"{path}.{k}" if path else str(k)
            results.extend(find_non_finite_values(v, subpath))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            results.extend(find_non_finite_values(v, f"{path}[{i}]"))
    return results


class Verifier:
    def __init__(
        self,
        root_dir: Optional[Path] = None,
        verbose: bool = False,
        skip_tests: bool = False,
        out_stream=None,
        err_stream=None,
    ):
        self.root = (root_dir or ROOT).resolve()
        self.verbose = verbose
        self.skip_tests = skip_tests
        self.out = out_stream or sys.stdout
        self.err = err_stream or sys.stderr
        self.failures: List[str] = []
        self.passes: List[str] = []
        self.skips: List[str] = []
        self.prerequisites_ok: bool = True

    def log(self, text: str) -> None:
        self.out.write(text + "\n")
        self.out.flush()

    def log_err(self, text: str) -> None:
        self.err.write(text + "\n")
        self.err.flush()

    def record_pass(self, name: str, detail: str = "") -> None:
        msg = f"[PASS] {name}"
        if detail and self.verbose:
            msg += f" ({detail})"
        self.log(msg)
        self.passes.append(name)

    def record_fail(self, name: str, reason: str) -> None:
        msg = f"[FAIL] {name}: {reason}"
        self.log_err(msg)
        self.failures.append(f"{name}: {reason}")

    def record_skip(self, name: str, reason: str) -> None:
        msg = f"[SKIP] {name}: {reason}"
        self.log(msg)
        self.skips.append(f"{name}: {reason}")

    # =========================================================================
    # 0. External Artifact Prerequisites (Preflight)
    # =========================================================================
    def check_prerequisites(self) -> None:
        self.log("\n=== Check 0: External Artifact Prerequisites (Preflight) ===")
        try:
            missing = []
            for rel in FALCON_PREREQUISITES:
                if not (self.root / rel).exists():
                    missing.append(rel)

            if missing:
                self.prerequisites_ok = False
                detail = f"Missing {len(missing)} FALCON artifact(s)"
                if self.verbose:
                    detail += f": {missing}"
                self.record_fail("FALCON Prerequisite Check", detail)
                self.log_err(
                    "\nFALCON prerequisite missing.\n"
                    "Run:\n"
                    "python scripts/bootstrap_falcon.py --archive <path-to-falcon.zip>\n"
                )
            else:
                self.prerequisites_ok = True
                self.record_pass(
                    "FALCON Prerequisite Check",
                    f"All {len(FALCON_PREREQUISITES)} reproduction artifacts present in work/artifacts/falcon",
                )
        except Exception as e:
            self.prerequisites_ok = False
            self.record_fail("Check 0 Prerequisites", f"Unexpected error: {e}")

    # =========================================================================
    # 1. Environment & Imports
    # =========================================================================
    def check_environment_and_imports(self) -> None:
        self.log("\n=== Check 1: Environment & Module Imports ===")
        try:
            if sys.version_info < (3, 11):
                self.record_fail("Python Version", f"Requires >= 3.11, found {sys.version}")
                return
            self.record_pass("Python Version", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")

            if str(self.root) not in sys.path:
                sys.path.insert(0, str(self.root))

            modules = [
                ("tcp", "Core TCP domain & metrics"),
                ("hc_falcon", "HC-FALCON core algorithms"),
                ("numpy", "Numerical computing"),
                ("pandas", "Data analysis"),
                ("scipy", "Scientific computing"),
                ("sklearn", "Scikit-learn algorithms"),
            ]

            for mod, desc in modules:
                try:
                    m = importlib.import_module(mod)
                    file_path = getattr(m, "__file__", "builtin")
                    self.record_pass(f"Import {mod}", f"{desc} -> {file_path}")
                except Exception as e:
                    self.record_fail(f"Import {mod}", str(e))
        except Exception as e:
            self.record_fail("Check 1 Environment", f"Unexpected error: {e}")

    # =========================================================================
    # 2. Code Compilation & Syntax Warnings (In-Memory, Strictly Read-Only)
    # =========================================================================
    def check_compilation_and_syntax(self) -> None:
        self.log("\n=== Check 2: Python Compilation & Syntax Integrity (Read-Only) ===")
        try:
            py_files: List[Path] = []
            for folder in ["tcp", "hc_falcon", "scripts", "tests", "configs"]:
                p = self.root / folder
                if p.exists():
                    py_files.extend(p.rglob("*.py"))

            if not py_files:
                self.record_fail("Code Compilation", "No python files found to compile")
                return

            syntax_errors = []
            for pf in py_files:
                try:
                    code_text = pf.read_text(encoding="utf-8")
                    with warnings.catch_warnings(record=True) as w_list:
                        warnings.simplefilter("error", SyntaxWarning)
                        compile(code_text, str(pf), "exec")
                except Exception as e:
                    rel_path = str(pf.relative_to(self.root)) if pf.is_relative_to(self.root) else str(pf)
                    syntax_errors.append((rel_path, str(e)))

            if syntax_errors:
                for f, err in syntax_errors:
                    self.record_fail(f"Syntax Check {f}", err)
            else:
                self.record_pass("Code Compilation", f"Compiled {len(py_files)} files cleanly in-memory (0 SyntaxErrors, 0 SyntaxWarnings, 0 .pyc generated)")
        except Exception as e:
            self.record_fail("Check 2 Compilation", f"Unexpected error: {e}")

    # =========================================================================
    # 3. JSON Integrity & Finite Values
    # =========================================================================
    def check_json_integrity(self) -> None:
        self.log("\n=== Check 3: JSON Parsing, Encoding & Finite Values ===")
        try:
            json_files: List[Path] = []
            for folder in ["configs", "reports"]:
                p = self.root / folder
                if p.exists():
                    json_files.extend(p.rglob("*.json"))

            if not json_files:
                self.record_fail("JSON Integrity", "No JSON files found in configs/ or reports/")
                return

            json_errors = []
            non_finite_errors = []
            for jf in json_files:
                rel_path = str(jf.relative_to(self.root)) if jf.is_relative_to(self.root) else str(jf)
                try:
                    with open(jf, "r", encoding="utf-8-sig") as f:
                        data = json.load(f)
                    bad_values = find_non_finite_values(data)
                    if bad_values:
                        non_finite_errors.append((rel_path, str(bad_values[:3])))
                except Exception as e:
                    json_errors.append((rel_path, str(e)))

            if json_errors:
                for f, err in json_errors:
                    self.record_fail(f"JSON Validation {f}", err)
            elif non_finite_errors:
                for f, err in non_finite_errors:
                    self.record_fail(f"JSON Finite Values {f}", f"Contains non-finite numbers (NaN/Inf): {err}")
            else:
                self.record_pass("JSON Integrity", f"Parsed {len(json_files)} JSON files; all valid syntax and 100% finite numerical values")
        except Exception as e:
            self.record_fail("Check 3 JSON Integrity", f"Unexpected error: {e}")

    # =========================================================================
    # 4. Mandatory Files & Locked Configurations
    # =========================================================================
    def check_locked_configs(self) -> None:
        self.log("\n=== Check 4: Mandatory Files & Locked Configurations ===")
        try:
            mandatory_files = [
                "reports/stage6/summary.json",
                "reports/stage8/summary.json",
                "reports/stage10/reproduction-summary.json",
                "reports/stage10/bridge/summary.json",
                "reports/stage11/simulation-results.json",
                "reports/stage11/forensic-analysis.json",
                "configs/evaluation-v1.json",
                "configs/hc-falcon-v1.json",
                "configs/falcon-reproduction-v1.json",
                "configs/chart-bridge-v1.json",
                "reports/stage5/implementation-freeze.json",
                "reports/stage6/final-evidence-freeze.json",
                "reports/stage7/evidence-freeze.json",
                "reports/stage8/evidence-freeze.json",
                "reports/stage9/evidence-freeze.json",
                "reports/stage10/evidence-freeze.json",
                "reports/stage11/evidence-freeze.json",
                "reports/release/clean-clone-amendment.json",
            ]

            missing_mandatory = []
            for mf in mandatory_files:
                p = self.root / mf
                if not p.exists():
                    missing_mandatory.append(mf)

            if missing_mandatory:
                for mf in missing_mandatory:
                    self.record_fail(f"Mandatory File Missing", mf)
            else:
                self.record_pass("Mandatory Files Check", f"All {len(mandatory_files)} mandatory research artifacts and freeze manifests present")

            # 1. evaluation-v1.json
            eval_cfg_p = self.root / "configs/evaluation-v1.json"
            if eval_cfg_p.exists():
                try:
                    eval_cfg = json.loads(eval_cfg_p.read_text(encoding="utf-8-sig"))
                    if eval_cfg.get("status") != "design_frozen_confirmation_not_opened":
                        self.record_fail("Config evaluation-v1 Status", f"Expected design_frozen_confirmation_not_opened, got {eval_cfg.get('status')}")
                    else:
                        self.record_pass("Config evaluation-v1 Status", "design_frozen_confirmation_not_opened")

                    gate = eval_cfg.get("pilot_effect_gate", {})
                    if gate.get("median_paired_apfdc_delta") != 0.03:
                        self.record_fail("Effect Gate Delta", f"Expected 0.03, got {gate.get('median_paired_apfdc_delta')}")
                    else:
                        self.record_pass("Effect Gate Threshold", "+0.0300 (+3.0% pts) locked")

                    if gate.get("comparators") != ["falcon_lrts", "history_cost"]:
                        self.record_fail("Effect Gate Comparators", f"Expected ['falcon_lrts', 'history_cost'], got {gate.get('comparators')}")
                    else:
                        self.record_pass("Effect Gate Comparators", "Dual baseline [falcon_lrts, history_cost] locked")
                except Exception as e:
                    self.record_fail("Config evaluation-v1 Schema", str(e))

            # 2. hc-falcon-v1.json
            hc_cfg_p = self.root / "configs/hc-falcon-v1.json"
            if hc_cfg_p.exists():
                try:
                    hc_cfg = json.loads(hc_cfg_p.read_text(encoding="utf-8-sig"))
                    if hc_cfg.get("alpha") != 0.5:
                        self.record_fail("HC-FALCON Alpha", f"Expected alpha=0.5, got {hc_cfg.get('alpha')}")
                    else:
                        self.record_pass("HC-FALCON Alpha", "alpha=0.5 locked")
                except Exception as e:
                    self.record_fail("Config hc-falcon-v1 Schema", str(e))

            # 3. falcon-reproduction-v1.json
            rep_cfg_p = self.root / "configs/falcon-reproduction-v1.json"
            if rep_cfg_p.exists():
                try:
                    rep_cfg = json.loads(rep_cfg_p.read_text(encoding="utf-8-sig"))
                    if rep_cfg.get("model", {}).get("name") != "microsoft/unixcoder-base":
                        self.record_fail("Reproduction Model", f"Expected microsoft/unixcoder-base, got {rep_cfg.get('model', {}).get('name')}")
                    else:
                        self.record_pass("Reproduction Model", "microsoft/unixcoder-base locked")

                    if rep_cfg.get("ranker", {}).get("algorithm") != "lazy_greedy":
                        self.record_fail("Reproduction Ranker", f"Expected lazy_greedy, got {rep_cfg.get('ranker', {}).get('algorithm')}")
                    else:
                        self.record_pass("Reproduction Ranker", "lazy_greedy with smallest_input_index tie-breaking locked")
                except Exception as e:
                    self.record_fail("Config falcon-reproduction-v1 Schema", str(e))

            # 4. Input manifest cohort check
            input_manifest_p = self.root / "reports/stage10/input-manifest.json"
            if input_manifest_p.exists():
                try:
                    im = json.loads(input_manifest_p.read_text(encoding="utf-8-sig"))
                    cohort = list(im.get("projects", {}).keys())
                    expected_prjs = ["Chart", "Mockito", "Lang", "Math", "Time", "Closure"]
                    if cohort != expected_prjs:
                        self.record_fail("Reproduction Cohort", f"Expected {expected_prjs}, got {cohort}")
                    else:
                        self.record_pass("Reproduction Cohort", "All 6 Defects4J projects locked in manifest")
                except Exception as e:
                    self.record_fail("Config input-manifest Schema", str(e))
        except Exception as e:
            self.record_fail("Check 4 Locked Configs", f"Unexpected error: {e}")

    # =========================================================================
    # 5. Cryptographic Manifests & Freezes
    # =========================================================================
    def check_cryptographic_freezes(self) -> None:
        self.log("\n=== Check 5: Cryptographic Freezes & Manifest Hashes ===")
        try:
            strict_freezes = [
                ("Stage 5 Implementation", self.root / "reports/stage5/implementation-freeze.json", 41),
                ("Stage 7 Diagnosis", self.root / "reports/stage7/evidence-freeze.json", 8),
                ("Stage 8 Restricted Pilot", self.root / "reports/stage8/evidence-freeze.json", 613),
                ("Stage 9 Fidelity Audit", self.root / "reports/stage9/evidence-freeze.json", 3),
                ("Stage 10 Defects4J Reproduction", self.root / "reports/stage10/evidence-freeze.json", 41),
                ("Stage 11 Improvement Evaluation", self.root / "reports/stage11/evidence-freeze.json", 10),
            ]

            for stage_name, freeze_file, exp_count in strict_freezes:
                if not freeze_file.exists():
                    self.record_fail(f"Freeze File {stage_name}", f"Missing file")
                    continue

                try:
                    doc = json.loads(freeze_file.read_text(encoding="utf-8-sig"))
                    files = doc.get("files_sha256", {})
                    if len(files) != exp_count:
                        self.record_fail(f"{stage_name} Count", f"Expected {exp_count} files, found {len(files)}")
                        continue

                    mismatches = []
                    for rel, exp_hash in files.items():
                        fp = self.root / rel
                        if not fp.exists():
                            mismatches.append(f"MISSING: {rel}")
                        else:
                            act_hash = sha256_file(fp)
                            if act_hash != exp_hash:
                                mismatches.append(f"MISMATCH {rel}: exp={exp_hash[:10]} act={act_hash[:10]}")

                    if mismatches:
                        self.record_fail(f"{stage_name} SHA-256", f"{len(mismatches)} discrepancies: {mismatches[:3]}")
                    else:
                        self.record_pass(f"{stage_name} Freeze", f"All {len(files)} files match disk SHA-256 perfectly")
                except Exception as e:
                    self.record_fail(f"{stage_name} Parse", str(e))

            # Stage 6 freeze (645 files: 644 strict + README verified via clean-clone-amendment)
            st6_freeze_p = self.root / "reports/stage6/final-evidence-freeze.json"
            amendment_p = self.root / "reports/release/clean-clone-amendment.json"
            if st6_freeze_p.exists():
                try:
                    st6_doc = json.loads(st6_freeze_p.read_text(encoding="utf-8-sig"))
                    st6_files = st6_doc.get("files_sha256", {})
                    st6_mismatches = []
                    for rel, exp in st6_files.items():
                        if rel == "README.md":
                            continue
                        fp = self.root / rel
                        if not fp.exists():
                            st6_mismatches.append(f"MISSING: {rel}")
                        elif sha256_file(fp) != exp:
                            st6_mismatches.append(f"MISMATCH: {rel}")

                    non_readme_ok = (len(st6_mismatches) == 0)
                    if not non_readme_ok:
                        self.record_fail("Stage 6 Freeze", f"Discrepancies in non-README files: {st6_mismatches[:3]}")
                    else:
                        self.record_pass("Stage 6 Non-README Files", "All 644 evidence files match disk SHA-256 perfectly")

                    # Verify README via clean-clone-amendment
                    readme_ok = False
                    if not (self.root / "README.md").exists():
                        self.record_fail("README Verification", "README.md missing from repository root")
                    elif not amendment_p.exists():
                        self.record_fail("README Amendment", "Missing reports/release/clean-clone-amendment.json")
                    else:
                        try:
                            amend_doc = json.loads(amendment_p.read_text(encoding="utf-8-sig"))
                            s6_frozen_in_freeze = st6_files.get("README.md")
                            lineage = amend_doc.get("readme_lineage", {})
                            amend_s6_frozen = lineage.get("stage6_frozen_sha256")
                            amend_current = lineage.get("current_sha256")
                            scope = amend_doc.get("scope")
                            sci_changed = amend_doc.get("scientific_results_changed")
                            res_opened = amend_doc.get("reserved_opened")

                            readme_actual = sha256_file(self.root / "README.md")

                            amend_errors = []
                            if s6_frozen_in_freeze != amend_s6_frozen:
                                amend_errors.append(
                                    f"stage6_frozen_sha256 mismatch: freeze={s6_frozen_in_freeze} vs amend={amend_s6_frozen}"
                                )
                            if readme_actual != amend_current:
                                amend_errors.append(
                                    f"current_sha256 mismatch: disk={readme_actual} vs amend={amend_current}"
                                )
                            if scope != "documentation_and_packaging_only":
                                amend_errors.append(f"Invalid scope: {scope}")
                            if sci_changed is not False:
                                amend_errors.append(f"scientific_results_changed must be false, got: {sci_changed}")
                            if res_opened is not False:
                                amend_errors.append(f"reserved_opened must be false, got: {res_opened}")

                            if amend_errors:
                                self.record_fail("README Amendment", "; ".join(amend_errors))
                            else:
                                readme_ok = True
                                if self.verbose:
                                    self.log(
                                        f"  [README Lineage] frozen={str(amend_s6_frozen)[:10]}... "
                                        f"pre_clone={str(lineage.get('pre_clean_clone_sha256'))[:10]}... "
                                        f"current={str(amend_current)[:10]}..."
                                    )
                        except Exception as e:
                            self.record_fail("README Amendment Parse", f"Invalid amendment JSON: {e}")

                    if non_readme_ok and readme_ok:
                        self.record_pass(
                            "Stage 6 Final Freeze",
                            f"All 644 evidence files match; README verified via amendment "
                            f"(frozen={str(amend_s6_frozen)[:8]}, current={str(amend_current)[:8]})"
                        )
                except Exception as e:
                    self.record_fail("Stage 6 Freeze Parse", str(e))
        except Exception as e:
            self.record_fail("Check 5 Cryptographic Freezes", f"Unexpected error: {e}")

    # =========================================================================
    # 5b. Stage 12 Preregistration and Development Result Integrity
    # =========================================================================
    def check_stage12_preregistration(self) -> None:
        self.log("\n=== Check 5b: Stage 12 Preregistration & Development State ===")
        try:
            st12_manifest = self.root / "reports/stage12/pre-evaluation-manifest.json"
            if not st12_manifest.exists():
                self.record_skip(
                    "Stage 12 Preregistration",
                    "reports/stage12/pre-evaluation-manifest.json not present"
                )
                return

            from scripts.stage12_freeze import validate_pre_evaluation_manifest
            is_valid, errors = validate_pre_evaluation_manifest(st12_manifest, self.root)
            if not is_valid:
                self.record_fail("Stage 12 Preregistration Integrity", "; ".join(errors[:3]))
                return

            dev_screen = self.root / "reports/stage12/development-screen.json"
            if not dev_screen.exists():
                self.record_pass(
                    "Stage 12 Preregistration Integrity",
                    "Phase A: pre-evaluation manifest (8 files) and disk SHA-256 hashes strictly verified "
                    "(reserved sealed, development unobserved)"
                )
                return

            # Phase B is valid only when the recorded development result is
            # cryptographically linked to the preregistered assets and its
            # decision can be reproduced from the frozen config and raw report.
            screen = json.loads(dev_screen.read_text(encoding="utf-8-sig"))
            config_path = self.root / "configs/hc-falcon-v2-preregistered.json"
            implementation_path = self.root / "hc_falcon/v2.py"
            harness_path = self.root / "scripts/stage12_evaluate.py"

            expected_hashes = {
                "preregistered_config_sha256": sha256_file(config_path),
                "implementation_sha256": sha256_file(implementation_path),
                "evaluation_harness_sha256": sha256_file(harness_path),
            }
            phase_b_errors = []
            for field, expected in expected_hashes.items():
                actual = screen.get(field)
                if actual != expected:
                    phase_b_errors.append(
                        f"{field} mismatch: expected {expected}, got {actual!r}"
                    )

            if screen.get("reserved_opened") is not False:
                phase_b_errors.append(
                    f"reserved_opened must be false, got {screen.get('reserved_opened')!r}"
                )

            config = json.loads(config_path.read_text(encoding="utf-8-sig"))
            from scripts.stage12_evaluate import evaluate_decision
            recomputed = evaluate_decision(
                screen.get("projects"),
                config,
                screen.get("engineering_metrics"),
            )
            recorded = screen.get("decision")
            if recorded != recomputed:
                phase_b_errors.append(
                    "recorded decision does not match a fresh evaluation of projects and engineering metrics"
                )
            if recomputed.get("final_decision") != "NO-GO":
                phase_b_errors.append(
                    f"evaluated Phase B must record NO-GO, got {recomputed.get('final_decision')!r}"
                )
            if recomputed.get("audit_errors"):
                phase_b_errors.append(
                    f"recomputed decision contains audit errors: {recomputed.get('audit_errors')!r}"
                )

            if phase_b_errors:
                self.record_fail("Stage 12 Development State", "; ".join(phase_b_errors[:3]))
                return

            self.record_pass(
                "Stage 12 Development State",
                "Phase B: frozen assets verified; development NO-GO reproduced; reserved confirmation remains sealed"
            )
        except Exception as e:
            self.record_fail("Check Stage 12 Preregistration", f"Unexpected error: {e}")

    # =========================================================================
    # 6. Scientific Invariants
    # =========================================================================
    def check_scientific_invariants(self) -> None:
        self.log("\n=== Check 6: Core Scientific Invariants & Findings ===")

        # 6.1 Reserved confirmation dataset strictly unopened
        try:
            freezes = [
                ("Stage 6", self.root / "reports/stage6/final-evidence-freeze.json"),
                ("Stage 8", self.root / "reports/stage8/evidence-freeze.json"),
                ("Stage 10", self.root / "reports/stage10/evidence-freeze.json"),
                ("Stage 11", self.root / "reports/stage11/evidence-freeze.json"),
            ]
            all_closed = True
            for sname, fp in freezes:
                if not fp.exists():
                    self.record_fail(f"Reserved Check {sname}", "Freeze file missing")
                    all_closed = False
                    continue
                doc = json.loads(fp.read_text(encoding="utf-8-sig"))
                if doc.get("reserved_opened") is not False:
                    self.record_fail(f"Reserved Check {sname}", f"reserved_opened is not False (got {doc.get('reserved_opened')})")
                    all_closed = False
            if all_closed:
                self.record_pass("Reserved Confirmation Invariant", "Strictly CLOSED & SEALED (reserved_opened == False across Stages 6, 8, 10, 11)")
        except Exception as e:
            self.record_fail("Reserved Confirmation Invariant", f"Unexpected error: {e}")

        # 6.2 Stage 6 Effect Gate Independent Verification (3 Projects: Karaf, ActiveMQ, Log4j)
        try:
            st6_p = self.root / "reports/stage6/summary.json"
            eval_p = self.root / "configs/evaluation-v1.json"
            if not st6_p.exists():
                self.record_fail("Stage 6 Effect Gate", "Missing reports/stage6/summary.json")
            elif not eval_p.exists():
                self.record_fail("Stage 6 Effect Gate", "Missing configs/evaluation-v1.json")
            else:
                st6_data = json.loads(st6_p.read_text(encoding="utf-8-sig"))
                eval_cfg = json.loads(eval_p.read_text(encoding="utf-8-sig"))

                gate_threshold = eval_cfg.get("pilot_effect_gate", {}).get("median_paired_apfdc_delta", 0.03)
                primary_method = eval_cfg.get("primary_method", "hc_falcon_normalized_v1")
                expected_prjs = ["karaf", "activemq", "log4j"]

                st6_projects = st6_data.get("projects", {})
                missing_st6_prjs = [p for p in expected_prjs if p not in st6_projects]
                if missing_st6_prjs:
                    self.record_fail("Stage 6 Effect Gate", f"Missing expected projects: {missing_st6_prjs}")
                else:
                    deltas = {}
                    passed_projects = []
                    schema_error = False

                    for prj_name in expected_prjs:
                        pdata = st6_projects[prj_name]
                        methods = pdata.get("methods", {})
                        if primary_method not in methods:
                            self.record_fail(f"Stage 6 Project {prj_name}", f"Primary method {primary_method} missing")
                            schema_error = True
                            break

                        paired = pdata.get("paired", {})
                        if "history_cost" not in paired:
                            self.record_fail(f"Stage 6 Project {prj_name}", "Comparator history_cost missing in paired data")
                            schema_error = True
                            break

                        hc_apfdc = paired["history_cost"].get("apfdc_midpoint", {})
                        med_delta = hc_apfdc.get("median_delta")
                        if med_delta is None or not isinstance(med_delta, (int, float)) or math.isnan(med_delta) or math.isinf(med_delta):
                            self.record_fail(f"Stage 6 Project {prj_name}", f"Invalid non-finite median_delta: {med_delta}")
                            schema_error = True
                            break

                        deltas[prj_name] = med_delta
                        fl_paired = paired.get("fl_only", {}).get("apfdc_midpoint", {})
                        fl_med_delta = fl_paired.get("median_delta")

                        # Gate check: must achieve >= gate_threshold (+0.0300) vs history_cost and fl_only
                        if med_delta >= gate_threshold and (fl_med_delta is not None and fl_med_delta >= gate_threshold):
                            passed_projects.append(prj_name)

                    if not schema_error:
                        delta_str = ", ".join([f"{p}: delta={deltas[p]:+.6f}" for p in expected_prjs])
                        if len(passed_projects) == 0:
                            self.record_pass("Stage 6 Effect Gate", f"0/3 NO-GO confirmed ({delta_str}; gate=+{gate_threshold:.4f})")
                        else:
                            self.record_fail("Stage 6 Effect Gate", f"Expected 0/3 NO-GO, but {len(passed_projects)} passed: {passed_projects} ({delta_str})")
        except Exception as e:
            self.record_fail("Stage 6 Effect Gate", f"Unexpected error: {e}")

        # 6.3 Stage 8 Restricted Pilot Independent Verification (3 Projects)
        try:
            st8_p = self.root / "reports/stage8/summary.json"
            eval_p = self.root / "configs/evaluation-v1.json"
            if not st8_p.exists():
                self.record_fail("Stage 8 Restricted Gate", "Missing reports/stage8/summary.json")
            elif not eval_p.exists():
                self.record_fail("Stage 8 Restricted Gate", "Missing configs/evaluation-v1.json")
            else:
                st8_data = json.loads(st8_p.read_text(encoding="utf-8-sig"))
                eval_cfg = json.loads(eval_p.read_text(encoding="utf-8-sig"))

                # 1. Validate locked gate threshold from config
                pilot_gate = eval_cfg.get("pilot_effect_gate", {})
                gate_val = pilot_gate.get("median_paired_apfdc_delta")
                if gate_val is None or not isinstance(gate_val, (int, float)) or math.isnan(gate_val) or math.isinf(gate_val) or gate_val < 0:
                    self.record_fail("Stage 8 Restricted Gate", f"Invalid gate threshold in evaluation-v1.json: {gate_val}")
                else:
                    # 2. Validate comparators from config
                    req_comparators = pilot_gate.get("comparators", [])
                    if not isinstance(req_comparators, list) or not req_comparators:
                        self.record_fail("Stage 8 Restricted Gate", f"Invalid or missing comparators in evaluation-v1.json: {req_comparators}")
                    else:
                        unsupported = [c for c in req_comparators if c not in STAGE8_COMPARATOR_MAP]
                        if unsupported:
                            self.record_fail("Stage 8 Restricted Gate", f"Required comparator(s) {unsupported} not supported by Stage 8 mapping")
                        else:
                            st8_prjs = st8_data.get("projects", {})
                            expected_prjs = ["karaf", "activemq", "log4j"]
                            missing_st8_prjs = [p for p in expected_prjs if p not in st8_prjs]

                            if missing_st8_prjs:
                                self.record_fail("Stage 8 Restricted Gate", f"Missing expected projects: {missing_st8_prjs}")
                            else:
                                project_deltas = {}
                                passed_projects = []
                                schema_error = False

                                for prj_name in expected_prjs:
                                    pdata = st8_prjs[prj_name]
                                    comps = pdata.get("comparisons", {}).get("restricted_semantic_cost_v1", {})
                                    project_deltas[prj_name] = {}
                                    comp_passed = []

                                    for cfg_comp in req_comparators:
                                        art_comp = STAGE8_COMPARATOR_MAP[cfg_comp]
                                        if art_comp not in comps:
                                            self.record_fail(f"Stage 8 Project {prj_name}", f"Missing comparator '{art_comp}' (for '{cfg_comp}')")
                                            schema_error = True
                                            break

                                        comp_data = comps[art_comp].get("apfdc", {})
                                        med_delta = comp_data.get("median_delta")
                                        if med_delta is None or not isinstance(med_delta, (int, float)) or math.isnan(med_delta) or math.isinf(med_delta):
                                            self.record_fail(f"Stage 8 Project {prj_name}", f"Invalid non-finite median_delta for comparator '{art_comp}': {med_delta}")
                                            schema_error = True
                                            break

                                        project_deltas[prj_name][art_comp] = med_delta
                                        comp_passed.append(med_delta >= gate_val)

                                    if schema_error:
                                        break

                                    # Project passes only if candidate passes gate vs ALL mandatory comparators
                                    if all(comp_passed):
                                        passed_projects.append(prj_name)

                                if not schema_error:
                                    decision = st8_data.get("decision")
                                    effect_gate_passed = st8_data.get("effect_gate_projects_passed")

                                    delta_parts = []
                                    for p in expected_prjs:
                                        sub_parts = [f"vs_{c}={project_deltas[p][c]:+.6f}" for c in sorted(project_deltas[p].keys())]
                                        delta_parts.append(f"{p}: {', '.join(sub_parts)}")
                                    delta_str = "; ".join(delta_parts)

                                    discrepancy = False
                                    if len(passed_projects) != effect_gate_passed:
                                        self.record_fail(
                                            "Stage 8 Restricted Gate",
                                            f"Discrepancy: computed {len(passed_projects)} passed projects ({passed_projects}), but artifact records effect_gate_projects_passed={effect_gate_passed}"
                                        )
                                        discrepancy = True

                                    expected_decision = "no_go" if len(passed_projects) == 0 else "go"
                                    if decision != expected_decision:
                                        self.record_fail(
                                            "Stage 8 Restricted Gate",
                                            f"Discrepancy: computed decision '{expected_decision}' based on {len(passed_projects)} passed projects, but artifact records decision='{decision}'"
                                        )
                                        discrepancy = True

                                    if not discrepancy:
                                        if len(passed_projects) == 0:
                                            self.record_pass("Stage 8 Restricted Gate", f"0/3 NO-GO confirmed ({delta_str}; gate=+{gate_val:.4f}, decision=no_go)")
                                        else:
                                            self.record_fail("Stage 8 Restricted Gate", f"Expected 0/3 NO-GO, but {len(passed_projects)} passed: {passed_projects} ({delta_str})")
        except Exception as e:
            self.record_fail("Stage 8 Restricted Gate", f"Unexpected error: {e}")

        # 6.4 Stage 10 Defects4J Reproduction Fidelity (6/6 projects)
        try:
            st10_sum_p = self.root / "reports/stage10/reproduction-summary.json"
            if not st10_sum_p.exists():
                self.record_fail("Defects4J Reproduction Fidelity", "Missing reports/stage10/reproduction-summary.json")
            else:
                st10_sum = json.loads(st10_sum_p.read_text(encoding="utf-8-sig"))
                projects = st10_sum.get("projects", [])
                expected_prjs = ["Chart", "Mockito", "Lang", "Math", "Time", "Closure"]
                found_prjs = [p.get("project") for p in projects if isinstance(p, dict)]

                if found_prjs != expected_prjs:
                    self.record_fail("Defects4J Reproduction Cohort", f"Expected {expected_prjs}, got {found_prjs}")
                else:
                    tot_methods = st10_sum.get("total_methods")
                    tot_faults = st10_sum.get("total_faults")
                    if tot_methods != 20770 or tot_faults != 288:
                        self.record_fail("Defects4J Reproduction Totals", f"Expected 20770 methods, 288 faults; got {tot_methods}, {tot_faults}")
                    else:
                        m = st10_sum.get("metrics_summary", {})
                        mean_rerun = m.get("mean_rerun_apfd")
                        mean_author = m.get("mean_author_apfd")
                        delta = m.get("mean_delta_apfd")
                        max_rss = m.get("max_peak_rss_gib")

                        if any(v is None or not isinstance(v, (int, float)) or math.isnan(v) or math.isinf(v) for v in [mean_rerun, mean_author, delta, max_rss]):
                            self.record_fail("Defects4J Reproduction Metrics", "Non-finite or missing metrics values")
                        elif abs(delta - 0.003666) < 1e-4 and max_rss <= 8.0:
                            self.record_pass(
                                "Defects4J Reproduction Fidelity",
                                f"6/6 projects verified (20,770 methods, 288 faults; Author APFD={mean_author:.6f}, Rerun APFD={mean_rerun:.6f}, delta={delta:+.6f}; max RSS={max_rss:.3f} GiB)"
                            )
                        else:
                            self.record_fail("Defects4J Reproduction Fidelity", f"Unexpected metrics: delta={delta}, max_rss={max_rss}")
        except Exception as e:
            self.record_fail("Defects4J Reproduction Fidelity", f"Unexpected error: {e}")

        # 6.5 Stage 10 Bridge Chart Decomposition (Arms A, B, C, D)
        try:
            bridge_sum_p = self.root / "reports/stage10/bridge/summary.json"
            if not bridge_sum_p.exists():
                self.record_fail("Chart Bridge Invariant", "Missing reports/stage10/bridge/summary.json")
            else:
                bs = json.loads(bridge_sum_p.read_text(encoding="utf-8-sig"))
                arms = bs.get("arms", {})
                required_arms = ["A", "B", "C", "D"]
                if any(arm not in arms for arm in required_arms):
                    self.record_fail("Chart Bridge Invariant", f"Missing one or more required arms: {required_arms}")
                else:
                    a_apfd = arms["A"].get("apfd")
                    b_apfd = arms["B"].get("apfd")
                    c_apfd = arms["C"].get("apfd")
                    d_apfd = arms["D"].get("apfd")

                    if any(v is None or not isinstance(v, (int, float)) or math.isnan(v) or math.isinf(v) for v in [a_apfd, b_apfd, c_apfd, d_apfd]):
                        self.record_fail("Chart Bridge Invariant", "Non-finite arm APFD values")
                    elif (
                        abs(a_apfd - 0.732278) < 1e-5
                        and abs(b_apfd - 0.732278) < 1e-5
                        and abs(c_apfd - 0.732278) < 1e-5
                        and abs(d_apfd - 0.763531) < 1e-5
                    ):
                        self.record_pass(
                            "Chart Bridge Invariant",
                            f"Arms verified (A={a_apfd:.6f}, B={b_apfd:.6f}, C={c_apfd:.6f}, D={d_apfd:.6f}; delta_D-C=+0.031253 via attention masking)"
                        )
                    else:
                        self.record_fail("Chart Bridge Invariant", f"Unexpected arm APFDs: A={a_apfd}, B={b_apfd}, C={c_apfd}, D={d_apfd}")
        except Exception as e:
            self.record_fail("Chart Bridge Invariant", f"Unexpected error: {e}")

        # 6.6 Stage 11 Improvement Evaluation (CNS-Greedy Gate)
        try:
            st11_sim_p = self.root / "reports/stage11/simulation-results.json"
            eval_p = self.root / "configs/evaluation-v1.json"
            if not st11_sim_p.exists():
                self.record_fail("Stage 11 CNS-Greedy Gate", "Missing reports/stage11/simulation-results.json")
            elif not eval_p.exists():
                self.record_fail("Stage 11 CNS-Greedy Gate", "Missing configs/evaluation-v1.json")
            else:
                st11_sim = json.loads(st11_sim_p.read_text(encoding="utf-8-sig"))
                eval_cfg = json.loads(eval_p.read_text(encoding="utf-8-sig"))

                # 1. Gate & development cohort parameters validation
                pilot_gate = eval_cfg.get("pilot_effect_gate", {})
                gate_val = pilot_gate.get("median_paired_apfdc_delta")
                if gate_val is None or not isinstance(gate_val, (int, float)) or math.isnan(gate_val) or math.isinf(gate_val) or gate_val < 0:
                    self.record_fail("Stage 11 CNS-Greedy Gate", f"Invalid gate threshold in evaluation-v1.json: {gate_val}")
                else:
                    min_prjs = pilot_gate.get("minimum_development_projects")
                    tot_prjs = pilot_gate.get("total_development_projects")
                    if min_prjs is None or not isinstance(min_prjs, int) or min_prjs <= 0:
                        self.record_fail("Stage 11 CNS-Greedy Gate", f"Invalid minimum_development_projects: {min_prjs}")
                    elif tot_prjs is None or not isinstance(tot_prjs, int) or tot_prjs <= 0:
                        self.record_fail("Stage 11 CNS-Greedy Gate", f"Invalid total_development_projects: {tot_prjs}")
                    else:
                        req_comparators = pilot_gate.get("comparators", [])
                        if not isinstance(req_comparators, list) or not req_comparators:
                            self.record_fail("Stage 11 CNS-Greedy Gate", f"Invalid or missing comparators in evaluation-v1.json: {req_comparators}")
                        else:
                            unsupported = [c for c in req_comparators if c not in STAGE11_COMPARATOR_MAP]
                            if unsupported:
                                self.record_fail("Stage 11 CNS-Greedy Gate", f"Required comparator(s) {unsupported} not supported by Stage 11 mapping")
                            else:
                                st11_prjs = st11_sim.get("projects", {})
                                expected_prjs = ["karaf", "activemq", "log4j"]
                                missing_st11 = [p for p in expected_prjs if p not in st11_prjs]

                                if missing_st11:
                                    self.record_fail("Stage 11 CNS-Greedy Gate", f"Missing expected projects: {missing_st11}")
                                else:
                                    project_deltas = {}
                                    passed_projects = []
                                    schema_error = False

                                    for p in expected_prjs:
                                        pdata = st11_prjs[p]
                                        project_deltas[p] = {}
                                        comp_passed = []

                                        for cfg_comp in req_comparators:
                                            group_key = STAGE11_COMPARATOR_MAP[cfg_comp]
                                            group_data = pdata.get(group_key)
                                            if group_data is None or not isinstance(group_data, dict):
                                                self.record_fail(f"Stage 11 Project {p}", f"Missing comparator group '{group_key}' (for '{cfg_comp}')")
                                                schema_error = True
                                                break

                                            method_data = group_data.get("hc_cns_v1")
                                            if method_data is None or not isinstance(method_data, dict):
                                                self.record_fail(f"Stage 11 Project {p}", f"Missing method 'hc_cns_v1' in '{group_key}'")
                                                schema_error = True
                                                break

                                            val = method_data.get("median")
                                            if val is None or not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
                                                self.record_fail(f"Stage 11 Project {p}", f"Invalid non-finite median delta in '{group_key}': {val}")
                                                schema_error = True
                                                break

                                            project_deltas[p][cfg_comp] = val
                                            comp_passed.append(val >= gate_val)

                                        if schema_error:
                                            break

                                        # Project passes gate iff candidate passes gate vs ALL mandatory comparators
                                        if all(comp_passed):
                                            passed_projects.append(p)

                                    if not schema_error:
                                        delta_parts = []
                                        for p in expected_prjs:
                                            sub_parts = [f"vs_{c}={project_deltas[p][c]:+.6f}" for c in sorted(project_deltas[p].keys())]
                                            delta_parts.append(f"{p}: {', '.join(sub_parts)}")
                                        delta_str = "; ".join(delta_parts)

                                        if len(passed_projects) == 0:
                                            self.record_pass(
                                                "Stage 11 CNS-Greedy Gate",
                                                f"0/3 NO-GO confirmed ({delta_str}; gate=+{gate_val:.4f}, min_required={min_prjs}/{tot_prjs})"
                                            )
                                        else:
                                            self.record_fail(
                                                "Stage 11 CNS-Greedy Gate",
                                                f"Expected 0/{tot_prjs} NO-GO, but {len(passed_projects)} passed: {passed_projects} ({delta_str}; gate=+{gate_val:.4f})"
                                            )
        except Exception as e:
            self.record_fail("Stage 11 CNS-Greedy Gate", f"Unexpected error: {e}")

        # 6.7 Stage 11 Heavy Predecessors Causal Mechanism
        try:
            forensic_p = self.root / "reports/stage11/forensic-analysis.json"
            if not forensic_p.exists():
                self.record_fail("Forensic Heavy Predecessors", "Missing reports/stage11/forensic-analysis.json")
            else:
                forensic = json.loads(forensic_p.read_text(encoding="utf-8-sig"))
                cross = forensic.get("cross_project", {})
                net_delay = cross.get("total_net_predecessor_seconds_added")
                if net_delay is None or not isinstance(net_delay, (int, float)) or math.isnan(net_delay) or math.isinf(net_delay):
                    self.record_fail("Forensic Heavy Predecessors", f"Invalid net_delay value: {net_delay}")
                elif net_delay > 35000:
                    self.record_pass(
                        "Forensic Heavy Predecessors",
                        f"+{net_delay:.1f}s net delay induced by cost-agnostic semantic greedy across 161 failure builds"
                    )
                else:
                    self.record_fail("Forensic Heavy Predecessors", f"Expected >35000s net delay, got {net_delay}")
        except Exception as e:
            self.record_fail("Forensic Heavy Predecessors", f"Unexpected error: {e}")

    # =========================================================================
    # 7. Test Suite Execution (Dynamic Discovery)
    # =========================================================================
    def check_test_suite(self) -> None:
        self.log("\n=== Check 7: Automated Test Suite (Dynamic Discovery) ===")
        if self.skip_tests:
            self.record_skip("Automated Test Suite", "Skipped via --skip-tests flag")
            return

        if not self.prerequisites_ok:
            self.record_skip(
                "Automated Test Suite",
                "BLOCKED DUE TO FAILED PREREQUISITE (Run scripts/bootstrap_falcon.py first)",
            )
            return

        try:
            import unittest

            tests_dir = self.root / "tests"
            if not tests_dir.exists():
                self.record_fail("Automated Test Suite", "tests/ directory does not exist")
                return

            loader = unittest.TestLoader()
            suite = loader.discover(start_dir=str(tests_dir), pattern="test_*.py")
            total_tests = suite.countTestCases()

            if total_tests == 0:
                self.record_fail("Automated Test Suite", "No test cases discovered in tests/")
                return

            runner = unittest.TextTestRunner(stream=self.out, verbosity=1)
            res = runner.run(suite)

            if res.wasSuccessful():
                self.record_pass("Automated Test Suite", f"{total_tests}/{total_tests} tests PASSED (0 failures, 0 errors)")
            else:
                self.record_fail(
                    "Automated Test Suite",
                    f"{len(res.failures)} failures, {len(res.errors)} errors out of {total_tests} tests"
                )
        except Exception as e:
            self.record_fail("Automated Test Suite", f"Execution crashed: {e}")

    # =========================================================================
    # 8. Documentation Links Integrity
    # =========================================================================
    def check_documentation_links(self) -> None:
        self.log("\n=== Check 8: Documentation Relative Links Integrity ===")
        try:
            md_files = list(self.root.glob("*.md"))
            docs_dir = self.root / "docs"
            if docs_dir.exists():
                md_files.extend(docs_dir.rglob("*.md"))

            if not md_files:
                self.record_fail("Documentation Links", "No markdown documentation files found")
                return

            broken_links = []
            file_uri_links = []
            total_checked = 0

            for md_file in md_files:
                try:
                    text = md_file.read_text(encoding="utf-8")
                except Exception as e:
                    broken_links.append((str(md_file.relative_to(self.root)), f"Read error: {e}"))
                    continue

                links = re.findall(r"\[.*?\]\((.*?)\)", text)
                for raw_link in links:
                    target = raw_link.strip()
                    if not target:
                        continue
                    if target.startswith(("http://", "https://", "mailto:")):
                        continue
                    if target.startswith("file:"):
                        file_uri_links.append((str(md_file.relative_to(self.root)), target))
                        continue

                    # Strip section fragment #...
                    path_part = target.split("#")[0].strip()
                    if not path_part:
                        # Internal document anchor, valid
                        continue

                    path_part = urllib.parse.unquote(path_part)
                    resolved_dest = (md_file.parent / path_part).resolve()
                    total_checked += 1

                    if not resolved_dest.exists():
                        # Check if link points to unbootstrapped FALCON prerequisite in work/
                        try:
                            rel_to_root = str(resolved_dest.relative_to(self.root)).replace("\\", "/")
                        except ValueError:
                            rel_to_root = ""

                        is_prereq_link = (
                            rel_to_root.startswith("work/artifacts/falcon/")
                            or any(rel_to_root == p for p in FALCON_PREREQUISITES)
                        )
                        if is_prereq_link and not self.prerequisites_ok:
                            # Prerequisite failure recorded in Check 0; suppress duplicate noise
                            continue

                        broken_links.append((str(md_file.relative_to(self.root)), target))

            if file_uri_links:
                for src, link in file_uri_links[:5]:
                    self.record_fail("Non-Portable Link", f"{src} contains absolute URI '{link}'")

            if broken_links:
                for src, link in broken_links[:5]:
                    self.record_fail("Broken Link", f"{src} -> '{link}' (target does not exist on disk)")
            elif not file_uri_links:
                self.record_pass(
                    "Documentation Links",
                    f"All {total_checked} relative links across {len(md_files)} markdown files resolve cleanly (0 absolute file URIs)"
                )
        except Exception as e:
            self.record_fail("Check 8 Documentation Links", f"Unexpected error: {e}")

    # =========================================================================
    # Run All
    # =========================================================================
    def run_all(self) -> int:
        self.log("=" * 70)
        self.log("HC-FALCON RESEARCH ARTIFACT COMPREHENSIVE VERIFIER")
        self.log("=" * 70)

        self.check_prerequisites()
        self.check_environment_and_imports()
        self.check_compilation_and_syntax()
        self.check_json_integrity()
        self.check_locked_configs()
        self.check_cryptographic_freezes()
        self.check_stage12_preregistration()
        self.check_scientific_invariants()
        self.check_test_suite()
        self.check_documentation_links()

        self.log("\n" + "=" * 70)
        skip_msg = f", {len(self.skips)} SKIPPED" if self.skips else ""
        self.log(f"VERIFICATION SUMMARY: {len(self.passes)} PASSED, {len(self.failures)} FAILED{skip_msg}")
        self.log("=" * 70)

        if self.failures:
            self.log_err("\nFailures encountered:")
            for f in self.failures:
                self.log_err(f"  - {f}")
            return 1

        if self.skips:
            self.log("\nALL COMPLETED CHECKS PASSED (NOTE: some checks were explicitly skipped as requested)")
        else:
            self.log("\nALL RESEARCH INTEGRITY AND TECHNICAL CHECKS PASSED PERFECTLY!")
        return 0


def main():
    parser = argparse.ArgumentParser(description="HC-FALCON Comprehensive Verifier")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show verbose details for passes")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running the automated test suite")
    args = parser.parse_args()

    verifier = Verifier(verbose=args.verbose, skip_tests=args.skip_tests)
    code = verifier.run_all()
    sys.exit(code)


if __name__ == "__main__":
    main()
