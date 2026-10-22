"""Actual-cohort endpoint and mutation checks against stored full rankings."""
import argparse
from dataclasses import asdict, replace
import gzip
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.stage5_sources import selected
from scripts.pilot_support import conservative
from scripts.stage6_pilot import verify_implementation, write_json
from tcp.lrts import load_builds
from tcp.history import RollingHistory
from tcp.baselines import METHODS
from hc_falcon.methods import SEMANTIC_METHODS, prioritize
from hc_falcon.semantic import kernel
from hc_falcon.greedy import normalize


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', choices=('karaf','activemq','log4j'), required=True)
    args = parser.parse_args()
    verify_implementation()
    directory = ROOT / 'reports/stage6' / args.project
    ledger = json.loads((directory / 'ledger.json').read_text())
    rows = [row for row in ledger if row['checkpoint']]
    builds, _ = load_builds(ROOT / 'references/artifacts/dante/ML_TCSP.zip', args.project, len(selected(args.project)))
    builds = tuple(map(conservative, builds))
    historical = RollingHistory()
    for build in builds:
        historical.observe(build)
    endpoints = 0
    exceptions = []
    for row in rows:
        with gzip.open(directory / 'builds' / row['checkpoint'], 'rt', encoding='utf-8') as f:
            saved = json.load(f)
        orders = {r['method']:r['order'] for r in saved['rankings'] if r['seed'] == 0}
        if orders['hc_alpha_1.0'] != orders['fl_only']:
            raise AssertionError('Alpha-one endpoint mismatch: ' + str(row['key']))
        if orders['hc_alpha_0.0'] != orders['history_cost']:
            current = next(b for b in builds if asdict(b.inputs.key) == row['key'])
            snapshot = historical.snapshot(current.inputs)
            weights = normalize([f.history_cost_score for f in snapshot.features])
            weight = {f.test_id:float(w) for f,w in zip(snapshot.features,weights)}
            raw = {f.test_id:f.history_cost_score for f in snapshot.features}
            if orders['hc_alpha_0.0'] != sorted(weight, key=lambda tid:(-weight[tid],tid)):
                raise AssertionError('Alpha-zero does not obey frozen normalized float objective')
            changed = [(a,b) for a,b in zip(orders['hc_alpha_0.0'],orders['history_cost']) if a!=b]
            if any(weight[a] != weight[b] for a,b in changed):
                raise AssertionError('Non-rounding endpoint mismatch')
            records = {r['method']:r for r in saved['rankings'] if r['seed']==0}
            exceptions.append(dict(key=row['key'], kind='float64_normalization_collapses_distinct_q_to_exact_tie',
                changed_positions=[dict(normalized_first=a,raw_first=b,q_a=raw[a],q_b=raw[b],w=weight[a]) for a,b in changed],
                alpha_zero_metrics=records['hc_alpha_0.0']['metrics'], history_cost_metrics=records['history_cost']['metrics']))
        endpoints += 2
    checked = []
    for row in (rows[0], rows[-1]):
        with gzip.open(directory / 'builds' / row['checkpoint'], 'rt', encoding='utf-8') as f:
            saved = json.load(f)
        current = next(b for b in builds if asdict(b.inputs.key) == row['key'])
        snapshot = historical.snapshot(current.inputs)
        changed = RollingHistory()
        mutations = 0
        for build in builds:
            if build.inputs.key not in snapshot.eligible_builds:
                build = replace(build, outcomes=tuple(replace(o, failed=not o.failed if o.failed is not None else None, duration=987654.) for o in build.outcomes))
                mutations += 1
            changed.observe(build)
        if changed.snapshot(current.inputs) != snapshot:
            raise AssertionError('Ineligible current/future/context mutation changed history')
        vectors, valid = [], []
        for source in saved['source']:
            with np.load(ROOT / 'work/cache/stage6/vectors' / (source['cache_key'] + '.npz'), allow_pickle=False) as cached:
                vector = cached['vector']
            if hashlib.sha256(vector.tobytes()).hexdigest() != source['vector_sha256']:
                raise AssertionError('Vector hash mismatch')
            vectors.append(vector)
            valid.append(source['valid'])
        ids = tuple(t.test_id for t in current.inputs.tests)
        if ids != tuple(saved['inventory']):
            raise AssertionError('Inventory order mismatch')
        k = kernel(vectors, valid)
        orders = {r['method']:tuple(r['order']) for r in saved['rankings'] if r['seed'] == 0}
        for method in (*METHODS, *SEMANTIC_METHODS):
            actual, _ = prioritize(snapshot, ids, k, method, seed=0)
            if actual != orders[method]:
                raise AssertionError('Stored ranking differs from reconstructed replay: ' + method)
        for method in ('hc_falcon_normalized_v1','fl_only'):
            standard, _ = prioritize(snapshot, ids, k, method, lazy=False)
            if standard != orders[method]:
                raise AssertionError('Full real-kernel standard/lazy mismatch: ' + method)
        checked.append(dict(key=row['key'], full_tests=len(ids), mutated_ineligible_builds=mutations,
                            standard_lazy_real_kernel_methods=2,
                            reconstructed_methods=len(METHODS)+len(SEMANTIC_METHODS)))
    write_json(directory / 'replay-verification.json', dict(passed=True, endpoint_order_checks=endpoints,
        strict_alpha_zero_equivalence=not exceptions, numerical_tie_exceptions=exceptions,
        actual_cohort_mutation_checks=checked, scope='all development endpoints; first/last scored development full-inventory reconstruction and mutation', reserved_opened=False))
    print(args.project, 'objective endpoint checks', endpoints, 'and two full-inventory reconstructions passed;',len(exceptions),'strict alpha-zero tie exceptions')


if __name__ == '__main__':
    main()
