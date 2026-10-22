"""Development revision: semantic/cost selection within a raw-history score band."""
import numpy as np


def rank(snapshot, test_ids, kernel, *, history_only=False):
    ids = tuple(test_ids)
    features = {f.test_id:f for f in snapshot.features}
    if len(set(ids)) != len(ids) or set(ids) != set(features):
        raise ValueError('Unique full inventory must match snapshot')
    q = np.asarray([features[t].history_cost_score for t in ids], dtype=np.float64)
    cost = np.asarray([features[t].duration_estimate for t in ids], dtype=np.float64)
    if not np.isfinite(q).all() or (q < 0).any() or not np.isfinite(cost).all() or (cost < 0).any():
        raise ValueError('Invalid historical scores or costs')
    cost = np.maximum(cost, 1e-6)
    baseline = sorted(range(len(ids)), key=lambda i:(-q[i],ids[i]))
    if history_only:
        return tuple(ids[i] for i in baseline), []
    k = np.asarray(kernel, dtype=np.float32)
    if k.shape != (len(ids),len(ids)) or not np.isfinite(k).all() or (k < 0).any() or (k > 1).any():
        raise ValueError('Invalid kernel')
    remaining = set(baseline)
    coverage = np.zeros(len(ids), dtype=np.float64)
    cursor, trace = 0, []
    while remaining:
        while baseline[cursor] not in remaining:
            cursor += 1
        b = baseline[cursor]
        pool = sorted((i for i in remaining if q[i] >= .95*q[b] and cost[i] <= 1.25*cost[b]),
                      key=lambda i:ids[i])
        gains = {i:float(np.maximum(k[:,i].astype(np.float64)-coverage,0).sum()) for i in pool}
        zero = all(g == 0 for g in gains.values())
        chosen = b if zero else min(pool,key=lambda i:(-gains[i]/cost[i],-q[i],ids[i]))
        trace.append(dict(test_id=ids[chosen], baseline_head=ids[b], candidate_count=len(pool),
            q=float(q[chosen]), head_q=float(q[b]), predicted_cost=float(cost[chosen]),
            head_predicted_cost=float(cost[b]), semantic_gain=gains[chosen],
            zero_q=bool(q[b] == 0), zero_gain_fallback=zero))
        coverage = np.maximum(coverage,k[:,chosen])
        remaining.remove(chosen)
    return tuple(row['test_id'] for row in trace), trace
