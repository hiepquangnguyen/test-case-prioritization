"""Facility location plus a nonnegative modular term, with exact tie breaking."""
from dataclasses import dataclass
import heapq
import numpy as np


@dataclass(frozen=True)
class Step:
    test_id: str
    semantic_gain: float
    modular_gain: float
    total_gain: float
    coverage_sum: float


def rank(test_ids, kernel, weights, alpha=0.5, lazy=True):
    ids = tuple(test_ids)
    n = len(ids)
    k = np.asarray(kernel, dtype=np.float32)
    w = np.asarray(weights, dtype=np.float64)
    if len(set(ids)) != n or k.shape != (n, n) or w.shape != (n,):
        raise ValueError('Unique IDs and aligned square kernel/weights required')
    if not np.isfinite(k).all() or not np.isfinite(w).all():
        raise ValueError('Nonfinite ranking input')
    if (k < 0).any() or (k > 1).any() or (w < 0).any() or not 0 <= alpha <= 1:
        raise ValueError('Invalid objective parameters')
    coverage = np.zeros(n, dtype=np.float64)
    remaining = set(range(n))
    trace = []

    def gain(i):
        semantic = alpha * np.maximum(k[:, i].astype(np.float64) - coverage, 0).sum() / n
        modular = (1 - alpha) * w[i]
        return float(semantic), float(modular), float(semantic + modular)

    heap = [(-gain(i)[2], ids[i], i, 0) for i in remaining] if lazy else []
    heapq.heapify(heap)
    while remaining:
        if lazy:
            while True:
                _, _, i, stamp = heapq.heappop(heap)
                if stamp == len(trace):
                    break
                heapq.heappush(heap, (-gain(i)[2], ids[i], i, len(trace)))
        else:
            i = min(remaining, key=lambda j: (-gain(j)[2], ids[j]))
        semantic, modular, total = gain(i)
        coverage = np.maximum(coverage, k[:, i])
        trace.append(Step(ids[i], semantic, modular, total, float(coverage.sum())))
        remaining.remove(i)
    return tuple(s.test_id for s in trace), tuple(trace)


def normalize(values):
    values = np.asarray(values, dtype=np.float64)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError('Expected finite nonnegative weights')
    total = values.sum()
    return values / total if total else np.zeros_like(values)
