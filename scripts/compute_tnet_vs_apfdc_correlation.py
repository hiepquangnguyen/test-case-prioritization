"""Compute Spearman and Pearson correlations between T_net and Delta APFDc per build.

For each failing physical build on the Development screening split:
- Computes T_net = T_add - T_rem relative to history_cost
- Computes Delta APFDc = APFDc(candidate) - APFDc(history_cost)
Evaluates both:
1. HC-FALCON v1 (hc_falcon_normalized_v1)
2. UGCS v2 (hc_ugcs_v2)
per project (karaf, activemq, log4j) and across all 161 builds combined.

Outputs results to reports/stage12/tnet_vs_apfdc_correlation.json.
"""
from collections import defaultdict
import gzip
import json
import math
from pathlib import Path
import sys
import numpy as np
from scipy import stats

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import scripts.stage12_evaluate as s12
from tcp.domain import Outcome
from tcp.metrics import evaluate

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

def compute_stats(t_net_list, delta_apfdc_list):
    n = len(t_net_list)
    if n < 3:
        return None
    # Spearman rank correlation
    spearman_res = stats.spearmanr(t_net_list, delta_apfdc_list)
    # Pearson correlation
    pearson_res = stats.pearsonr(t_net_list, delta_apfdc_list)
    return {
        'n': n,
        'spearman': {
            'rho': float(spearman_res.statistic) if math.isfinite(spearman_res.statistic) else None,
            'p_value': float(spearman_res.pvalue) if math.isfinite(spearman_res.pvalue) else None,
        },
        'pearson': {
            'r': float(pearson_res.statistic) if math.isfinite(pearson_res.statistic) else None,
            'p_value': float(pearson_res.pvalue) if math.isfinite(pearson_res.pvalue) else None,
        }
    }

def main():
    cfg = json.loads((ROOT / 'configs/hc-falcon-v2-preregistered.json').read_text(encoding='utf-8'))
    sem_weight = cfg['fixed_constants']['semantic_weight']
    z_val = cfg['fixed_constants']['z_value']

    STAGE6_DIR = ROOT / 'reports/stage6'
    VECTORS_DIR = ROOT / 'work/cache/stage6/vectors'

    vectors_cache = {}

    results_by_method = {
        'hc_falcon_normalized_v1': {'projects': {}, 'all': {'t_net': [], 'delta_apfdc': []}},
        'hc_ugcs_v2': {'projects': {}, 'all': {'t_net': [], 'delta_apfdc': []}},
    }

    for project in ['karaf', 'activemq', 'log4j']:
        old = STAGE6_DIR / project
        ledger = json.loads((old / 'ledger.json').read_text(encoding='utf-8'))
        builds, _ = s12.load_builds(ROOT / 'references/artifacts/dante/ML_TCSP.zip', project, len(s12.selected(project)))
        builds = tuple(map(s12.conservative, builds))
        history = s12.RollingHistory()

        phys_data = defaultdict(lambda: {
            't_net_v1': 0.0,
            't_net_ugcs': 0.0,
            't_total': 0.0,
            'apfdc_hc': [],
            'apfdc_v1': [],
            'apfdc_ugcs': []
        })

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
            ids = tuple(saved['inventory'])
            outcomes_by_id = {o['test_id']: o for o in saved['outcomes']}
            existing = {r['method']: r for r in saved['rankings'] if r.get('seed') == 0 or 'seed' not in r}

            hc_order = existing['history_cost']['order']
            v1_order = existing['hc_falcon_normalized_v1']['order']

            vectors, valid = [], []
            for src in saved['source']:
                ck = src['cache_key']
                if ck not in vectors_cache:
                    with np.load(VECTORS_DIR / f'{ck}.npz', allow_pickle=False) as c_vec:
                        vectors_cache[ck] = c_vec['vector'].copy()
                vectors.append(vectors_cache[ck])
                valid.append(src['valid'])
            k = compute_fast_kernel(vectors, valid)
            ugcs_order = s12.rank_ugcs(snapshot, ids, k, semantic_weight=sem_weight, z_value=z_val)

            # Evaluate APFDc for this stage
            domain_outcomes = tuple(Outcome(o['test_id'], o['failed'], o['duration']) for o in saved['outcomes'])
            ev_hc = existing['history_cost']['metrics']['apfdc_midpoint']
            ev_v1 = existing['hc_falcon_normalized_v1']['metrics']['apfdc_midpoint']
            ev_ugcs = evaluate(ugcs_order, domain_outcomes)['apfdc_midpoint']

            phys_data[phys_key]['apfdc_hc'].append(ev_hc)
            phys_data[phys_key]['apfdc_v1'].append(ev_v1)
            phys_data[phys_key]['apfdc_ugcs'].append(ev_ugcs)

            # Predecessors
            cand_pos_v1 = {tid: idx for idx, tid in enumerate(v1_order)}
            cand_pos_ugcs = {tid: idx for idx, tid in enumerate(ugcs_order)}
            hc_pos = {tid: idx for idx, tid in enumerate(hc_order)}

            stage_tnet_v1 = 0.0
            stage_tnet_ugcs = 0.0

            for fid in [o['test_id'] for o in failing]:
                preds_hc = set(hc_order[:hc_pos[fid]])

                preds_v1 = set(v1_order[:cand_pos_v1[fid]])
                add_v1 = preds_v1 - preds_hc
                rem_v1 = preds_hc - preds_v1
                dur_add_v1 = sum(outcomes_by_id[t]['duration'] for t in add_v1 if outcomes_by_id[t]['duration'] is not None and math.isfinite(outcomes_by_id[t]['duration']))
                dur_rem_v1 = sum(outcomes_by_id[t]['duration'] for t in rem_v1 if outcomes_by_id[t]['duration'] is not None and math.isfinite(outcomes_by_id[t]['duration']))
                stage_tnet_v1 += (dur_add_v1 - dur_rem_v1)

                preds_ugcs = set(ugcs_order[:cand_pos_ugcs[fid]])
                add_ugcs = preds_ugcs - preds_hc
                rem_ugcs = preds_hc - preds_ugcs
                dur_add_ugcs = sum(outcomes_by_id[t]['duration'] for t in add_ugcs if outcomes_by_id[t]['duration'] is not None and math.isfinite(outcomes_by_id[t]['duration']))
                dur_rem_ugcs = sum(outcomes_by_id[t]['duration'] for t in rem_ugcs if outcomes_by_id[t]['duration'] is not None and math.isfinite(outcomes_by_id[t]['duration']))
                stage_tnet_ugcs += (dur_add_ugcs - dur_rem_ugcs)

            phys_data[phys_key]['t_net_v1'] += stage_tnet_v1
            phys_data[phys_key]['t_net_ugcs'] += stage_tnet_ugcs
            stage_total_dur = sum(o['duration'] for o in saved['outcomes'] if o['duration'] is not None and math.isfinite(o['duration']))
            phys_data[phys_key]['t_total'] += stage_total_dur

        # Aggregate per physical build
        proj_tnet_v1 = []
        proj_ratio_v1 = []
        proj_delta_v1 = []
        proj_tnet_ugcs = []
        proj_ratio_ugcs = []
        proj_delta_ugcs = []

        for pk in sorted(phys_data.keys()):
            p_entry = phys_data[pk]
            mean_hc = np.mean(p_entry['apfdc_hc'])
            mean_v1 = np.mean(p_entry['apfdc_v1'])
            mean_ugcs = np.mean(p_entry['apfdc_ugcs'])

            delta_v1 = mean_v1 - mean_hc
            delta_ugcs = mean_ugcs - mean_hc

            t_tot = p_entry['t_total'] if p_entry['t_total'] > 0 else 1.0
            r_v1 = p_entry['t_net_v1'] / t_tot
            r_ugcs = p_entry['t_net_ugcs'] / t_tot

            proj_tnet_v1.append(p_entry['t_net_v1'])
            proj_ratio_v1.append(r_v1)
            proj_delta_v1.append(delta_v1)

            proj_tnet_ugcs.append(p_entry['t_net_ugcs'])
            proj_ratio_ugcs.append(r_ugcs)
            proj_delta_ugcs.append(delta_ugcs)

        results_by_method['hc_falcon_normalized_v1']['projects'][project] = {
            't_net': compute_stats(proj_tnet_v1, proj_delta_v1),
            't_net_over_t_total': compute_stats(proj_ratio_v1, proj_delta_v1)
        }
        if 'all_t_net' not in results_by_method['hc_falcon_normalized_v1']:
            results_by_method['hc_falcon_normalized_v1']['all_t_net'] = []
            results_by_method['hc_falcon_normalized_v1']['all_ratio'] = []
            results_by_method['hc_falcon_normalized_v1']['all_delta'] = []
            results_by_method['hc_ugcs_v2']['all_t_net'] = []
            results_by_method['hc_ugcs_v2']['all_ratio'] = []
            results_by_method['hc_ugcs_v2']['all_delta'] = []

        results_by_method['hc_falcon_normalized_v1']['all_t_net'].extend(proj_tnet_v1)
        results_by_method['hc_falcon_normalized_v1']['all_ratio'].extend(proj_ratio_v1)
        results_by_method['hc_falcon_normalized_v1']['all_delta'].extend(proj_delta_v1)

        results_by_method['hc_ugcs_v2']['projects'][project] = {
            't_net': compute_stats(proj_tnet_ugcs, proj_delta_ugcs),
            't_net_over_t_total': compute_stats(proj_ratio_ugcs, proj_delta_ugcs)
        }
        results_by_method['hc_ugcs_v2']['all_t_net'].extend(proj_tnet_ugcs)
        results_by_method['hc_ugcs_v2']['all_ratio'].extend(proj_ratio_ugcs)
        results_by_method['hc_ugcs_v2']['all_delta'].extend(proj_delta_ugcs)

    # Compute overall correlation across all 161 builds
    for m in ['hc_falcon_normalized_v1', 'hc_ugcs_v2']:
        all_t = results_by_method[m]['all_t_net']
        all_r = results_by_method[m]['all_ratio']
        all_d = results_by_method[m]['all_delta']
        results_by_method[m]['overall'] = {
            't_net': compute_stats(all_t, all_d),
            't_net_over_t_total': compute_stats(all_r, all_d)
        }
        del results_by_method[m]['all_t_net']
        del results_by_method[m]['all_ratio']
        del results_by_method[m]['all_delta']
        del results_by_method[m]['all']

    output = {
        'metadata': {
            'analysis': 'Correlation between per-build T_net and per-build Delta APFDc vs history_cost',
            'split': 'development_screening',
            'sample_size': 161,
            'note': 'Exploratory diagnostic metric. Negative correlation means higher delay (larger positive T_net) correlates with lower APFDc (negative Delta APFDc).'
        },
        'correlations': results_by_method
    }

    out_path = ROOT / 'reports/stage12/tnet_vs_apfdc_correlation.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2), encoding='utf-8')
    print(f"Correlation results written to {out_path}")
    print(json.dumps(output, indent=2))

if __name__ == '__main__':
    main()
