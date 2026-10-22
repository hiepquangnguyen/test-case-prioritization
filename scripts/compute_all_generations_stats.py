"""Compute comprehensive statistical significance tests and effect sizes across all generations.

Evaluates on all 161 failing builds across Karaf (79), ActiveMQ (57), Log4j (25):
- Gen 1: hc_falcon_normalized_v1
- Gen 3a: hc_cns_v1 (Cost-Normalized Semantic Greedy)
- Gen 4: hc_ugcs_v2 (Uncertainty-Guarded Cost-aware Semantic Greedy)
- Baseline: fl_only (Semantic Facility Location only)
all paired vs history_cost.

Computes:
1. Paired Wilcoxon signed-rank test (two-sided, zero_method='pratt')
2. Cliff's delta effect size between paired distributions
3. Bootstrap 95% confidence intervals (10,000 resamples, seed=2026)
4. Win / Loss / Tie counts and win rate percentages
"""
from collections import defaultdict
import gzip
import json
from pathlib import Path
import statistics
import sys
import time

import numpy as np
from scipy import stats

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hc_falcon.v2 import rank_ugcs
from hc_falcon.variants import rank_cns
from scripts.pilot_support import conservative
from scripts.stage5_sources import selected
from tcp.domain import Outcome
from tcp.history import RollingHistory
from tcp.lrts import load_builds
from tcp.metrics import evaluate

PROJECTS = ['karaf', 'activemq', 'log4j']
STAGE6_DIR = ROOT / 'reports' / 'stage6'
VECTORS_DIR = ROOT / 'work' / 'cache' / 'stage6' / 'vectors'

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

def compute_cliffs_delta(x, y):
    n_x, n_y = len(x), len(y)
    if n_x == 0 or n_y == 0:
        return 0.0
    diffs = np.subtract.outer(x, y)
    more = np.sum(diffs > 1e-12)
    less = np.sum(diffs < -1e-12)
    return float((more - less) / (n_x * n_y))

def cliffs_delta_interpretation(d):
    ad = abs(d)
    if ad < 0.147:
        return "negligible"
    elif ad < 0.33:
        return "small"
    elif ad < 0.474:
        return "medium"
    else:
        return "large"

def bootstrap_ci(deltas, n_iter=10000, seed=2026, ci=0.95):
    rng = np.random.default_rng(seed)
    deltas = np.array(deltas, dtype=float)
    if len(deltas) == 0:
        return (0.0, 0.0)
    boot_means = [rng.choice(deltas, size=len(deltas), replace=True).mean() for _ in range(n_iter)]
    lower = float(np.percentile(boot_means, ((1.0 - ci) / 2.0) * 100.0))
    upper = float(np.percentile(boot_means, (1.0 - (1.0 - ci) / 2.0) * 100.0))
    return (lower, upper)

def run():
    print("=" * 80)
    print("COMPUTING STATISTICAL TESTS FOR ALL ALGORITHM GENERATIONS")
    print("=" * 80)
    
    vectors_cache = {}
    methods_to_evaluate = ['hc_falcon_normalized_v1', 'hc_cns_v1', 'hc_ugcs_v2', 'fl_only']
    all_methods = ['history_cost'] + methods_to_evaluate
    
    per_project_physical_scores = {}
    
    for project in PROJECTS:
        print(f"\nProcessing {project.upper()}...")
        old = STAGE6_DIR / project
        ledger = json.loads((old / 'ledger.json').read_text(encoding='utf-8'))
        
        builds, _ = load_builds(ROOT / 'references/artifacts/dante/ML_TCSP.zip', project, len(selected(project)))
        builds = tuple(map(conservative, builds))
        
        history = RollingHistory()
        stage_metrics = defaultdict(lambda: defaultdict(dict))
        
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
            
            # Read-only from Stage 6
            for m in ['history_cost', 'fl_only', 'hc_falcon_normalized_v1']:
                if m in existing_rankings:
                    stage_metrics[phys_key][m][stage_name] = existing_rankings[m]['metrics']
            
            # Vectors
            vectors, valid = [], []
            for src in saved['source']:
                ck = src['cache_key']
                if ck not in vectors_cache:
                    with np.load(VECTORS_DIR / f"{ck}.npz", allow_pickle=False) as c_vec:
                        vectors_cache[ck] = c_vec['vector'].copy()
                vectors.append(vectors_cache[ck])
                valid.append(src['valid'])
            
            k = compute_kernel(vectors, valid)
            
            # CNS v1
            cns_order = rank_cns(snapshot, ids, k, alpha=0.5)
            stage_metrics[phys_key]['hc_cns_v1'][stage_name] = evaluate(cns_order, domain_outcomes)
            
            # UGCS v2
            ugcs_order = rank_ugcs(snapshot, ids, k, semantic_weight=0.25, z_value=1.96)
            stage_metrics[phys_key]['hc_ugcs_v2'][stage_name] = evaluate(ugcs_order, domain_outcomes)
        
        physical_keys = sorted(stage_metrics.keys())
        print(f"  Failing physical builds: {len(physical_keys)}")
        
        # Physical build mean score for APFDc
        phys_scores = {m: {} for m in all_methods}
        for pk in physical_keys:
            for m in all_methods:
                st_dict = stage_metrics[pk].get(m, {})
                valid_vals = [s['apfdc_midpoint'] for s in st_dict.values() if s.get('apfdc_midpoint') is not None]
                if valid_vals:
                    phys_scores[m][pk] = statistics.mean(valid_vals)
        
        per_project_physical_scores[project] = phys_scores

    # Now compute statistical tests for each method vs history_cost
    results = {}
    for m in methods_to_evaluate:
        results[m] = {}
        print(f"\n==================== METHOD: {m} vs history_cost ====================")
        for proj in PROJECTS:
            scores = per_project_physical_scores[proj]
            pairs = []
            cand_vals = []
            base_vals = []
            
            for pk in scores['history_cost']:
                if pk in scores[m]:
                    vc = scores[m][pk]
                    vb = scores['history_cost'][pk]
                    pairs.append(vc - vb)
                    cand_vals.append(vc)
                    base_vals.append(vb)
            
            n = len(pairs)
            pairs_arr = np.array(pairs)
            wins = int(np.sum(pairs_arr > 1e-12))
            ties = int(np.sum(np.abs(pairs_arr) <= 1e-12))
            losses = int(np.sum(pairs_arr < -1e-12))
            win_rate = (wins / n) * 100 if n else 0.0
            
            med_delta = float(np.median(pairs_arr)) * 100
            mean_delta = float(np.mean(pairs_arr)) * 100
            
            # Wilcoxon
            try:
                w_stat, p_val = stats.wilcoxon(cand_vals, base_vals, zero_method='pratt', alternative='two-sided')
            except Exception as e:
                w_stat, p_val = np.nan, np.nan
            
            cd = compute_cliffs_delta(cand_vals, base_vals)
            cd_desc = cliffs_delta_interpretation(cd)
            
            ci_low, ci_high = bootstrap_ci(pairs_arr, n_iter=10000, seed=2026)
            ci_low_pct, ci_high_pct = ci_low * 100, ci_high * 100
            
            results[m][proj] = {
                'n': n,
                'wins': wins,
                'losses': losses,
                'ties': ties,
                'win_rate_pct': win_rate,
                'median_delta_pct': med_delta,
                'mean_delta_pct': mean_delta,
                'ci95_low_pct': ci_low_pct,
                'ci95_high_pct': ci_high_pct,
                'wilcoxon_stat': float(w_stat),
                'p_value': float(p_val),
                'cliffs_delta': cd,
                'cliffs_desc': cd_desc
            }
            
            print(f"[{proj.upper()}] N={n} | W/L/T: {wins}/{losses}/{ties} ({win_rate:.1f}%) | "
                  f"Med Δ: {med_delta:+.3f}% | Mean Δ: {mean_delta:+.3f}% [95% CI: {ci_low_pct:+.2f}%, {ci_high_pct:+.2f}%] | "
                  f"Wilcoxon p={p_val:.4e} | Cliff's delta={cd:+.3f} ({cd_desc})")
    
    out_file = ROOT / 'reports' / 'release' / 'statistical_tests_all_gens.json'
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(f"\nSaved all generations statistical tests to {out_file}")

if __name__ == '__main__':
    run()
