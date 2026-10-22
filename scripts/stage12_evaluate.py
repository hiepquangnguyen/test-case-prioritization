"""Stage 12 Evaluation Harness: HC-FALCON v2 Screening on Development.

Replays all development builds across Karaf, ActiveMQ, Log4j using exact Stage 6
historical snapshots and cached vector embeddings.

Evaluates:
- hc_ugcs_v2 (Preregistered Candidate)
Reproduces read-only without file modification:
- history_cost (Baseline)
- fl_only (Baseline)
- hc_falcon_normalized_v1 (Stage 6 Primary)
- hc_cns_v1 (Stage 11 Candidate A1)

Integrity Requirements:
- Strictly verifies reports/stage12/pre-evaluation-manifest.json before execution.
- Reads Stage 6 inputs and vectors strictly read-only.
- Never accesses or opens reserved confirmation data.
- Evaluates both Effect Gate and Engineering Gates before rendering a GO / NO-GO decision.
- Outputs exclusively to reports/stage12/development-screen.json.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
try:
    import resource
except ImportError:
    resource = None
import statistics
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hc_falcon.v2 import rank_ugcs
from hc_falcon.variants import rank_cns
from scripts.pilot_support import conservative
from scripts.stage5_sources import selected
from scripts.stage12_freeze import PREREGISTRATION_FILES, validate_pre_evaluation_manifest
from tcp.baselines import rank as baseline_rank
from tcp.domain import Outcome
from tcp.history import RollingHistory
from tcp.lrts import load_builds
from tcp.metrics import evaluate

PROJECTS = ['karaf', 'activemq', 'log4j']
STAGE6_DIR = ROOT / 'reports' / 'stage6'
VECTORS_DIR = ROOT / 'work' / 'cache' / 'stage6' / 'vectors'
OUT_DIR = ROOT / 'reports' / 'stage12'
CONFIG_PATH = ROOT / 'configs' / 'hc-falcon-v2-preregistered.json'
PRE_EVAL_MANIFEST_PATH = OUT_DIR / 'pre-evaluation-manifest.json'


def sha256_file(path: Path) -> str:
    """Computes SHA-256 hash of a file on disk."""
    hasher = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_peak_rss_bytes() -> int:
    """Returns peak memory working set / RSS in bytes across platforms."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            pmc = PROCESS_MEMORY_COUNTERS()
            pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            psapi = ctypes.windll.psapi
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                wintypes.DWORD,
            ]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            if psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
                return int(pmc.PeakWorkingSetSize)
        except Exception:
            pass
    if resource is not None:
        try:
            rusage = resource.getrusage(resource.RUSAGE_SELF)
            if sys.platform == "darwin":
                return int(rusage.ru_maxrss)
            return int(rusage.ru_maxrss * 1024)
        except Exception:
            pass
    return 0


def compute_kernel(vectors, valid):
    """Computes cosine similarity kernel for valid embeddings."""
    vecs = np.asarray(vectors, dtype=np.float64)
    val = np.asarray(valid, dtype=bool)
    n = len(vecs)
    k = np.zeros((n, n), dtype=np.float64)
    if not val.any():
        return k
    idx = np.where(val)[0]
    sub = vecs[idx]
    norms = np.linalg.norm(sub, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    sub = sub / norms
    sub_k = np.clip(sub @ sub.T, 0.0, 1.0)
    for i_pos, i in enumerate(idx):
        for j_pos, j in enumerate(idx):
            k[i, j] = sub_k[i_pos, j_pos]
    np.fill_diagonal(k, np.where(val, 1.0, 0.0).astype(np.float64))
    return k


def percentile(data, p):
    """Calculates percentile with linear interpolation."""
    if not data:
        return None
    s = sorted(data)
    k = (len(s) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (k - f) * (s[c] - s[f])


def describe_deltas(values):
    """Descriptive statistics for paired deltas."""
    if not values:
        return {
            'count': 0,
            'mean': None,
            'median': None,
            'std': None,
            'min': None,
            'max': None,
            'p5': None,
            'p25': None,
            'p75': None,
            'p95': None,
            'pos': 0,
            'neg': 0,
            'tie': 0,
        }
    return {
        'count': len(values),
        'mean': statistics.mean(values),
        'median': statistics.median(values),
        'std': statistics.stdev(values) if len(values) > 1 else 0.0,
        'min': min(values),
        'max': max(values),
        'p5': percentile(values, 5),
        'p25': percentile(values, 25),
        'p75': percentile(values, 75),
        'p95': percentile(values, 95),
        'pos': sum(1 for v in values if v > 1e-12),
        'neg': sum(1 for v in values if v < -1e-12),
        'tie': sum(1 for v in values if abs(v) <= 1e-12),
    }


def compute_stage_predecessor_delay(
    cand_order: Tuple[str, ...],
    hc_order: Tuple[str, ...],
    domain_outcomes: Tuple[Outcome, ...],
) -> float:
    """Computes net predecessor delay seconds for candidate ranking relative to history_cost.

    Uses the standard Stage 7 / Stage 11 formula:
    For each failing test, added predecessors are tests placed before it in candidate
    that were NOT before it in history_cost; removed predecessors are tests placed before it
    in history_cost that were NOT before it in candidate.
    net_delay = sum(duration of added) - sum(duration of removed).
    """
    outcomes_by_id = {o.test_id: o for o in domain_outcomes}
    failing_ids = [o.test_id for o in domain_outcomes if o.failed]
    if not failing_ids:
        return 0.0

    cand_pos = {tid: idx for idx, tid in enumerate(cand_order)}
    hc_pos = {tid: idx for idx, tid in enumerate(hc_order)}

    stage_net_delay = 0.0
    for fid in failing_ids:
        idx_cand = cand_pos[fid]
        idx_hc = hc_pos[fid]
        preds_cand = set(cand_order[:idx_cand])
        preds_hc = set(hc_order[:idx_hc])
        added = preds_cand - preds_hc
        removed = preds_hc - preds_cand
        added_cost = sum(
            outcomes_by_id[t].duration
            for t in added
            if outcomes_by_id[t].duration is not None and math.isfinite(outcomes_by_id[t].duration)
        )
        removed_cost = sum(
            outcomes_by_id[t].duration
            for t in removed
            if outcomes_by_id[t].duration is not None and math.isfinite(outcomes_by_id[t].duration)
        )
        stage_net_delay += (added_cost - removed_cost)

    return stage_net_delay


def is_valid_number(val: Any, positive_only: bool = False) -> bool:
    """Checks if value is a valid, finite number (rejects booleans, None, NaN, Inf)."""
    if val is None or type(val) is bool or not isinstance(val, (int, float)):
        return False
    if not math.isfinite(val):
        return False
    if positive_only and val <= 0:
        return False
    return True


def is_valid_int(val: Any, non_negative: bool = False, positive_only: bool = False) -> bool:
    """Checks if value is a valid integer (rejects booleans, floats, None)."""
    if val is None or type(val) is bool or type(val) is not int:
        return False
    if non_negative and val < 0:
        return False
    if positive_only and val <= 0:
        return False
    return True


MISSING = object()


def validate_delta_summary(
    summary: Any,
    metric_name: str,
    audit_errors: List[str],
    require_wtl: bool = True,
) -> bool:
    """Validates summary dictionary produced by describe_deltas().

    Fail closed if summary:
    - Not a dictionary.
    - Missing required fields.
    - count is not an actual int (rejects booleans, floats, strings, None), or count <= 0.
    - mean is not a finite number (rejects booleans, None, NaN, Inf, strings).
    - median is not a finite number (rejects booleans, None, NaN, Inf, strings).
    - If require_wtl:
      - pos, neg, tie are not non-negative ints (rejects booleans, floats, strings).
      - pos + neg + tie != count.
    """
    if not isinstance(summary, dict):
        audit_errors.append(f"{metric_name} summary must be a dictionary, got {type(summary).__name__}")
        return False

    is_valid = True

    # 1. count check
    count = summary.get("count")
    if not is_valid_int(count, positive_only=True):
        audit_errors.append(f"{metric_name} count must be positive int, got {count!r}")
        is_valid = False

    # 2. mean check
    mean = summary.get("mean")
    if not is_valid_number(mean):
        audit_errors.append(
            f"{metric_name} mean delta non-finite or missing (non-finite or missing mean delta, got {mean!r})"
        )
        is_valid = False

    # 3. median check
    median = summary.get("median")
    if not is_valid_number(median):
        audit_errors.append(
            f"{metric_name} median delta non-finite or missing (non-finite or missing median delta, got {median!r})"
        )
        is_valid = False

    # 4. W/T/L check
    if require_wtl:
        pos = summary.get("pos")
        neg = summary.get("neg")
        tie = summary.get("tie")
        wtl_valid = True
        if not is_valid_int(pos, non_negative=True):
            audit_errors.append(f"{metric_name} pos must be non-negative int, got {pos!r}")
            wtl_valid = False
        if not is_valid_int(neg, non_negative=True):
            audit_errors.append(f"{metric_name} neg must be non-negative int, got {neg!r}")
            wtl_valid = False
        if not is_valid_int(tie, non_negative=True):
            audit_errors.append(f"{metric_name} tie must be non-negative int, got {tie!r}")
            wtl_valid = False

        if wtl_valid and is_valid_int(count, positive_only=True):
            if pos + neg + tie != count:
                audit_errors.append(
                    f"{metric_name} pos+tie+neg ({pos}+{tie}+{neg}={pos+tie+neg}) != count ({count})"
                )
                wtl_valid = False

        if not wtl_valid:
            is_valid = False

    return is_valid


def validate_preregistered_config(config: Any) -> List[str]:
    """Strictly validates that config contains all mandatory preregistered fields and locked values.

    Fail-closed rules:
    - Missing top-level or section fields -> error.
    - Incorrect types (rejects bool for numbers, floats for ints, non-strings) -> error.
    - Any divergence from locked preregistered constants or governance parameters -> error.
    - No fallback defaults: every required field must be explicitly present and exact.
    """
    errors: List[str] = []
    if not isinstance(config, dict):
        return ["Config must be a dictionary"]

    # 1. Top-level fields
    if config.get("version") != "stage12-hc-falcon-v2-preregistered":
        errors.append(
            f"Invalid or missing version: expected 'stage12-hc-falcon-v2-preregistered', got {config.get('version')!r}"
        )
    if config.get("status") != "preregistered_not_evaluated":
        errors.append(
            f"Invalid or missing status: expected 'preregistered_not_evaluated', got {config.get('status')!r}"
        )
    if config.get("parent_release") != "v0.1.1":
        errors.append(
            f"Invalid or missing parent_release: expected 'v0.1.1', got {config.get('parent_release')!r}"
        )
    if config.get("primary_method") != "hc_ugcs_v2":
        errors.append(
            f"Invalid or missing primary_method: expected 'hc_ugcs_v2', got {config.get('primary_method')!r}"
        )

    # Top-level development_projects (single source of truth)
    dev_projects = config.get("development_projects")
    expected_projects = ["karaf", "activemq", "log4j"]
    if not isinstance(dev_projects, list) or dev_projects != expected_projects:
        errors.append(
            f"Invalid or missing 'development_projects': expected {expected_projects!r}, got {dev_projects!r}"
        )

    # 2. Fixed constants
    fixed = config.get("fixed_constants")
    if not isinstance(fixed, dict):
        errors.append("Missing or invalid 'fixed_constants' dictionary")
    else:
        sw = fixed.get("semantic_weight")
        if type(sw) is bool or sw != 0.25:
            errors.append(f"Invalid semantic_weight: expected 0.25, got {sw!r}")
        zv = fixed.get("z_value")
        if type(zv) is bool or zv != 1.96:
            errors.append(f"Invalid z_value: expected 1.96, got {zv!r}")
        cf = fixed.get("cost_floor")
        if type(cf) is bool or cf != 1e-6:
            errors.append(f"Invalid cost_floor: expected 1e-6, got {cf!r}")
        eps = fixed.get("epsilon")
        if type(eps) is bool or eps != 1e-8:
            errors.append(f"Invalid epsilon: expected 1e-8, got {eps!r}")
        gt = fixed.get("gain_tolerance")
        if type(gt) is bool or gt != 1e-12:
            errors.append(f"Invalid gain_tolerance: expected 1e-12, got {gt!r}")

    # 3. Effect gate
    eff = config.get("effect_gate")
    if not isinstance(eff, dict):
        errors.append("Missing or invalid 'effect_gate' dictionary")
    else:
        if eff.get("metric") != "median_paired_apfdc_delta":
            errors.append(
                f"Invalid effect_gate metric: expected 'median_paired_apfdc_delta', got {eff.get('metric')!r}"
            )
        th = eff.get("threshold")
        if type(th) is bool or th != 0.03:
            errors.append(f"Invalid effect_gate threshold: expected 0.03, got {th!r}")
        comps = eff.get("comparators")
        expected_comps = ["history_cost", "fl_only"]
        if not isinstance(comps, list) or comps != expected_comps:
            errors.append(f"Invalid effect_gate comparators: expected {expected_comps!r}, got {comps!r}")
        min_p = eff.get("minimum_development_projects")
        if type(min_p) is not int or min_p != 2:
            errors.append(f"Invalid minimum_development_projects: expected int 2, got {min_p!r}")
        tot_p = eff.get("total_development_projects")
        if type(tot_p) is not int or tot_p != 3:
            errors.append(f"Invalid total_development_projects: expected int 3, got {tot_p!r}")

    # 4. Engineering gates
    eng = config.get("engineering_gates")
    if not isinstance(eng, dict):
        errors.append("Missing or invalid 'engineering_gates' dictionary")
    else:
        p95 = eng.get("p95_warm_overhead_fraction")
        if type(p95) is bool or p95 != 0.10:
            errors.append(f"Invalid p95_warm_overhead_fraction threshold: expected 0.10, got {p95!r}")
        rss = eng.get("peak_rss_bytes")
        if type(rss) is bool or rss != 8589934592:
            errors.append(f"Invalid peak_rss_bytes threshold: expected 8589934592, got {rss!r}")

    # 5. Runtime protocol
    rp = config.get("runtime_protocol")
    if not isinstance(rp, dict):
        errors.append("Missing or invalid 'runtime_protocol' dictionary")
    else:
        wu = rp.get("warmup_runs")
        if type(wu) is not int or wu < 1:
            errors.append(f"Invalid warmup_runs: expected int >= 1, got {wu!r}")
        rep = rp.get("repetitions")
        if type(rep) is not int or rep < 1:
            errors.append(f"Invalid repetitions: expected int >= 1, got {rep!r}")
        if rp.get("timer") != "perf_counter":
            errors.append(f"Invalid timer: expected 'perf_counter', got {rp.get('timer')!r}")
        if rp.get("overhead_definition") != "relative_to_history_cost_ranking_latency":
            errors.append(
                f"Invalid overhead_definition: expected 'relative_to_history_cost_ranking_latency', got {rp.get('overhead_definition')!r}"
            )

    # 6. Governance
    gov = config.get("governance")
    if not isinstance(gov, dict):
        errors.append("Missing or invalid 'governance' dictionary")
    else:
        if gov.get("reserved_opened") is not False:
            errors.append(f"Invalid reserved_opened: expected False, got {gov.get('reserved_opened')!r}")
        if gov.get("development_evaluated") is not False:
            errors.append(f"Invalid development_evaluated: expected False, got {gov.get('development_evaluated')!r}")
        if gov.get("tuning_rounds_allowed") != 0 or type(gov.get("tuning_rounds_allowed")) is not int:
            errors.append(f"Invalid tuning_rounds_allowed: expected int 0, got {gov.get('tuning_rounds_allowed')!r}")
        if gov.get("confirmation_requires_explicit_human_approval") is not True:
            errors.append(
                f"Invalid confirmation_requires_explicit_human_approval: expected True, got {gov.get('confirmation_requires_explicit_human_approval')!r}"
            )

    # 7. Metrics
    met = config.get("metrics")
    if not isinstance(met, dict):
        errors.append("Missing or invalid 'metrics' dictionary")
    else:
        if met.get("primary") != "median_paired_apfdc_midpoint_delta":
            errors.append(
                f"Invalid primary metric: expected 'median_paired_apfdc_midpoint_delta', got {met.get('primary')!r}"
            )
        sec = met.get("secondary")
        expected_sec = [
            "mean_paired_delta",
            "win_tie_loss",
            "ttff_seconds",
            "recall_at_10pct",
            "predecessor_seconds",
            "runtime_overhead",
            "peak_rss_bytes",
        ]
        if not isinstance(sec, list) or sec != expected_sec:
            errors.append(f"Invalid secondary metrics list: expected {expected_sec!r}, got {sec!r}")

    return errors


def evaluate_decision(
    project_reports: Dict[str, Any],
    config: Dict[str, Any],
    engineering_metrics: Dict[str, Any],
) -> Dict[str, Any]:
    """Pure decision governance function evaluating Stage 12 gates.

    Strict rules:
    1. Preregistered Config Integrity:
       - Every mandatory top-level and section field must be present without fallbacks.
       - Any missing, malformed, or tampered config field strictly forces NO-GO.
    2. Exact Project Set:
       - Requires exactly the preregistered development_projects (no missing, no extra, no substitutions).
       - Validates total_development_projects == len(development_projects).
       - Validates 1 <= minimum_development_projects <= total_development_projects.
    3. Effect Gate:
       - Requires median paired APFDc delta >= threshold vs ALL preregistered comparators
       - on at least minimum_development_projects out of total_development_projects.
    4. Engineering Gates:
       - P95 warm overhead fraction <= threshold
       - Peak RSS bytes <= threshold
       - All mandatory metrics must be validly computed without missing or non-finite values.
    5. Secondary Delta Summaries:
       - TTFF and Recall@10% summaries must be valid dicts with finite mean/median, count > 0,
         and consistent W/T/L counts.
    6. GO decision permitted ONLY if effect gate passes AND all engineering gates pass AND zero audit errors.
    7. Fail-closed: missing data, non-finite values (NaN/Inf), count <= 0, or count mismatches result in NO-GO.
    """
    audit_errors: List[str] = []

    # 1. Strict preregistered config validation (no fallback defaults allowed)
    cfg_errors = validate_preregistered_config(config)
    audit_errors.extend(cfg_errors)

    if not isinstance(config, dict):
        config = {}

    effect_cfg = config.get("effect_gate") if isinstance(config.get("effect_gate"), dict) else {}
    eng_cfg = config.get("engineering_gates") if isinstance(config.get("engineering_gates"), dict) else {}

    primary_cand = config.get("primary_method", MISSING)
    threshold = effect_cfg.get("threshold", MISSING)
    comparators = effect_cfg.get("comparators", MISSING)
    dev_projects = config.get("development_projects", MISSING)
    min_dev_projects = effect_cfg.get("minimum_development_projects", MISSING)
    total_dev_projects = effect_cfg.get("total_development_projects", MISSING)
    p95_overhead_threshold = eng_cfg.get("p95_warm_overhead_fraction", MISSING)
    peak_rss_threshold = eng_cfg.get("peak_rss_bytes", MISSING)

    if dev_projects is MISSING or not isinstance(dev_projects, list) or len(dev_projects) == 0:
        audit_errors.append("Invalid or missing 'development_projects' in preregistered config")
        dev_projects_list: List[str] = []
    else:
        dev_projects_list = list(dev_projects)

    if is_valid_int(total_dev_projects, positive_only=True) and is_valid_int(min_dev_projects, positive_only=True):
        if total_dev_projects != len(dev_projects_list):
            audit_errors.append(
                f"Config mismatch: development_projects count ({len(dev_projects_list)}) != total_development_projects ({total_dev_projects})"
            )
        if min_dev_projects > total_dev_projects:
            audit_errors.append(
                f"Config mismatch: minimum_development_projects ({min_dev_projects}) > total_development_projects ({total_dev_projects})"
            )

    # 2. Check observed projects against expected
    expected_projects_set = set(dev_projects_list)
    observed_projects_set = set(project_reports.keys()) if isinstance(project_reports, dict) else set()

    if not isinstance(project_reports, dict):
        audit_errors.append(f"Invalid project_reports type: expected dict, got {type(project_reports).__name__}")
    else:
        missing_prjs = expected_projects_set - observed_projects_set
        extra_prjs = observed_projects_set - expected_projects_set
        if missing_prjs:
            audit_errors.append(f"Missing required development project reports: {sorted(missing_prjs)}")
        if extra_prjs:
            audit_errors.append(f"Unexpected extra project reports observed: {sorted(extra_prjs)}")

    # 3. Evaluate Project-level Metrics & Effect Gate
    project_effect_results = {}
    passed_projects = []

    for p_name in dev_projects_list:
        if not isinstance(project_reports, dict) or p_name not in project_reports:
            project_effect_results[p_name] = {
                "project_passed": False,
                "reason": f"Project report for {p_name} is missing",
            }
            continue

        p_data = project_reports[p_name]
        if not isinstance(p_data, dict):
            audit_errors.append(f"Project report for {p_name} must be a dict, got {type(p_data).__name__}")
            project_effect_results[p_name] = {
                "project_passed": False,
                "reason": "Invalid project report structure",
            }
            continue

        # Validate physical_builds and stages counts
        phys_builds = p_data.get("physical_builds")
        if not is_valid_int(phys_builds, positive_only=True):
            audit_errors.append(f"Project {p_name} physical_builds must be positive int, got {phys_builds!r}")

        stages_count = p_data.get("stages")
        if not is_valid_int(stages_count, positive_only=True):
            audit_errors.append(f"Project {p_name} stages count must be positive int, got {stages_count!r}")

        # Validate primary effect comparators
        proj_comp_results = {}
        all_comps_met = True

        if comparators is MISSING or not isinstance(comparators, list) or len(comparators) == 0:
            audit_errors.append("Invalid or missing effect_gate comparators")
            all_comps_met = False
        else:
            for comp in comparators:
                paired_key = f"paired_vs_{comp}"
                comp_data = (
                    p_data.get(paired_key, {}).get(primary_cand)
                    if (isinstance(p_data.get(paired_key), dict) and primary_cand is not MISSING)
                    else None
                )
                metric_desc = f"Project {p_name} APFDc vs {comp}"
                is_summary_valid = validate_delta_summary(
                    comp_data,
                    metric_desc,
                    audit_errors,
                    require_wtl=True,
                )

                if not is_summary_valid:
                    all_comps_met = False
                    passed_comp = False
                else:
                    if not is_valid_number(threshold):
                        audit_errors.append(f"Invalid effect_gate threshold: expected finite number, got {threshold!r}")
                        all_comps_met = False
                        passed_comp = False
                    else:
                        med_delta = comp_data.get("median")
                        passed_comp = (med_delta >= threshold)
                        if not passed_comp:
                            all_comps_met = False

                proj_comp_results[comp] = {
                    "median_delta": comp_data.get("median") if isinstance(comp_data, dict) else None,
                    "mean_delta": comp_data.get("mean") if isinstance(comp_data, dict) else None,
                    "count": comp_data.get("count") if isinstance(comp_data, dict) else None,
                    "threshold": threshold if is_valid_number(threshold) else None,
                    "passed": passed_comp,
                }

        # Secondary metrics validation for project
        ttff_data = (
            p_data.get("paired_ttff_vs_history_cost", {}).get(primary_cand)
            if (isinstance(p_data.get("paired_ttff_vs_history_cost"), dict) and primary_cand is not MISSING)
            else None
        )
        validate_delta_summary(
            ttff_data,
            f"Project {p_name} TTFF",
            audit_errors,
            require_wtl=True,
        )

        rec10_data = (
            p_data.get("paired_recall10_vs_history_cost", {}).get(primary_cand)
            if (isinstance(p_data.get("paired_recall10_vs_history_cost"), dict) and primary_cand is not MISSING)
            else None
        )
        validate_delta_summary(
            rec10_data,
            f"Project {p_name} Recall@10%",
            audit_errors,
            require_wtl=True,
        )

        pred_sec = p_data.get("cumulative_predecessor_seconds")
        if not is_valid_number(pred_sec):
            audit_errors.append(f"Project {p_name} non-finite or missing cumulative_predecessor_seconds: {pred_sec!r}")

        project_effect_results[p_name] = {
            "comparators": proj_comp_results,
            "project_passed": all_comps_met,
            "sample_count": phys_builds,
        }

        if all_comps_met:
            passed_projects.append(p_name)

    # 4. Evaluate Engineering Metrics
    if not isinstance(engineering_metrics, dict):
        audit_errors.append(f"Invalid engineering_metrics type: expected dict, got {type(engineering_metrics).__name__}")
        engineering_metrics = {}

    observed_p95_overhead = engineering_metrics.get("p95_warm_overhead_fraction")
    overhead_gate_passed = False
    if not is_valid_number(p95_overhead_threshold):
        audit_errors.append(f"Missing or invalid p95_warm_overhead_fraction threshold: {p95_overhead_threshold!r}")
    elif not is_valid_number(observed_p95_overhead):
        audit_errors.append(f"Non-finite or missing p95_warm_overhead_fraction: {observed_p95_overhead!r}")
    else:
        overhead_gate_passed = (observed_p95_overhead <= p95_overhead_threshold)

    observed_peak_rss = engineering_metrics.get("peak_rss_bytes")
    rss_gate_passed = False
    if not is_valid_number(peak_rss_threshold, positive_only=True):
        audit_errors.append(f"Missing or invalid peak_rss_bytes threshold: {peak_rss_threshold!r}")
    elif not is_valid_number(observed_peak_rss, positive_only=True):
        audit_errors.append(f"Peak RSS bytes missing, non-finite, or <= 0: {observed_peak_rss!r}")
    else:
        rss_gate_passed = (observed_peak_rss <= peak_rss_threshold)

    lat_ugcs = engineering_metrics.get("median_latency_ugcs_seconds")
    if not is_valid_number(lat_ugcs, positive_only=True):
        audit_errors.append(f"Invalid or non-positive median_latency_ugcs_seconds: {lat_ugcs!r}")

    lat_hc = engineering_metrics.get("median_latency_hc_seconds")
    if not is_valid_number(lat_hc, positive_only=True):
        audit_errors.append(f"Invalid or non-positive median_latency_hc_seconds: {lat_hc!r}")

    scored_stages_total = engineering_metrics.get("scored_stages_total")
    if not is_valid_int(scored_stages_total, positive_only=True):
        audit_errors.append(f"Invalid or non-positive scored_stages_total: {scored_stages_total!r}")

    # 5. Determine Gates and Final Decision
    completeness_passed = (len(audit_errors) == 0)
    engineering_gates_passed = overhead_gate_passed and rss_gate_passed and completeness_passed

    min_required = min_dev_projects if is_valid_int(min_dev_projects, positive_only=True) else 999
    total_required = total_dev_projects if is_valid_int(total_dev_projects, positive_only=True) else 999
    effect_gate_passed = (len(passed_projects) >= min_required) and (len(audit_errors) == 0)

    go_decision = effect_gate_passed and engineering_gates_passed and (len(audit_errors) == 0)
    decision_str = (
        f"GO ({len(passed_projects)}/{total_required} projects, engineering gates passed)"
        if go_decision
        else f"NO-GO ({len(passed_projects)}/{total_required} projects passed, eng_passed={engineering_gates_passed})"
    )

    return {
        "final_decision": "GO" if go_decision else "NO-GO",
        "decision_summary": decision_str,
        "expected_projects": list(dev_projects_list),
        "observed_projects": sorted(project_reports.keys()) if isinstance(project_reports, dict) else [],
        "effect_gate": {
            "passed": effect_gate_passed,
            "threshold": threshold if is_valid_number(threshold) else None,
            "comparators": list(comparators) if isinstance(comparators, list) else [],
            "minimum_projects": min_dev_projects if is_valid_int(min_dev_projects, positive_only=True) else None,
            "total_projects": total_dev_projects if is_valid_int(total_dev_projects, positive_only=True) else None,
            "passed_projects_count": len(passed_projects),
            "passed_projects": passed_projects,
            "project_details": project_effect_results,
        },
        "engineering_gates": {
            "all_passed": engineering_gates_passed,
            "overhead_gate": {
                "metric": "p95_warm_overhead_fraction",
                "threshold": p95_overhead_threshold if is_valid_number(p95_overhead_threshold) else None,
                "actual_value": observed_p95_overhead if is_valid_number(observed_p95_overhead) else None,
                "passed": overhead_gate_passed,
            },
            "memory_gate": {
                "metric": "peak_rss_bytes",
                "threshold": peak_rss_threshold if is_valid_number(peak_rss_threshold, positive_only=True) else None,
                "actual_value": observed_peak_rss if is_valid_number(observed_peak_rss, positive_only=True) else None,
                "passed": rss_gate_passed,
            },
            "completeness_gate": {
                "missing_or_invalid_errors": list(audit_errors),
                "passed": completeness_passed,
            },
        },
        "audit_errors": audit_errors,
    }


def verify_preregistration_integrity():
    """Fail-closed pre-evaluation manifest verification before evaluation."""
    validate_pre_evaluation_manifest(PRE_EVAL_MANIFEST_PATH, ROOT, raise_on_error=True)


def run_stage12_evaluation():
    """Main Stage 12 Evaluation execution flow on the Development screening cohort.

    Safety: MUST NOT be called in Phase A.
    """
    print("=" * 80)
    print("STAGE 12: HC-FALCON v2 Screening Evaluation on Development Cohort")
    print("=" * 80)

    verify_preregistration_integrity()
    print("[+] Pre-evaluation manifest verified cleanly.")

    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)

    cfg_errors = validate_preregistered_config(config)
    if cfg_errors:
        raise RuntimeError(f"Preregistered config validation failed: {'; '.join(cfg_errors)}")

    cfg_constants = config["fixed_constants"]
    sem_weight = cfg_constants["semantic_weight"]
    z_val = cfg_constants["z_value"]

    dev_projects = config["development_projects"]
    if dev_projects != list(PROJECTS):
        raise RuntimeError(f"Config development_projects {dev_projects} does not match expected projects {PROJECTS}")

    runtime_cfg = config["runtime_protocol"]
    warmup_runs = runtime_cfg["warmup_runs"]
    timed_repetitions = runtime_cfg["repetitions"]

    vectors_cache = {}
    project_reports = {}

    all_methods = ['history_cost', 'fl_only', 'hc_falcon_normalized_v1', 'hc_cns_v1', 'hc_ugcs_v2']
    stage_warm_overhead_ratios = []
    warm_latencies_ugcs = []
    warm_latencies_hc = []

    for project in dev_projects:
        print(f"\n>>> Project: {project.upper()} <<<")
        start_proj = time.perf_counter()
        old = STAGE6_DIR / project
        ledger = json.loads((old / 'ledger.json').read_text(encoding='utf-8'))

        builds, _ = load_builds(ROOT / 'references/artifacts/dante/ML_TCSP.zip', project, len(selected(project)))
        builds = tuple(map(conservative, builds))

        history = RollingHistory()
        stage_metrics = defaultdict(lambda: defaultdict(dict))
        scored_stages = 0
        cumulative_predecessor_delay = 0.0

        for index, (build, row) in enumerate(zip(builds, ledger)):
            if not row.get('checkpoint'):
                history.observe(build)
                continue

            cp_path = old / 'builds' / row['checkpoint']
            with gzip.open(cp_path, 'rt', encoding='utf-8') as f:
                saved = json.load(f)

            snapshot = history.snapshot(build.inputs)
            history.observe(build)

            failing = [o for o in saved['outcomes'] if o['failed']]
            if not failing:
                continue

            ids = tuple(saved['inventory'])
            domain_outcomes = tuple(Outcome(o['test_id'], o['failed'], o['duration']) for o in saved['outcomes'])
            existing_rankings = {r['method']: r for r in saved['rankings'] if r.get('seed') == 0 or 'seed' not in r}

            phys_key = f"{row['key']['project']}/{row['key']['pr']}/{row['key']['build']}"
            stage_name = row['key']['stage']

            # 1. Historical rankings reproduced read-only from Stage 6
            for m in ['history_cost', 'fl_only', 'hc_falcon_normalized_v1']:
                if m in existing_rankings:
                    stage_metrics[phys_key][m][stage_name] = existing_rankings[m]['metrics']

            # 2. Embeddings kernel
            vectors, valid = [], []
            for src in saved['source']:
                ck = src['cache_key']
                if ck not in vectors_cache:
                    with np.load(VECTORS_DIR / f"{ck}.npz", allow_pickle=False) as c_vec:
                        vectors_cache[ck] = c_vec['vector'].copy()
                vectors.append(vectors_cache[ck])
                valid.append(src['valid'])

            k = compute_kernel(vectors, valid)

            # 3. Stage 11 hc_cns_v1 reproduction
            cns_order = rank_cns(snapshot, ids, k, alpha=0.5)
            stage_metrics[phys_key]['hc_cns_v1'][stage_name] = evaluate(cns_order, domain_outcomes)

            # 4. Primary Candidate: hc_ugcs_v2 & history_cost warm runtime measurement
            hc_order = baseline_rank(snapshot, 'history_cost')

            # Warmup runs
            for _ in range(warmup_runs):
                _ = baseline_rank(snapshot, 'history_cost')
                _ = rank_ugcs(snapshot, ids, k, semantic_weight=sem_weight, z_value=z_val)

            # Timed repetitions for history_cost
            hc_times = []
            for _ in range(timed_repetitions):
                t_start = time.perf_counter()
                _ = baseline_rank(snapshot, 'history_cost')
                hc_times.append(time.perf_counter() - t_start)
            lat_hc = statistics.median(hc_times)
            warm_latencies_hc.append(lat_hc)

            # Timed repetitions for hc_ugcs_v2
            ugcs_times = []
            ugcs_order = None
            for _ in range(timed_repetitions):
                t_start = time.perf_counter()
                ugcs_order = rank_ugcs(snapshot, ids, k, semantic_weight=sem_weight, z_value=z_val)
                ugcs_times.append(time.perf_counter() - t_start)
            lat_ugcs = statistics.median(ugcs_times)
            warm_latencies_ugcs.append(lat_ugcs)

            # Stage warm overhead fraction
            stage_overhead = (lat_ugcs - lat_hc) / max(lat_hc, 1e-9)
            stage_warm_overhead_ratios.append(stage_overhead)

            ugcs_ev = evaluate(ugcs_order, domain_outcomes)
            stage_metrics[phys_key]['hc_ugcs_v2'][stage_name] = ugcs_ev

            # Compute predecessor delay vs history_cost
            stage_pred_delay = compute_stage_predecessor_delay(ugcs_order, hc_order, domain_outcomes)
            cumulative_predecessor_delay += stage_pred_delay

            scored_stages += 1

        physical_keys = sorted(stage_metrics.keys())
        print(f"  Processed {scored_stages} failing stages across {len(physical_keys)} physical builds.")

        # Physical build mean score for APFDc, TTFF, and Recall@10%
        phys_apfdc = {m: {} for m in all_methods}
        phys_ttff = {m: {} for m in all_methods}
        phys_recall10 = {m: {} for m in all_methods}

        for pk in physical_keys:
            for m in all_methods:
                st_dict = stage_metrics[pk].get(m, {})
                apfdc_vals = [s['apfdc_midpoint'] for s in st_dict.values() if s.get('apfdc_midpoint') is not None]
                if apfdc_vals:
                    phys_apfdc[m][pk] = statistics.mean(apfdc_vals)

                ttff_vals = [s['ttff_seconds'] for s in st_dict.values() if s.get('ttff_seconds') is not None and not s.get('ttff_censored')]
                if ttff_vals:
                    phys_ttff[m][pk] = statistics.mean(ttff_vals)

                recall10_vals = [s.get('recall', {}).get('0.1') for s in st_dict.values() if s.get('recall', {}).get('0.1') is not None]
                if recall10_vals:
                    phys_recall10[m][pk] = statistics.mean(recall10_vals)

        # Paired APFDc deltas vs history_cost
        base_hc_apfdc = phys_apfdc['history_cost']
        paired_vs_hc = {}
        for m in all_methods:
            if m == 'history_cost':
                continue
            common = [pk for pk in physical_keys if pk in phys_apfdc[m] and pk in base_hc_apfdc]
            deltas = [phys_apfdc[m][pk] - base_hc_apfdc[pk] for pk in common]
            paired_vs_hc[m] = describe_deltas(deltas)

        # Paired APFDc deltas vs fl_only
        base_fl_apfdc = phys_apfdc['fl_only']
        paired_vs_fl = {}
        for m in all_methods:
            if m == 'fl_only':
                continue
            common = [pk for pk in physical_keys if pk in phys_apfdc[m] and pk in base_fl_apfdc]
            deltas = [phys_apfdc[m][pk] - base_fl_apfdc[pk] for pk in common]
            paired_vs_fl[m] = describe_deltas(deltas)

        # Paired TTFF deltas vs history_cost
        base_hc_ttff = phys_ttff['history_cost']
        paired_ttff_vs_hc = {}
        for m in all_methods:
            if m == 'history_cost':
                continue
            common = [pk for pk in physical_keys if pk in phys_ttff[m] and pk in base_hc_ttff]
            deltas = [phys_ttff[m][pk] - base_hc_ttff[pk] for pk in common]
            paired_ttff_vs_hc[m] = describe_deltas(deltas)

        # Paired Recall@10% deltas vs history_cost
        base_hc_rec10 = phys_recall10['history_cost']
        paired_rec10_vs_hc = {}
        for m in all_methods:
            if m == 'history_cost':
                continue
            common = [pk for pk in physical_keys if pk in phys_recall10[m] and pk in base_hc_rec10]
            deltas = [phys_recall10[m][pk] - base_hc_rec10[pk] for pk in common]
            paired_rec10_vs_hc[m] = describe_deltas(deltas)

        elapsed = time.perf_counter() - start_proj
        print(f"  {project.upper()} finished in {elapsed:.1f}s.")
        print(f"  hc_ugcs_v2 vs history_cost: median delta = {paired_vs_hc['hc_ugcs_v2']['median'] * 100:+.3f}% pts")
        print(f"  hc_ugcs_v2 vs fl_only:      median delta = {paired_vs_fl['hc_ugcs_v2']['median'] * 100:+.3f}% pts")

        project_reports[project] = {
            'physical_builds': len(physical_keys),
            'stages': scored_stages,
            'paired_vs_history_cost': paired_vs_hc,
            'paired_vs_fl_only': paired_vs_fl,
            'paired_ttff_vs_history_cost': paired_ttff_vs_hc,
            'paired_recall10_vs_history_cost': paired_rec10_vs_hc,
            'cumulative_predecessor_seconds': cumulative_predecessor_delay,
        }

    # Aggregate Engineering Metrics
    p95_overhead = percentile(stage_warm_overhead_ratios, 95)
    peak_rss = get_peak_rss_bytes()

    engineering_metrics = {
        'p95_warm_overhead_fraction': p95_overhead,
        'peak_rss_bytes': peak_rss,
        'median_latency_ugcs_seconds': statistics.median(warm_latencies_ugcs) if warm_latencies_ugcs else None,
        'median_latency_hc_seconds': statistics.median(warm_latencies_hc) if warm_latencies_hc else None,
        'scored_stages_total': sum(pr['stages'] for pr in project_reports.values()),
    }

    # Pure Decision Governance Evaluation
    decision_result = evaluate_decision(project_reports, config, engineering_metrics)

    final_report = {
        'version': 'stage12-development-screen-v1',
        'created_at': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        'parent_release': config.get('parent_release', 'v0.1.1'),
        'primary_method': config.get('primary_method', 'hc_ugcs_v2'),
        'reserved_opened': False,
        'preregistered_config_sha256': sha256_file(CONFIG_PATH),
        'implementation_sha256': sha256_file(ROOT / 'hc_falcon' / 'v2.py'),
        'evaluation_harness_sha256': sha256_file(Path(__file__).resolve()),
        'decision': decision_result,
        'engineering_metrics': engineering_metrics,
        'projects': project_reports,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUT_DIR / 'development-screen.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(final_report, f, indent=2)

    print("\n" + "=" * 80)
    print(f"EVALUATION COMPLETE. Decision: {decision_result['final_decision']} ({decision_result['decision_summary']})")
    print(f"Results written to: {out_file}")
    print("=" * 80)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Stage 12 Evaluation Harness: HC-FALCON v2 Screening")
    args = parser.parse_args()
    run_stage12_evaluation()
