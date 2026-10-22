"""Compute winning build intersections across generations and UGCS v2 absolute APFDc.

Answers:
1. Of the 38 builds where HC-FALCON v1 beat history_cost:
   - How many still win in Stage 8 (Restricted Semantic)?
   - How many still win in Stage 11 (CNS-Greedy)?
   - How many still win in Stage 12 (UGCS v2)?
   - Are Stage 11's 38 wins identical to v1's 38 wins?
2. Absolute APFDc of UGCS v2:
   - Computed as APFDc(history_cost) + delta per physical build
   - Mean, Median per project, and cross-project summary.

Outputs:
- reports/stage12/winning_builds_intersection.json
- reports/stage12/ugcs_v2_absolute_apfdc.json
"""
from collections import defaultdict
import gzip
import json
import math
from pathlib import Path
import statistics
import sys
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import scripts.stage12_evaluate as s12

PROJECTS = ['karaf', 'activemq', 'log4j']
STAGE6_DIR = ROOT / 'reports/stage6'
STAGE8_DIR = ROOT / 'reports/stage8'
VECTORS_DIR = ROOT / 'work/cache/stage6/vectors'

def compute_fast_kernel(vectors, valid):
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
    k[np.ix_(idx, idx)] = sub_k
    np.fill_diagonal(k, np.where(val, 1.0, 0.0).astype(np.float64))
    return k

def main():
    cfg = json.loads((ROOT / 'configs/hc-falcon-v2-preregistered.json').read_text(encoding='utf-8'))
    sem_weight = cfg['fixed_constants']['semantic_weight']
    z_val = cfg['fixed_constants']['z_value']

    vectors_cache = {}

    # 1. Load Stage 8 physical deltas
    s8_phys_deltas = {}
    for p in PROJECTS:
        s8_build_deltas = defaultdict(list)
        for cp_path in (STAGE8_DIR / p / 'builds').glob('*.json.gz'):
            with gzip.open(cp_path, 'rt', encoding='utf-8') as f:
                saved = json.load(f)
            c_val = saved['metrics']['apfdc_midpoint']
            h_val = saved['comparators']['history_cost']['apfdc_midpoint']
            if c_val is not None and h_val is not None:
                pk = f"{saved['key']['project']}/{saved['key']['pr']}/{saved['key']['build']}"
                s8_build_deltas[pk].append(c_val - h_val)
        s8_phys_deltas[p] = {pk: statistics.mean(vals) for pk, vals in s8_build_deltas.items()}

    # 2. Replay Stage 6 / 11 / 12
    per_project_phys_scores = {}

    for project in PROJECTS:
        print(f"Replaying {project}...")
        old = STAGE6_DIR / project
        ledger = json.loads((old / 'ledger.json').read_text(encoding='utf-8'))
        builds, _ = s12.load_builds(ROOT / 'references/artifacts/dante/ML_TCSP.zip', project, len(s12.selected(project)))
        builds = tuple(map(s12.conservative, builds))
        history = s12.RollingHistory()

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

            phys_key = f"{row['key']['project']}/{row['key']['pr']}/{row['key']['build']}"
            stage_name = row['key']['stage']

            ids = tuple(saved['inventory'])
            domain_outcomes = tuple(s12.Outcome(o['test_id'], o['failed'], o['duration']) for o in saved['outcomes'])
            existing = {r['method']: r for r in saved['rankings'] if r.get('seed') == 0 or 'seed' not in r}

            stage_metrics[phys_key]['history_cost'][stage_name] = existing['history_cost']['metrics']['apfdc_midpoint']
            stage_metrics[phys_key]['hc_falcon_normalized_v1'][stage_name] = existing['hc_falcon_normalized_v1']['metrics']['apfdc_midpoint']

            vectors, valid = [], []
            for src in saved['source']:
                ck = src['cache_key']
                if ck not in vectors_cache:
                    with np.load(VECTORS_DIR / f'{ck}.npz', allow_pickle=False) as c_vec:
                        vectors_cache[ck] = c_vec['vector'].copy()
                vectors.append(vectors_cache[ck])
                valid.append(src['valid'])
            k = compute_fast_kernel(vectors, valid)

            cns_order = s12.rank_cns(snapshot, ids, k, alpha=0.5)
            stage_metrics[phys_key]['hc_cns_v1'][stage_name] = s12.evaluate(cns_order, domain_outcomes)['apfdc_midpoint']

            ugcs_order = s12.rank_ugcs(snapshot, ids, k, semantic_weight=sem_weight, z_value=z_val)
            stage_metrics[phys_key]['hc_ugcs_v2'][stage_name] = s12.evaluate(ugcs_order, domain_outcomes)['apfdc_midpoint']

        # Average over stages to get physical build scores
        phys_scores = defaultdict(dict)
        for pk, methods in stage_metrics.items():
            for m, st_dict in methods.items():
                vals = [v for v in st_dict.values() if v is not None]
                if vals:
                    phys_scores[m][pk] = statistics.mean(vals)
        per_project_phys_scores[project] = phys_scores

    # 3. Analyze Wins / Losses / Ties and intersections
    win_sets = {
        'v1': set(),
        'stage8': set(),
        'stage11_cns': set(),
        'stage12_ugcs': set()
    }
    loss_sets = {
        'v1': set(),
        'stage8': set(),
        'stage11_cns': set(),
        'stage12_ugcs': set()
    }

    per_build_deltas = defaultdict(dict)

    for project in PROJECTS:
        scores = per_project_phys_scores[project]
        hc_scores = scores['history_cost']

        for pk, hc_val in hc_scores.items():
            # v1
            v1_val = scores['hc_falcon_normalized_v1'][pk]
            d_v1 = v1_val - hc_val
            per_build_deltas[pk]['v1'] = d_v1
            if d_v1 > 1e-12: win_sets['v1'].add(pk)
            elif d_v1 < -1e-12: loss_sets['v1'].add(pk)

            # stage 8
            d_s8 = s8_phys_deltas[project].get(pk, 0.0)
            per_build_deltas[pk]['stage8'] = d_s8
            if d_s8 > 1e-12: win_sets['stage8'].add(pk)
            elif d_s8 < -1e-12: loss_sets['stage8'].add(pk)

            # stage 11
            cns_val = scores['hc_cns_v1'][pk]
            d_cns = cns_val - hc_val
            per_build_deltas[pk]['stage11_cns'] = d_cns
            if d_cns > 1e-12: win_sets['stage11_cns'].add(pk)
            elif d_cns < -1e-12: loss_sets['stage11_cns'].add(pk)

            # stage 12
            ugcs_val = scores['hc_ugcs_v2'][pk]
            d_ugcs = ugcs_val - hc_val
            per_build_deltas[pk]['stage12_ugcs'] = d_ugcs
            if d_ugcs > 1e-12: win_sets['stage12_ugcs'].add(pk)
            elif d_ugcs < -1e-12: loss_sets['stage12_ugcs'].add(pk)

    v1_w = win_sets['v1']
    s8_w = win_sets['stage8']
    cns_w = win_sets['stage11_cns']
    ugcs_w = win_sets['stage12_ugcs']

    print(f"\nTotal physical builds analyzed: {len(per_build_deltas)}")
    print(f"v1 wins: {len(v1_w)}")
    print(f"stage8 wins: {len(s8_w)}")
    print(f"stage11_cns wins: {len(cns_w)}")
    print(f"stage12_ugcs wins: {len(ugcs_w)}")

    inter_v1_s8 = v1_w & s8_w
    inter_v1_cns = v1_w & cns_w
    inter_v1_ugcs = v1_w & ugcs_w
    inter_all = v1_w & s8_w & cns_w & ugcs_w

    print(f"\nIntersection v1 & Stage 8: {len(inter_v1_s8)} / 38 (retained {len(inter_v1_s8)/38*100:.1f}%)")
    print(f"Intersection v1 & Stage 11: {len(inter_v1_cns)} / 38 (retained {len(inter_v1_cns)/38*100:.1f}%)")
    print(f"Intersection v1 & Stage 12: {len(inter_v1_ugcs)} / 38 (retained {len(inter_v1_ugcs)/38*100:.1f}%)")
    print(f"Are v1 wins and Stage 11 wins identical? {v1_w == cns_w}")

    # Output winning builds intersection JSON
    inter_report = {
        'metadata': {
            'purpose': 'Track winning builds across algorithm generations vs history_cost',
            'split': 'development_screening',
            'total_failing_physical_builds': len(per_build_deltas)
        },
        'generation_win_counts': {
            'hc_falcon_normalized_v1': len(v1_w),
            'stage8_restricted_semantic': len(s8_w),
            'stage11_cns_greedy': len(cns_w),
            'stage12_ugcs_v2': len(ugcs_w)
        },
        'intersections_with_v1_38_wins': {
            'retained_in_stage8': {
                'count': len(inter_v1_s8),
                'pct_of_v1': len(inter_v1_s8) / len(v1_w) * 100,
                'build_ids': sorted(list(inter_v1_s8))
            },
            'lost_in_stage8': {
                'count': len(v1_w - s8_w),
                'build_ids': sorted(list(v1_w - s8_w))
            },
            'new_wins_in_stage8_not_in_v1': {
                'count': len(s8_w - v1_w),
                'build_ids': sorted(list(s8_w - v1_w))
            },
            'retained_in_stage11_cns': {
                'count': len(inter_v1_cns),
                'pct_of_v1': len(inter_v1_cns) / len(v1_w) * 100,
                'build_ids': sorted(list(inter_v1_cns))
            },
            'lost_in_stage11_cns': {
                'count': len(v1_w - cns_w),
                'build_ids': sorted(list(v1_w - cns_w))
            },
            'new_wins_in_stage11_not_in_v1': {
                'count': len(cns_w - v1_w),
                'build_ids': sorted(list(cns_w - v1_w))
            },
            'retained_in_stage12_ugcs': {
                'count': len(inter_v1_ugcs),
                'pct_of_v1': len(inter_v1_ugcs) / len(v1_w) * 100,
                'build_ids': sorted(list(inter_v1_ugcs))
            },
            'retained_in_all_four_generations': {
                'count': len(inter_all),
                'build_ids': sorted(list(inter_all))
            }
        },
        'identical_sets_v1_vs_stage11': (v1_w == cns_w)
    }

    out_inter = ROOT / 'reports/stage12/winning_builds_intersection.json'
    out_inter.write_text(json.dumps(inter_report, indent=2), encoding='utf-8')
    print(f"Saved intersection report to {out_inter}")

    # 4. Compute Absolute APFDc for UGCS v2
    ugcs_abs_report = {
        'metadata': {
            'purpose': 'Absolute APFDc of UGCS v2 derived from per-build history_cost + delta',
            'split': 'development_screening',
            'formula': 'APFDc(UGCS v2)_i = APFDc(history_cost)_i + Delta_i',
            'note': 'Suy ra trực tiếp từ chênh lệch ghép cặp theo từng build vật lý'
        },
        'projects': {}
    }

    all_hc_vals = []
    all_ugcs_vals = []

    for project in PROJECTS:
        scores = per_project_phys_scores[project]
        hc_vals = [scores['history_cost'][pk] for pk in scores['history_cost']]
        ugcs_vals = [scores['hc_ugcs_v2'][pk] for pk in scores['history_cost']]

        all_hc_vals.extend(hc_vals)
        all_ugcs_vals.extend(ugcs_vals)

        ugcs_abs_report['projects'][project] = {
            'n_physical_builds': len(hc_vals),
            'history_cost': {
                'mean': statistics.mean(hc_vals),
                'median': statistics.median(hc_vals)
            },
            'hc_ugcs_v2_derived': {
                'mean': statistics.mean(ugcs_vals),
                'median': statistics.median(ugcs_vals)
            },
            'paired_delta': {
                'mean': statistics.mean(ugcs_vals) - statistics.mean(hc_vals),
                'median': statistics.median([u - h for u, h in zip(ugcs_vals, hc_vals)])
            }
        }

    ugcs_abs_report['total'] = {
        'n_physical_builds': len(all_hc_vals),
        'history_cost': {
            'mean': statistics.mean(all_hc_vals),
            'median': statistics.median(all_hc_vals)
        },
        'hc_ugcs_v2_derived': {
            'mean': statistics.mean(all_ugcs_vals),
            'median': statistics.median(all_ugcs_vals)
        }
    }

    out_ugcs = ROOT / 'reports/stage12/ugcs_v2_absolute_apfdc.json'
    out_ugcs.write_text(json.dumps(ugcs_abs_report, indent=2), encoding='utf-8')
    print(f"Saved UGCS v2 absolute APFDc report to {out_ugcs}")

if __name__ == '__main__':
    main()
