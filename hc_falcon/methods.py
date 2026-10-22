"""Outcome-free ranker integration using frozen historical snapshots."""
import math
import numpy as np
from tcp.baselines import METHODS, rank as baseline_rank
from .greedy import normalize, rank

SEMANTIC_METHODS = ('hc_falcon_normalized_v1', 'hc_falcon_topic_raw_v1',
                    'fl_only', 'fl_history', 'no_confidence',
                    'borda_history', 'borda_history_cost')


def prioritize(snapshot, test_ids, kernel, method, alpha=0.5, lazy=True, seed=0):
    ids = tuple(test_ids)
    features = {f.test_id: f for f in snapshot.features}
    if len(set(ids)) != len(ids) or set(ids) != set(features):
        raise ValueError('Kernel inventory differs from snapshot')
    if method in METHODS:
        return baseline_rank(snapshot, method, seed), ()
    if method not in SEMANTIC_METHODS:
        raise ValueError('Unknown method: ' + method)
    q = [features[t].history_cost_score for t in ids]
    if method.startswith('borda_'):
        first, _ = rank(ids, kernel, np.zeros(len(ids)), alpha=1, lazy=lazy)
        second = baseline_rank(snapshot, 'history_only' if method == 'borda_history' else 'history_cost')
        positions = {t: i for i, t in enumerate(first)}
        for i, t in enumerate(second):
            positions[t] += i
        return tuple(sorted(ids, key=lambda t: (positions[t], t))), ()
    if method == 'fl_only':
        alpha, weights = 1, np.zeros(len(ids))
    elif method == 'hc_falcon_topic_raw_v1':
        weights = q
    elif method == 'fl_history':
        weights = normalize([features[t].history_score for t in ids])
    elif method == 'no_confidence':
        weights = normalize([features[t].probability / (math.sqrt(features[t].normalized_duration) + 1e-8) for t in ids])
    else:
        weights = normalize(q)
    return rank(ids, kernel, weights, alpha, lazy)
