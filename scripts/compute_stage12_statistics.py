"""Compute comprehensive statistical significance tests and effect sizes for Stage 12 (UGCS v2).

Compares Stage 12 (hc_ugcs_v2) vs history_cost on the development screening split
across Karaf (79), ActiveMQ (57), and Log4j2 (25) failing physical builds.

Computes:
1. Sample size n, Win / Loss / Tie counts, and Win rate (%)
2. Median and Mean paired Delta APFDc (%)
3. Non-parametric Bootstrap 95% Confidence Interval (10,000 resamples, seed=2026)
4. Two-sided Paired Wilcoxon Signed-Rank Test (zero_method='pratt')
5. Cliff's Delta effect size and verbal interpretation
6. Holm-Bonferroni adjusted p-values across the 3 projects
Outputs results to reports/stage12/stage12_statistical_tests.json.
"""
from collections import defaultdict
import gzip
import json
from pathlib import Path
import statistics
import sys

import numpy as np
from scipy import stats

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
STAGE12_ALL_GENS_PATH = ROOT / 'reports' / 'release' / 'statistical_tests_all_gens.json'
OUT_PATH = ROOT / 'reports' / 'stage12' / 'stage12_statistical_tests.json'


def holm_bonferroni_correction(p_values: dict[str, float]) -> dict[str, float]:
    """Compute step-down Holm-Bonferroni adjusted p-values.

    For m hypotheses sorted p_(1) <= p_(2) <= ... <= p_(m):
    adj_p_(k) = min(1.0, max(adj_p_(k-1), (m - k + 1) * p_(k)))
    """
    sorted_keys = sorted(p_values.keys(), key=lambda k: p_values[k])
    m = len(sorted_keys)
    adjusted = {}
    prev_adj = 0.0
    for rank, key in enumerate(sorted_keys):
        raw_p = p_values[key]
        multiplier = m - rank
        adj_p = min(1.0, max(prev_adj, multiplier * raw_p))
        adjusted[key] = adj_p
        prev_adj = adj_p
    return adjusted


def main():
    print("=" * 80)
    print("COMPUTING STAGE 12 (UGCS v2) STATISTICAL TESTS AND HOLM CORRECTION")
    print("=" * 80)

    if not STAGE12_ALL_GENS_PATH.exists():
        print(f"Error: {STAGE12_ALL_GENS_PATH} not found. Running generator...")
        import scripts.compute_all_generations_stats as gen_script
        gen_script.run()

    data = json.loads(STAGE12_ALL_GENS_PATH.read_text(encoding='utf-8'))
    ugcs_data = data['hc_ugcs_v2']

    # Extract raw p-values for Holm correction
    raw_p_values = {proj: ugcs_data[proj]['p_value'] for proj in ['karaf', 'activemq', 'log4j']}
    holm_p_values = holm_bonferroni_correction(raw_p_values)

    output = {
        "metadata": {
            "comparison": "Stage 12 (hc_ugcs_v2) vs baseline (history_cost)",
            "split": "development_screening",
            "seed": 2026,
            "bootstrap_iterations": 10000,
            "correction_method": "Holm-Bonferroni (family of 3 projects)"
        },
        "projects": {}
    }

    for proj in ['karaf', 'activemq', 'log4j']:
        item = dict(ugcs_data[proj])
        item['p_value_raw'] = item['p_value']
        item['p_value_holm'] = holm_p_values[proj]
        output['projects'][proj] = item

        print(f"\n[{proj.upper()}] (N = {item['n']})")
        print(f"  Win / Loss / Tie : {item['wins']} / {item['losses']} / {item['ties']} ({item['win_rate_pct']:.2f}%)")
        print(f"  Median Delta APFDc: {item['median_delta_pct']:+.4f}%")
        print(f"  Mean Delta APFDc  : {item['mean_delta_pct']:+.4f}% [95% CI: {item['ci95_low_pct']:+.4f}%, {item['ci95_high_pct']:+.4f}%]")
        print(f"  Wilcoxon W-stat   : {item['wilcoxon_stat']:.1f}")
        print(f"  p-value (raw)     : {item['p_value_raw']:.6e}")
        print(f"  p-value (Holm adj): {item['p_value_holm']:.6e}")
        print(f"  Cliff's delta     : {item['cliffs_delta']:+.4f} ({item['cliffs_desc']})")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output, indent=2), encoding='utf-8')
    print(f"\nSuccessfully wrote Stage 12 statistical tests to: {OUT_PATH}")


if __name__ == '__main__':
    main()
