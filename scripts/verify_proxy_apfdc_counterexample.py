"""Verify numerical counterexample for the Proxy-APFDc gap using real code.

Calls real implementations from hc_falcon.methods.prioritize and hc_falcon.greedy.rank
with real formulas for q_b(t), w_b(t), and semantic Facility Location gain.

Demonstrates that maximizing the submodular proxy objective F_N(S) under cardinality
constraint does not guarantee APFDc, and can yield arbitrarily poor APFDc due to
ignoring execution duration and true failure arrival.

Saves results to reports/stage12/proxy_apfdc_counterexample.json.
"""
import json
import math
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hc_falcon.methods import prioritize
from hc_falcon.greedy import rank as greedy_rank, normalize
from tcp.history import Feature, Snapshot, HistoryConfig
from tcp.domain import BuildKey

def compute_apfdc(order, costs, failing_set):
    """Compute APFDc midpoint as defined in evaluation protocol."""
    total_cost = sum(costs.values())
    m = len(failing_set)
    if m == 0 or total_cost == 0:
        return 0.0
    
    elapsed = 0.0
    midpoints = []
    for tid in order:
        c = costs[tid]
        if tid in failing_set:
            midpoints.append(elapsed + c / 2.0)
        elapsed += c
        
    apfdc = 1.0 - sum(midpoints) / (m * total_cost)
    return float(apfdc)

def main():
    # 3 tests: t1 (Heavy clean), t2 (Light clean), t3 (Light failing)
    test_ids = ('t1_heavy', 't2_light', 't3_failing')
    costs = {
        't1_heavy': 100.0,
        't2_light': 1.0,
        't3_failing': 1.0
    }
    failing = {'t3_failing'}
    total_cost = sum(costs.values())
    ref_cost = 1.0
    
    # Kernel matrix K (3x3)
    # t1 is moderately similar to all (0.8)
    # t2 and t3 are orthogonal to each other (0.0)
    K = np.array([
        [1.0, 0.8, 0.8],  # t1
        [0.8, 1.0, 0.0],  # t2
        [0.8, 0.0, 1.0],  # t3
    ], dtype=np.float32)
    
    # Historical feature setup: Cold-start scenario (0 prior observations)
    # Formula in tcp/history.py:86-95:
    # prob = (0 + 1) / (0 + 2) = 0.5
    # conf = 0 / (0 + 5) = 0.0
    # h_score = 0.0, q = 0.0
    features_cold = tuple([
        Feature(
            test_id=t,
            observations=0,
            failures=0,
            probability=0.5,
            confidence=0.0,
            last_failure_available_at=None,
            duration_estimate=costs[t],
            duration_origin='fixed_cold_start',
            normalized_duration=costs[t] / ref_cost,
            history_score=0.0,
            history_cost_score=0.0,
            evidence_builds=()
        )
        for t in test_ids
    ])
    snapshot_cold = Snapshot(
        key=BuildKey(project='counterexample', pr='1', build='1', stage='test'),
        cutoff=100.0,
        context=('counterexample', 'test', 'main'),
        features=features_cold,
        eligible_builds=(),
        latest_evidence_available_at=None,
        duration_reference=ref_cost
    )
    
    # Historical feature setup: Clean history scenario (10 prior runs, 0 failures)
    # prob = (0 + 1) / (10 + 2) = 1/12
    # conf = 10 / (10 + 5) = 2/3
    # h_score = conf * prob = 2/36 = 1/18
    # q = h_score / (sqrt(norm_cost) + 1e-8)
    features_clean = []
    for t in test_ids:
        c = costs[t]
        n, f = 10, 0
        prob = (f + 1.0) / (n + 2.0)
        conf = n / (n + 5.0)
        h_score = conf * prob
        norm_c = c / ref_cost
        q = h_score / (math.sqrt(norm_c) + 1e-8)
        features_clean.append(Feature(
            test_id=t,
            observations=n,
            failures=f,
            probability=prob,
            confidence=conf,
            last_failure_available_at=None,
            duration_estimate=c,
            duration_origin='test_median',
            normalized_duration=norm_c,
            history_score=h_score,
            history_cost_score=q,
            evidence_builds=()
        ))
    snapshot_clean = Snapshot(
        key=BuildKey(project='counterexample', pr='1', build='1', stage='test'),
        cutoff=100.0,
        context=('counterexample', 'test', 'main'),
        features=tuple(features_clean),
        eligible_builds=(),
        latest_evidence_available_at=None,
        duration_reference=ref_cost
    )
    
    # Execute REAL CODE calls across methods
    results_by_method = {}
    methods_to_test = [
        ('fl_only', snapshot_cold, 1.0),
        ('hc_falcon_topic_raw_v1_cold', snapshot_cold, 0.5),
        ('hc_falcon_normalized_v1_cold', snapshot_cold, 0.5),
        ('hc_falcon_topic_raw_v1_clean_history', snapshot_clean, 0.5),
    ]
    
    for label, snap, alpha_val in methods_to_test:
        method_name = label.replace('_cold', '').replace('_clean_history', '')
        # Call REAL hc_falcon.methods.prioritize
        order, trace = prioritize(
            snapshot=snap,
            test_ids=test_ids,
            kernel=K,
            method=method_name,
            alpha=alpha_val,
            lazy=True,
            seed=0
        )
        apfdc_val = compute_apfdc(order, costs, failing)
        results_by_method[label] = {
            'method': method_name,
            'alpha': alpha_val,
            'order': list(order),
            'ttff_seconds': float(sum(costs[t] for t in order[:order.index('t3_failing')])),
            'midpoint_seconds': float(sum(costs[t] for t in order[:order.index('t3_failing')]) + costs['t3_failing'] / 2.0),
            'apfdc': apfdc_val,
            'apfdc_percentage': round(apfdc_val * 100, 2),
            'trace': [
                {
                    'test_id': step.test_id,
                    'semantic_gain': step.semantic_gain,
                    'modular_gain': step.modular_gain,
                    'total_gain': step.total_gain,
                    'coverage_sum': step.coverage_sum
                }
                for step in trace
            ]
        }
    
    # Target greedy order under cold-start / fl_only / topic_raw
    greedy_order = tuple(results_by_method['fl_only']['order'])
    assert greedy_order == ('t1_heavy', 't2_light', 't3_failing'), f"Unexpected greedy order: {greedy_order}"
    
    # Cost-only order (Shortest Test First, no prior knowledge of failures)
    # Both t2 and t3 have cost 1.0; tie-broken by test ID asc ('t2_light' < 't3_failing'), then t1_heavy (100.0)
    cost_only_order = ('t2_light', 't3_failing', 't1_heavy')
    apfdc_cost_only = compute_apfdc(cost_only_order, costs, failing)
    ttff_cost_only = float(sum(costs[t] for t in cost_only_order[:cost_only_order.index('t3_failing')]))
    midpoint_cost_only = float(ttff_cost_only + costs['t3_failing'] / 2.0)
    
    # Theoretical optimal order (Upper bound: requires prior knowledge of failure)
    optimal_order = ('t3_failing', 't2_light', 't1_heavy')
    apfdc_optimal = compute_apfdc(optimal_order, costs, failing)
    
    output = {
        'description': 'Numerical counterexample proving proxy objective submodular optimality does not imply APFDc optimality. Generated by calling real code implementations hc_falcon.methods.prioritize and hc_falcon.greedy.rank.',
        'suite': {
            'tests': list(test_ids),
            'costs_seconds': costs,
            'total_cost_seconds': total_cost,
            'failing_tests': list(failing),
            'kernel_matrix': K.tolist(),
            'duration_reference_seconds': ref_cost
        },
        'input_snapshots': {
            'cold_start': {
                t: {
                    'observations': f.observations,
                    'failures': f.failures,
                    'p': f.probability,
                    'conf': f.confidence,
                    'norm_cost': f.normalized_duration,
                    'q': f.history_cost_score
                }
                for t, f in zip(test_ids, features_cold)
            },
            'clean_history_10_runs': {
                t: {
                    'observations': f.observations,
                    'failures': f.failures,
                    'p': f.probability,
                    'conf': f.confidence,
                    'norm_cost': f.normalized_duration,
                    'q': f.history_cost_score
                }
                for t, f in zip(test_ids, features_clean)
            }
        },
        'results_by_method': results_by_method,
        'comparison': {
            'greedy_sequence': list(greedy_order),
            'greedy_ttff_seconds': 101.0,
            'greedy_midpoint_seconds': 101.5,
            'greedy_apfdc': results_by_method['fl_only']['apfdc'],
            'greedy_apfdc_percentage': results_by_method['fl_only']['apfdc_percentage'],
            'cost_only_sequence': list(cost_only_order),
            'cost_only_ttff_seconds': ttff_cost_only,
            'cost_only_midpoint_seconds': midpoint_cost_only,
            'cost_only_apfdc': apfdc_cost_only,
            'cost_only_apfdc_percentage': round(apfdc_cost_only * 100, 2),
            'optimal_sequence': list(optimal_order),
            'optimal_ttff_seconds': 0.0,
            'optimal_midpoint_seconds': 0.5,
            'optimal_apfdc': apfdc_optimal,
            'optimal_apfdc_percentage': round(apfdc_optimal * 100, 2),
            'gap_greedy_vs_optimal_percentage_points': round((apfdc_optimal - results_by_method['fl_only']['apfdc']) * 100, 2),
            'gap_greedy_vs_cost_only_percentage_points': round((apfdc_cost_only - results_by_method['fl_only']['apfdc']) * 100, 2)
        }
    }
    
    out_path = ROOT / 'reports' / 'stage12' / 'proxy_apfdc_counterexample.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)
    print(f"Verified counterexample saved to {out_path}")
    print(f"Greedy order: {greedy_order} -> APFDc = {results_by_method['fl_only']['apfdc_percentage']}%")
    print(f"Cost-only order: {cost_only_order} -> APFDc = {round(apfdc_cost_only * 100, 2)}%")
    print(f"Optimal order: {optimal_order} -> APFDc = {round(apfdc_optimal * 100, 2)}%")
    print(f"Gap (Greedy vs Optimal): {round((apfdc_optimal - results_by_method['fl_only']['apfdc']) * 100, 2)} pp")
    print(f"Gap (Greedy vs Cost-only): {round((apfdc_cost_only - results_by_method['fl_only']['apfdc']) * 100, 2)} pp")

if __name__ == '__main__':
    main()
