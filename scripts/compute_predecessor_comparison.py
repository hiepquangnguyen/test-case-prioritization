"""Compute and compare predecessor delay metrics between HC-FALCON v1 and UGCS v2.

Uses the exact same mathematical formula across all 161 failing physical builds
(171 failing stages) on the Development screening split:
- Baseline: history_cost
- Predecessors before each failing test:
  added = preds_cand - preds_hc
  removed = preds_hc - preds_cand
  T_add = sum(duration of added)
  T_rem = sum(duration of removed)
  T_net = T_add - T_rem

Saves results to reports/stage12/predecessor_comparison.json.
"""
from collections import defaultdict
import gzip
import json
import math
from pathlib import Path
import sys
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import scripts.stage12_evaluate as s12

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

    STAGE6_DIR = ROOT / 'reports/stage6'
    VECTORS_DIR = ROOT / 'work/cache/stage6/vectors'

    vectors_cache = {}
    project_data = {}

    for project in ['karaf', 'activemq', 'log4j']:
        old = STAGE6_DIR / project
        ledger = json.loads((old / 'ledger.json').read_text(encoding='utf-8'))
        builds, _ = s12.load_builds(ROOT / 'references/artifacts/dante/ML_TCSP.zip', project, len(s12.selected(project)))
        builds = tuple(map(s12.conservative, builds))
        history = s12.RollingHistory()

        v1_add, v1_rem = 0.0, 0.0
        ugcs_add, ugcs_rem = 0.0, 0.0
        scored_stages = 0
        physical_keys = set()

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

            scored_stages += 1
            phys_key = f"{row['key']['project']}/{row['key']['pr']}/{row['key']['build']}"
            physical_keys.add(phys_key)

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

            cand_pos_v1 = {tid: idx for idx, tid in enumerate(v1_order)}
            cand_pos_ugcs = {tid: idx for idx, tid in enumerate(ugcs_order)}
            hc_pos = {tid: idx for idx, tid in enumerate(hc_order)}

            for fid in [o['test_id'] for o in failing]:
                preds_hc = set(hc_order[:hc_pos[fid]])

                # v1 vs hc
                preds_v1 = set(v1_order[:cand_pos_v1[fid]])
                add_v1 = preds_v1 - preds_hc
                rem_v1 = preds_hc - preds_v1
                v1_add += sum(outcomes_by_id[t]['duration'] for t in add_v1 if outcomes_by_id[t]['duration'] is not None and math.isfinite(outcomes_by_id[t]['duration']))
                v1_rem += sum(outcomes_by_id[t]['duration'] for t in rem_v1 if outcomes_by_id[t]['duration'] is not None and math.isfinite(outcomes_by_id[t]['duration']))

                # ugcs vs hc
                preds_ugcs = set(ugcs_order[:cand_pos_ugcs[fid]])
                add_ugcs = preds_ugcs - preds_hc
                rem_ugcs = preds_hc - preds_ugcs
                ugcs_add += sum(outcomes_by_id[t]['duration'] for t in add_ugcs if outcomes_by_id[t]['duration'] is not None and math.isfinite(outcomes_by_id[t]['duration']))
                ugcs_rem += sum(outcomes_by_id[t]['duration'] for t in rem_ugcs if outcomes_by_id[t]['duration'] is not None and math.isfinite(outcomes_by_id[t]['duration']))

        project_data[project] = {
            'physical_builds': len(physical_keys),
            'failing_stages': scored_stages,
            'hc_falcon_normalized_v1': {
                't_add_seconds': v1_add,
                't_rem_seconds': v1_rem,
                't_net_seconds': v1_add - v1_rem,
            },
            'hc_ugcs_v2': {
                't_add_seconds': ugcs_add,
                't_rem_seconds': ugcs_rem,
                't_net_seconds': ugcs_add - ugcs_rem,
            }
        }

    total_physical = sum(p['physical_builds'] for p in project_data.values())
    total_stages = sum(p['failing_stages'] for p in project_data.values())
    total_v1_add = sum(p['hc_falcon_normalized_v1']['t_add_seconds'] for p in project_data.values())
    total_v1_rem = sum(p['hc_falcon_normalized_v1']['t_rem_seconds'] for p in project_data.values())
    total_ugcs_add = sum(p['hc_ugcs_v2']['t_add_seconds'] for p in project_data.values())
    total_ugcs_rem = sum(p['hc_ugcs_v2']['t_rem_seconds'] for p in project_data.values())

    out = {
        'metadata': {
            'comparison': 'Predecessor delay (T_add, T_rem, T_net) relative to baseline history_cost',
            'split': 'development_screening',
            'total_physical_builds': total_physical,
            'total_failing_stages': total_stages,
            'formula': 'For each failing test fid: added = preds_cand - preds_hc; removed = preds_hc - preds_cand; T_net = sum(duration(added)) - sum(duration(removed))',
            'note': 'Both HC-FALCON v1 and UGCS v2 are computed using the exact same formula and the exact same input events'
        },
        'projects': project_data,
        'total': {
            'physical_builds': total_physical,
            'failing_stages': total_stages,
            'hc_falcon_normalized_v1': {
                't_add_seconds': total_v1_add,
                't_rem_seconds': total_v1_rem,
                't_net_seconds': total_v1_add - total_v1_rem,
            },
            'hc_ugcs_v2': {
                't_add_seconds': total_ugcs_add,
                't_rem_seconds': total_ugcs_rem,
                't_net_seconds': total_ugcs_add - total_ugcs_rem,
            }
        }
    }

    out_path = ROOT / 'reports/stage12/predecessor_comparison.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding='utf-8')
    print(f"Results successfully saved to {out_path}")

if __name__ == '__main__':
    main()
