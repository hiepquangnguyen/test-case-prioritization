"""Compute paired effect sizes (Rank-biserial and Paired Cliff's Delta) for Stage 12 and Stage 6 v1.

Address the user inquiry:
1. Explain why unpaired Cliff's delta was ~ -0.002 (unpaired comparison across all n*n cross-build combinations).
2. Compute paired effect sizes:
   - Matched-pairs rank-biserial correlation (Wilcoxon r_rb)
   - Paired Cliff's delta on build-level differences (d_i = x_i - y_i vs 0, equivalent to (Wins - Losses) / n)
3. Outputs to new JSON files without overwriting existing files:
   - reports/stage12/stage12_statistical_tests_paired_effect_sizes.json
   - reports/release/statistical_tests_v1_paired_effect_sizes.json
"""
import gzip
import json
from pathlib import Path
import statistics
import sys

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hc_falcon.v2 import rank_ugcs
from scripts.pilot_support import conservative
from scripts.stage5_sources import selected
from tcp.domain import Outcome
from tcp.history import RollingHistory
from tcp.lrts import load_builds
from tcp.metrics import evaluate

PROJECTS = ['karaf', 'activemq', 'log4j']
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


def analyze_paired_differences(cand_vals, base_vals):
    cand = np.asarray(cand_vals, dtype=np.float64)
    base = np.asarray(base_vals, dtype=np.float64)
    diffs = cand - base
    n = len(diffs)

    wins = int(np.sum(diffs > 1e-12))
    losses = int(np.sum(diffs < -1e-12))
    ties = int(np.sum(np.abs(diffs) <= 1e-12))
    win_rate_pct = (wins / n) * 100.0 if n > 0 else 0.0

    # 1. Paired Cliff's delta on differences vs 0: (Wins - Losses) / n
    cliffs_delta_paired = float((wins - losses) / n) if n > 0 else 0.0

    # 2. Unpaired Cliff's delta across all n*n pairs (for comparison and explanation)
    diffs_outer = np.subtract.outer(cand, base)
    more = np.sum(diffs_outer > 1e-12)
    less = np.sum(diffs_outer < -1e-12)
    cliffs_delta_unpaired = float((more - less) / (n * n)) if n > 0 else 0.0

    # 3. Wilcoxon signed-rank test and Rank-biserial correlation
    # Non-zero differences (standard Wilcoxon)
    non_zero = diffs[np.abs(diffs) > 1e-12]
    if len(non_zero) > 0:
        ranks = stats.rankdata(np.abs(non_zero))
        w_plus = float(np.sum(ranks[non_zero > 0]))
        w_minus = float(np.sum(ranks[non_zero < 0]))
        total_w = w_plus + w_minus
        rank_biserial_wilcoxon = float((w_plus - w_minus) / total_w) if total_w > 0 else 0.0
    else:
        w_plus, w_minus, total_w = 0.0, 0.0, 0.0
        rank_biserial_wilcoxon = 0.0

    # Pratt rank-biserial (including zero differences)
    ranks_pratt = stats.rankdata(np.abs(diffs))
    w_plus_pratt = float(np.sum(ranks_pratt[diffs > 1e-12]))
    w_minus_pratt = float(np.sum(ranks_pratt[diffs < -1e-12]))
    total_w_pratt = float(np.sum(ranks_pratt))
    rank_biserial_pratt = float((w_plus_pratt - w_minus_pratt) / total_w_pratt) if total_w_pratt > 0 else 0.0

    # Scipy wilcoxon stat and p-value
    try:
        w_res = stats.wilcoxon(cand, base, zero_method='pratt', alternative='two-sided')
        wilcoxon_stat = float(w_res.statistic)
        p_val_raw = float(w_res.pvalue)
    except Exception:
        wilcoxon_stat, p_val_raw = float('nan'), float('nan')

    return {
        'n': n,
        'wins': wins,
        'losses': losses,
        'ties': ties,
        'win_rate_pct': win_rate_pct,
        'median_delta_pct': float(np.median(diffs)) * 100.0,
        'mean_delta_pct': float(np.mean(diffs)) * 100.0,
        'wilcoxon_stat': wilcoxon_stat,
        'p_value_raw': p_val_raw,
        'effect_sizes': {
            'paired_cliffs_delta': cliffs_delta_paired,
            'paired_cliffs_delta_formula': '(wins - losses) / n',
            'rank_biserial_wilcoxon': rank_biserial_wilcoxon,
            'rank_biserial_wilcoxon_formula': '(W_plus - W_minus) / (W_plus + W_minus) [zeros excluded]',
            'rank_biserial_pratt': rank_biserial_pratt,
            'rank_biserial_pratt_formula': '(W_plus - W_minus) / total_ranks [zeros included in ranking]',
            'unpaired_cliffs_delta_diagnostic': cliffs_delta_unpaired,
            'unpaired_cliffs_delta_explanation': (
                'Calculated across all n*n unpaired combinations cand[i] vs base[j]. '
                'Dominated by cross-build score variance rather than within-build delta.'
            )
        },
        'rank_sums': {
            'w_plus': w_plus,
            'w_minus': w_minus,
            'w_plus_pratt': w_plus_pratt,
            'w_minus_pratt': w_minus_pratt
        }
    }


def holm_bonferroni(p_dict):
    sorted_items = sorted(p_dict.items(), key=lambda kv: kv[1])
    m = len(sorted_items)
    adjusted = {}
    prev = 0.0
    for rank, (k, p) in enumerate(sorted_items):
        adj = min(1.0, max(prev, (m - rank) * p))
        adjusted[k] = adj
        prev = adj
    return adjusted


def main():
    print("=" * 80)
    print("COMPUTING PAIRED EFFECT SIZES (RANK-BISERIAL & PAIRED CLIFF'S DELTA)")
    print("=" * 80)

    vectors_cache = {}
    v1_scores = {p: {'cand': [], 'base': []} for p in PROJECTS}
    ugcs_scores = {p: {'cand': [], 'base': []} for p in PROJECTS}

    for project in PROJECTS:
        old = ROOT / 'reports' / 'stage6' / project
        with open(old / 'ledger.json', encoding='utf-8') as f:
            ledger = json.load(f)

        builds, _ = load_builds(ROOT / 'references/artifacts/dante/ML_TCSP.zip', project, len(selected(project)))
        builds = tuple(map(conservative, builds))
        history = RollingHistory()

        stage_metrics = {}

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

            phys_key = f"{row['key']['project']}/{row['key']['pr']}/{row['key']['build']}"
            stage_name = row['key']['stage']

            if phys_key not in stage_metrics:
                stage_metrics[phys_key] = {'history_cost': {}, 'hc_falcon_normalized_v1': {}, 'hc_ugcs_v2': {}}

            existing_rankings = {r['method']: r for r in saved['rankings'] if r.get('seed') == 0 or 'seed' not in r}
            stage_metrics[phys_key]['history_cost'][stage_name] = existing_rankings['history_cost']['metrics']['apfdc_midpoint']
            stage_metrics[phys_key]['hc_falcon_normalized_v1'][stage_name] = existing_rankings['hc_falcon_normalized_v1']['metrics']['apfdc_midpoint']

            # Compute vectors and UGCS v2
            vectors, valid = [], []
            for src in saved['source']:
                ck = src['cache_key']
                if ck not in vectors_cache:
                    with np.load(VECTORS_DIR / f"{ck}.npz", allow_pickle=False) as c_vec:
                        vectors_cache[ck] = c_vec['vector'].copy()
                vectors.append(vectors_cache[ck])
                valid.append(src['valid'])

            k = compute_kernel(vectors, valid)
            ids = tuple(saved['inventory'])
            domain_outcomes = tuple(Outcome(o['test_id'], o['failed'], o['duration']) for o in saved['outcomes'])

            ugcs_order = rank_ugcs(snapshot, ids, k, semantic_weight=0.25, z_value=1.96)
            ugcs_ev = evaluate(ugcs_order, domain_outcomes)
            stage_metrics[phys_key]['hc_ugcs_v2'][stage_name] = ugcs_ev['apfdc_midpoint']

        # Physical build mean
        phys_keys = sorted(stage_metrics.keys())
        for pk in phys_keys:
            m_hc = statistics.mean(stage_metrics[pk]['history_cost'].values())
            m_v1 = statistics.mean(stage_metrics[pk]['hc_falcon_normalized_v1'].values())
            m_ugcs = statistics.mean(stage_metrics[pk]['hc_ugcs_v2'].values())

            v1_scores[project]['cand'].append(m_v1)
            v1_scores[project]['base'].append(m_hc)

            ugcs_scores[project]['cand'].append(m_ugcs)
            ugcs_scores[project]['base'].append(m_hc)

        print(f"[{project.upper()}] Processed {len(phys_keys)} failing physical builds.")

    # 1. Compute for Stage 12 (UGCS v2)
    stage12_output = {
        'metadata': {
            'method': 'hc_ugcs_v2',
            'baseline': 'history_cost',
            'split': 'development_screening',
            'purpose': 'Paired effect size correction (Rank-biserial & Paired Cliff Delta)'
        },
        'projects': {}
    }
    raw_p_ugcs = {}
    for p in PROJECTS:
        res = analyze_paired_differences(ugcs_scores[p]['cand'], ugcs_scores[p]['base'])
        raw_p_ugcs[p] = res['p_value_raw']
        stage12_output['projects'][p] = res

    holm_ugcs = holm_bonferroni(raw_p_ugcs)
    for p in PROJECTS:
        stage12_output['projects'][p]['p_value_holm'] = holm_ugcs[p]

    out_s12 = ROOT / 'reports' / 'stage12' / 'stage12_statistical_tests_paired_effect_sizes.json'
    out_s12.write_text(json.dumps(stage12_output, indent=2), encoding='utf-8')
    print(f"\nWrote Stage 12 paired effect sizes to: {out_s12}")

    # 2. Compute for Stage 6 v1 (HC-FALCON v1 normalized)
    v1_output = {
        'metadata': {
            'method': 'hc_falcon_normalized_v1',
            'baseline': 'history_cost',
            'split': 'development_screening',
            'purpose': 'Paired effect size correction (Rank-biserial & Paired Cliff Delta)'
        },
        'projects': {}
    }
    raw_p_v1 = {}
    for p in PROJECTS:
        res = analyze_paired_differences(v1_scores[p]['cand'], v1_scores[p]['base'])
        raw_p_v1[p] = res['p_value_raw']
        v1_output['projects'][p] = res

    holm_v1 = holm_bonferroni(raw_p_v1)
    for p in PROJECTS:
        v1_output['projects'][p]['p_value_holm'] = holm_v1[p]

    out_v1 = ROOT / 'reports' / 'release' / 'statistical_tests_v1_paired_effect_sizes.json'
    out_v1.write_text(json.dumps(v1_output, indent=2), encoding='utf-8')
    print(f"Wrote Stage 6 v1 paired effect sizes to: {out_v1}")


if __name__ == '__main__':
    main()
