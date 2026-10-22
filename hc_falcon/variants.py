"""Experimental candidate rankers for Topic 1 improvement (Phase 3).

Variants:
1. rank_cns: Cost-Normalized Semantic Greedy (CNS-Greedy)
   Discounts semantic marginal gain by sqrt(predicted_cost) to balance
   dimensional scaling with the history score q(t).
2. rank_knapsack: Knapsack Submodular Greedy
   Applies full benefit-cost ratio scaling over total marginal gain.
3. rank_tiered: Tiered History-Semantic Optimization (THS-Greedy)
   Partitions tests into confidence bands; within each band, optimizes
   cost-effective semantic coverage.
"""
from dataclasses import dataclass
import math
import numpy as np


def rank_cns(snapshot, test_ids, kernel, alpha=0.5):
    """Cost-Normalized Semantic Greedy (vectorized)."""
    ids = tuple(test_ids)
    n = len(ids)
    features = {f.test_id: f for f in snapshot.features}
    if len(set(ids)) != n or set(ids) != set(features):
        raise ValueError('Test IDs must match snapshot features exactly')
    
    q = np.asarray([features[t].history_cost_score for t in ids], dtype=np.float64)
    costs = np.asarray([features[t].duration_estimate for t in ids], dtype=np.float64)
    if not np.isfinite(q).all() or (q < 0).any() or not np.isfinite(costs).all() or (costs < 0).any():
        raise ValueError('Scores and costs must be finite and nonnegative')
    
    k = np.asarray(kernel, dtype=np.float64)
    if k.shape != (n, n) or not np.isfinite(k).all() or (k < 0).any() or (k > 1).any():
        raise ValueError('Invalid similarity kernel')
        
    sum_q = q.sum()
    w = q / sum_q if sum_q > 0 else np.zeros(n, dtype=np.float64)
    sqrt_cost = np.sqrt(np.maximum(costs, 1e-6))
    
    coverage = np.zeros(n, dtype=np.float64)
    remaining = list(range(n))
    order = []
    
    for _ in range(n):
        rem_idx = np.asarray(remaining, dtype=int)
        # Vectorized marginal semantic gain
        marginal = np.maximum(k[:, rem_idx] - coverage[:, None], 0.0).sum(axis=0) / n
        balanced_sem = marginal / sqrt_cost[rem_idx]
        gains = alpha * balanced_sem + (1.0 - alpha) * w[rem_idx]
        
        # Exact tie breaking: max gain desc, then FQN asc
        best_pos = None
        best_gain = -1e18
        for pos, (i, g) in enumerate(zip(rem_idx, gains)):
            if g > best_gain or (abs(g - best_gain) < 1e-12 and (best_pos is None or ids[i] < ids[rem_idx[best_pos]])):
                best_gain = g
                best_pos = pos
                
        best_i = rem_idx[best_pos]
        order.append(ids[best_i])
        coverage = np.maximum(coverage, k[:, best_i])
        remaining.remove(best_i)
        
    return tuple(order)


def rank_knapsack(snapshot, test_ids, kernel, alpha=0.5, gamma=0.5):
    """Knapsack Submodular Greedy (vectorized)."""
    ids = tuple(test_ids)
    n = len(ids)
    features = {f.test_id: f for f in snapshot.features}
    if len(set(ids)) != n or set(ids) != set(features):
        raise ValueError('Test IDs must match snapshot features exactly')
        
    q = np.asarray([features[t].history_cost_score for t in ids], dtype=np.float64)
    costs = np.asarray([features[t].duration_estimate for t in ids], dtype=np.float64)
    if not np.isfinite(q).all() or (q < 0).any() or not np.isfinite(costs).all() or (costs < 0).any():
        raise ValueError('Scores and costs must be finite and nonnegative')
        
    k = np.asarray(kernel, dtype=np.float64)
    if k.shape != (n, n) or not np.isfinite(k).all() or (k < 0).any() or (k > 1).any():
        raise ValueError('Invalid similarity kernel')
        
    sum_q = q.sum()
    w = q / sum_q if sum_q > 0 else np.zeros(n, dtype=np.float64)
    cost_denom = np.power(np.maximum(costs, 1e-6), gamma)
    
    coverage = np.zeros(n, dtype=np.float64)
    remaining = list(range(n))
    order = []
    
    for _ in range(n):
        rem_idx = np.asarray(remaining, dtype=int)
        marginal = np.maximum(k[:, rem_idx] - coverage[:, None], 0.0).sum(axis=0) / n
        raw_gain = alpha * marginal + (1.0 - alpha) * w[rem_idx]
        gains = raw_gain / cost_denom[rem_idx]
        
        best_pos = None
        best_gain = -1e18
        for pos, (i, g) in enumerate(zip(rem_idx, gains)):
            if g > best_gain or (abs(g - best_gain) < 1e-12 and (best_pos is None or ids[i] < ids[rem_idx[best_pos]])):
                best_gain = g
                best_pos = pos
                
        best_i = rem_idx[best_pos]
        order.append(ids[best_i])
        coverage = np.maximum(coverage, k[:, best_i])
        remaining.remove(best_i)
        
    return tuple(order)


def rank_tiered(snapshot, test_ids, kernel):
    """Tiered History-Semantic Optimization (THS-Greedy) (vectorized)."""
    ids = tuple(test_ids)
    n = len(ids)
    features = {f.test_id: f for f in snapshot.features}
    if len(set(ids)) != n or set(ids) != set(features):
        raise ValueError('Test IDs must match snapshot features exactly')
        
    q = np.asarray([features[t].history_cost_score for t in ids], dtype=np.float64)
    costs = np.asarray([features[t].duration_estimate for t in ids], dtype=np.float64)
    if not np.isfinite(q).all() or (q < 0).any() or not np.isfinite(costs).all() or (costs < 0).any():
        raise ValueError('Scores and costs must be finite and nonnegative')
        
    k = np.asarray(kernel, dtype=np.float64)
    if k.shape != (n, n) or not np.isfinite(k).all() or (k < 0).any() or (k > 1).any():
        raise ValueError('Invalid similarity kernel')
        
    max_q = q.max() if len(q) > 0 else 0.0
    if max_q == 0.0:
        tiers = np.zeros(n, dtype=int)
    else:
        tiers = np.where(q >= 0.5 * max_q, 0,
                np.where(q >= 0.1 * max_q, 1,
                np.where(q > 0.0, 2, 3)))
                
    order = []
    coverage = np.zeros(n, dtype=np.float64)
    sqrt_cost = np.sqrt(np.maximum(costs, 1e-6))
    
    for t_idx in sorted(set(tiers)):
        in_tier = [i for i in range(n) if tiers[i] == t_idx]
        remaining = list(in_tier)
        while remaining:
            rem_idx = np.asarray(remaining, dtype=int)
            marginal = np.maximum(k[:, rem_idx] - coverage[:, None], 0.0).sum(axis=0) / n
            vals = marginal / sqrt_cost[rem_idx]
            
            best_pos = None
            best_val = -1e18
            for pos, (i, v) in enumerate(zip(rem_idx, vals)):
                if v > best_val or (abs(v - best_val) < 1e-12 and (best_pos is None or (-q[i], ids[i]) < (-q[rem_idx[best_pos]], ids[rem_idx[best_pos]]))):
                    best_val = v
                    best_pos = pos
                    
            best_i = rem_idx[best_pos]
            order.append(ids[best_i])
            coverage = np.maximum(coverage, k[:, best_i])
            remaining.remove(best_i)
            
    return tuple(order)
