"""Compute comprehensive statistical significance tests and effect sizes for paper.

Performs:
1. Paired Wilcoxon signed-rank test (two-sided, zero_method='pratt')
2. Cliff's delta effect size between paired distributions
3. Bootstrap 95% confidence intervals (10,000 resamples, seed=2026)
4. Win / Loss / Tie counts and win rate percentages
5. Generates publication-ready markdown tables for LaTeX / Paper draft.
"""
from collections import defaultdict
import gzip
import json
from pathlib import Path
from statistics import mean, median
import sys

import numpy as np
from scipy import stats

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent

def compute_cliffs_delta(x, y):
    """Compute Cliff's delta between two independent or paired sets of scores."""
    n_x, n_y = len(x), len(y)
    if n_x == 0 or n_y == 0:
        return 0.0
    # d = #(x_i > y_j) - #(x_i < y_j) / (n_x * n_y)
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
    """Compute non-parametric bootstrap confidence interval for mean delta."""
    rng = np.random.default_rng(seed)
    deltas = np.array(deltas, dtype=float)
    if len(deltas) == 0:
        return (0.0, 0.0)
    boot_means = [rng.choice(deltas, size=len(deltas), replace=True).mean() for _ in range(n_iter)]
    lower = float(np.percentile(boot_means, ((1.0 - ci) / 2.0) * 100.0))
    upper = float(np.percentile(boot_means, (1.0 - (1.0 - ci) / 2.0) * 100.0))
    return (lower, upper)

def get_stage6_data():
    """Extract per-physical-build scores from Stage 6 for all evaluated methods."""
    results = {}
    for project in ['karaf', 'activemq', 'log4j']:
        directory = ROOT / 'reports' / 'stage6' / project
        ledger = json.loads((directory / 'ledger.json').read_text(encoding='utf-8'))
        stages = {}
        for row in ledger:
            if row['split'] != 'development' or not row['usable'] or not row.get('checkpoint'):
                continue
            with gzip.open(directory / 'builds' / row['checkpoint'], 'rt', encoding='utf-8') as f:
                b = json.load(f)
            key = tuple(b['key'][k] for k in ('project', 'pr', 'build', 'stage'))
            methods = defaultdict(list)
            for r in b['rankings']:
                m = r['metrics']
                if m['apfdc_midpoint'] is not None:
                    methods[r['method']].append(m['apfdc_midpoint'])
            if methods:
                stages[key] = {name: mean(vals) for name, vals in methods.items()}
        
        # Aggregate to physical builds (project, pr, build)
        phys_methods = defaultdict(lambda: defaultdict(list))
        for key, meths in stages.items():
            phys_key = key[:3]
            for m_name, val in meths.items():
                phys_methods[phys_key][m_name].append(val)
        
        # mean across stages within physical build
        phys_scores = defaultdict(dict)
        for phys_key, meths in phys_methods.items():
            for m_name, vals in meths.items():
                phys_scores[phys_key][m_name] = mean(vals)
        
        results[project] = phys_scores
    return results

def main():
    print("=" * 80)
    print("COMPUTING STATISTICAL TESTS FOR ICST/PAPER DRAFT")
    print("=" * 80)
    
    stage6_scores = get_stage6_data()
    
    # Comparisons of interest
    comparisons = [
        ("hc_falcon_normalized_v1", "history_cost", "HC-FALCON v1 vs History+Cost"),
        ("hc_falcon_normalized_v1", "fl_only", "HC-FALCON v1 vs FL-only (Semantic)"),
        ("history_cost", "fl_only", "History+Cost vs FL-only"),
    ]
    
    stat_summary = {}
    
    for m_cand, m_base, label in comparisons:
        print(f"\n>>> {label} <<<")
        stat_summary[label] = {}
        for proj in ['karaf', 'activemq', 'log4j']:
            scores = stage6_scores[proj]
            pairs = []
            x_vals = []
            y_vals = []
            for pk, m_dict in scores.items():
                if m_cand in m_dict and m_base in m_dict:
                    val_c = m_dict[m_cand]
                    val_b = m_dict[m_base]
                    delta = val_c - val_b
                    pairs.append(delta)
                    x_vals.append(val_c)
                    y_vals.append(val_b)
            
            n = len(pairs)
            if n == 0:
                continue
            
            pairs_arr = np.array(pairs)
            wins = int(np.sum(pairs_arr > 1e-12))
            ties = int(np.sum(np.abs(pairs_arr) <= 1e-12))
            losses = int(np.sum(pairs_arr < -1e-12))
            win_rate = (wins / n) * 100
            
            med_delta = float(np.median(pairs_arr)) * 100  # in percentage points
            mean_delta = float(np.mean(pairs_arr)) * 100
            
            # Wilcoxon signed-rank test
            # Note: zero_method='pratt' or 'wilcox'
            try:
                # Scipy wilcoxon
                w_stat, p_val = stats.wilcoxon(x_vals, y_vals, zero_method='pratt', alternative='two-sided')
            except Exception as e:
                w_stat, p_val = np.nan, np.nan
            
            # Cliff's delta
            cd = compute_cliffs_delta(x_vals, y_vals)
            cd_desc = cliffs_delta_interpretation(cd)
            
            # Bootstrap 95% CI for mean delta
            ci_low, ci_high = bootstrap_ci(pairs_arr, n_iter=10000, seed=2026)
            ci_low_pct, ci_high_pct = ci_low * 100, ci_high * 100
            
            stat_summary[label][proj] = {
                'n_builds': n,
                'wins': wins,
                'losses': losses,
                'ties': ties,
                'win_rate_pct': win_rate,
                'mean_delta_pct': mean_delta,
                'median_delta_pct': med_delta,
                'wilcoxon_stat': float(w_stat),
                'p_value': float(p_val),
                'cliffs_delta': cd,
                'cliffs_desc': cd_desc,
                'ci95_low_pct': ci_low_pct,
                'ci95_high_pct': ci_high_pct
            }
            
            print(f"[{proj.upper()}] N={n} | Win/Loss/Tie: {wins}/{losses}/{ties} ({win_rate:.1f}%) | "
                  f"Median Delta: {med_delta:+.2f}% | Mean Delta: {mean_delta:+.2f}% [95% CI: {ci_low_pct:+.2f}%, {ci_high_pct:+.2f}%] | "
                  f"Wilcoxon p={p_val:.4e} | Cliff's delta={cd:+.3f} ({cd_desc})")
    
    # Save results to reports/release
    out_file = ROOT / 'reports' / 'release' / 'statistical_tests.json'
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(stat_summary, indent=2), encoding='utf-8')
    print(f"\nSaved statistical summary to {out_file}")

if __name__ == '__main__':
    main()
