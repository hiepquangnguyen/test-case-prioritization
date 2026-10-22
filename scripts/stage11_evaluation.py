"""Comprehensive Phase 3 experimental evaluation of improvement variants on LRTS development.

Replays all development builds across Karaf, ActiveMQ, Log4j using exact Stage 6
historical snapshots and cached vector embeddings.

Evaluates:
- history_cost (Baseline)
- fl_only (Baseline)
- hc_falcon_normalized_v1 (Stage 6 Primary)
- hc_cns_v1 (Candidate A1: Cost-Normalized Semantic Greedy)
- hc_knapsack_v1 (Candidate A2: Knapsack Submodular Greedy)
- hc_tiered_v1 (Candidate B: Tiered History-Semantic Optimization)

Checks Effect Gate:
- median paired delta APFDc >= +0.0300 (+3.0% pts) vs BOTH history_cost and fl_only
- on at least 2 of 3 development projects.

Outputs:
- reports/stage11/simulation-results.json
"""
from collections import defaultdict
import gzip
import json
from pathlib import Path
import statistics
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hc_falcon.variants import rank_cns, rank_knapsack, rank_tiered
from scripts.pilot_support import conservative
from scripts.stage5_sources import selected
from tcp.domain import Outcome
from tcp.history import RollingHistory
from tcp.lrts import load_builds
from tcp.metrics import evaluate

PROJECTS = ['karaf', 'activemq', 'log4j']
STAGE6 = ROOT / 'reports' / 'stage6'
STAGE7 = ROOT / 'reports' / 'stage7'
VECTORS_DIR = ROOT / 'work' / 'cache' / 'stage6' / 'vectors'
OUT_DIR = ROOT / 'reports' / 'stage11'
OUT_DIR.mkdir(parents=True, exist_ok=True)


def compute_kernel(vectors, valid):
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
    if not data:
        return None
    s = sorted(data)
    k = (len(s) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (k - f) * (s[c] - s[f])


def describe_deltas(values):
    if not values:
        return {'count': 0, 'mean': None, 'median': None, 'pos': 0, 'neg': 0, 'tie': 0}
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


def run_evaluation():
    print("=" * 70)
    print("HC-FALCON Phase 3: Controlled Experimental Evaluation on Development")
    print("=" * 70)

    vectors_cache = {}
    project_reports = {}

    candidates = {
        'hc_cns_v1': lambda sn, ids, k: rank_cns(sn, ids, k, alpha=0.5),
        'hc_knapsack_v1': lambda sn, ids, k: rank_knapsack(sn, ids, k, alpha=0.5, gamma=0.5),
        'hc_tiered_v1': lambda sn, ids, k: rank_tiered(sn, ids, k),
    }

    all_methods = ['history_cost', 'fl_only', 'hc_falcon_normalized_v1'] + list(candidates.keys())

    for project in PROJECTS:
        print(f"\n>>> Project: {project.upper()} <<<")
        start_proj = time.perf_counter()
        old = STAGE6 / project
        ledger = json.loads((old / 'ledger.json').read_text(encoding='utf-8'))

        builds, _ = load_builds(ROOT / 'references/artifacts/dante/ML_TCSP.zip', project, len(selected(project)))
        builds = tuple(map(conservative, builds))

        history = RollingHistory()

        stage_metrics = defaultdict(lambda: defaultdict(dict))
        scored_stages = 0

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

            # Existing rankings
            existing_rankings = {r['method']: r for r in saved['rankings'] if r.get('seed') == 0 or 'seed' not in r}

            phys_key = f"{row['key']['project']}/{row['key']['pr']}/{row['key']['build']}"
            stage_name = row['key']['stage']

            # Evaluate existing methods
            for m in ['history_cost', 'fl_only', 'hc_falcon_normalized_v1']:
                if m in existing_rankings:
                    stage_metrics[phys_key][m][stage_name] = existing_rankings[m]['metrics']

            # Load vectors
            vectors, valid = [], []
            for src in saved['source']:
                ck = src['cache_key']
                if ck not in vectors_cache:
                    with np.load(VECTORS_DIR / f"{ck}.npz", allow_pickle=False) as c_vec:
                        vectors_cache[ck] = c_vec['vector'].copy()
                vectors.append(vectors_cache[ck])
                valid.append(src['valid'])

            k = compute_kernel(vectors, valid)

            # Evaluate candidate methods
            for c_name, c_fn in candidates.items():
                order = c_fn(snapshot, ids, k)
                ev = evaluate(order, domain_outcomes)
                stage_metrics[phys_key][c_name][stage_name] = ev

            scored_stages += 1
            if scored_stages % 25 == 0:
                print(f"  Processed {scored_stages} failing stages...")

        # Physical build aggregation
        physical_keys = sorted(stage_metrics.keys())
        print(f"  Failing physical builds: {len(physical_keys)} (stages: {scored_stages})")

        # For each method, compute physical build mean score
        phys_scores = {m: {} for m in all_methods}
        for pk in physical_keys:
            for m in all_methods:
                st_dict = stage_metrics[pk].get(m, {})
                valid_vals = [s['apfdc_midpoint'] for s in st_dict.values() if s.get('apfdc_midpoint') is not None]
                if valid_vals:
                    phys_scores[m][pk] = statistics.mean(valid_vals)

        # Paired deltas vs history_cost
        base_scores = phys_scores['history_cost']
        paired_deltas_vs_hc = {}
        for m in all_methods:
            if m == 'history_cost':
                continue
            common = [pk for pk in physical_keys if pk in phys_scores[m] and pk in base_scores]
            deltas = [phys_scores[m][pk] - base_scores[pk] for pk in common]
            paired_deltas_vs_hc[m] = describe_deltas(deltas)

        # Paired deltas vs fl_only
        fl_scores = phys_scores['fl_only']
        paired_deltas_vs_fl = {}
        for m in all_methods:
            if m == 'fl_only':
                continue
            common = [pk for pk in physical_keys if pk in phys_scores[m] and pk in fl_scores]
            deltas = [phys_scores[m][pk] - fl_scores[pk] for pk in common]
            paired_deltas_vs_fl[m] = describe_deltas(deltas)

        elapsed = time.perf_counter() - start_proj
        print(f"  Completed {project} in {elapsed:.1f}s")
        print("\n  Summary vs History+cost (Median Paired Delta APFDc):")
        for m, stats in paired_deltas_vs_hc.items():
            med_pct = stats['median'] * 100 if stats['median'] is not None else 0.0
            mean_pct = stats['mean'] * 100 if stats['mean'] is not None else 0.0
            print(f"    {m:25s}: median={med_pct:+.3f}% pts | mean={mean_pct:+.3f}% pts | W/T/L = {stats['pos']}/{stats['tie']}/{stats['neg']}")

        project_reports[project] = {
            'physical_builds': len(physical_keys),
            'stages': scored_stages,
            'paired_vs_history_cost': paired_deltas_vs_hc,
            'paired_vs_fl_only': paired_deltas_vs_fl,
        }

    # Cross-project gate evaluation
    print("\n" + "=" * 80)
    print("EFFECT GATE EVALUATION (Median Paired Delta APFDc vs History+cost)")
    print("Threshold: >= +0.0300 (+3.0% pts) on >= 2 of 3 projects")
    print("=" * 80)
    print(f"{'Method':25s} | {'Karaf':>10s} | {'ActiveMQ':>10s} | {'Log4j':>10s} | {'Gate Decision':>20s}")
    print("-" * 80)

    gate_summary = {}
    eval_methods = ['hc_falcon_normalized_v1', 'hc_cns_v1', 'hc_knapsack_v1', 'hc_tiered_v1']

    for m in eval_methods:
        row = []
        pass_count = 0
        for p in PROJECTS:
            med = project_reports[p]['paired_vs_history_cost'][m]['median']
            med_pct = med * 100 if med is not None else 0.0
            row.append(f"{med_pct:+.3f}%")
            if med is not None and med >= 0.03:
                pass_count += 1

        decision = f"PASS ({pass_count}/3)" if pass_count >= 2 else f"NO-GO ({pass_count}/3)"
        gate_summary[m] = {
            'passing_projects': pass_count,
            'decision': decision,
        }
        print(f"{m:25s} | {row[0]:>10s} | {row[1]:>10s} | {row[2]:>10s} | {decision:>20s}")

    final_report = {
        'timestamp': time.time(),
        'projects': project_reports,
        'gate_summary': gate_summary,
    }

    out_file = OUT_DIR / 'simulation-results.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(final_report, f, indent=2)
    print(f"\nFull evaluation report saved to: {out_file}")


if __name__ == '__main__':
    run_evaluation()
