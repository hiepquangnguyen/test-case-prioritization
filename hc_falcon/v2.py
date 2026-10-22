"""HC-FALCON v2: Uncertainty-Guarded Cost-aware Semantic ranking (hc_ugcs_v2).

Preregistered candidate algorithm combining Bayesian history credibility bounds,
cost-normalized marginal facility-location coverage, and relative utility ranking.
"""
from __future__ import annotations

import math
from typing import Sequence
import numpy as np


COST_FLOOR = 1e-6
EPSILON = 1e-8
GAIN_TOLERANCE = 1e-12
SEMANTIC_WEIGHT_DEFAULT = 0.25
Z_VALUE_DEFAULT = 1.96


def _validate_inputs(snapshot, test_ids, kernel, semantic_weight, z_value):
    ids = tuple(test_ids)
    n = len(ids)

    # 1. Unique test_ids
    if len(set(ids)) != n:
        raise ValueError("Duplicate test IDs")
    if any(not isinstance(t, str) or not t for t in ids):
        raise ValueError("Empty or non-string test ID")

    # 2. Exact match with snapshot.features
    if not hasattr(snapshot, "features"):
        raise ValueError("Snapshot must contain 'features' attribute")
    features_dict = {f.test_id: f for f in snapshot.features}
    if len(snapshot.features) != n or set(ids) != set(features_dict):
        raise ValueError("Test IDs must match snapshot features exactly")

    # 3. Parameters validation
    if not isinstance(semantic_weight, (int, float)) or not math.isfinite(semantic_weight) or not (0.0 <= semantic_weight <= 1.0):
        raise ValueError("semantic_weight must be finite and within [0, 1]")
    if not isinstance(z_value, (int, float)) or not math.isfinite(z_value) or z_value <= 0.0:
        raise ValueError("z_value must be finite and positive")

    # 4. Kernel shape and values
    k = np.asarray(kernel, dtype=np.float64)
    if k.shape != (n, n):
        raise ValueError(f"Kernel shape mismatch: expected ({n}, {n}), got {k.shape}")
    if not np.isfinite(k).all() or (k < 0.0).any() or (k > 1.0).any():
        raise ValueError("Kernel values must be finite and in [0, 1]")

    # 5. History and cost features validation
    for t in ids:
        f = features_dict[t]
        N = f.observations
        F = f.failures
        conf = f.confidence
        q = f.history_cost_score
        c = f.normalized_duration

        if not isinstance(N, (int, np.integer)) or not isinstance(F, (int, np.integer)):
            raise ValueError(f"Observations and failures for {t} must be integers")
        if N < 0 or F < 0 or F > N:
            raise ValueError(f"Invalid observation count ({N}) or failure count ({F}) for {t}")
        if not isinstance(conf, (int, float)) or not math.isfinite(conf) or conf < 0.0:
            raise ValueError(f"Confidence for {t} must be finite and nonnegative")
        if not isinstance(q, (int, float)) or not math.isfinite(q) or q < 0.0:
            raise ValueError(f"History cost score for {t} must be finite and nonnegative")
        if not isinstance(c, (int, float)) or not math.isfinite(c) or c < 0.0:
            raise ValueError(f"Normalized duration for {t} must be finite and nonnegative")

    return ids, features_dict, k, float(semantic_weight), float(z_value)


def rank_ugcs_reference(
    snapshot,
    test_ids: Sequence[str],
    kernel,
    semantic_weight: float = SEMANTIC_WEIGHT_DEFAULT,
    z_value: float = Z_VALUE_DEFAULT,
) -> tuple[str, ...]:
    """Pure Python reference implementation of Uncertainty-Guarded Cost-aware Semantic ranking."""
    ids, features_dict, k, sem_weight, z = _validate_inputs(snapshot, test_ids, kernel, semantic_weight, z_value)
    n = len(ids)
    if n == 0:
        return ()

    # Precompute statistics for each test
    q_list = []
    norm_cost_list = []
    lower_list = []
    upper_list = []

    for t in ids:
        f = features_dict[t]
        N = f.observations
        F = f.failures
        conf = float(f.confidence)
        q = float(f.history_cost_score)
        norm_cost = float(f.normalized_duration)

        a = F + 1.0
        b = N - F + 1.0
        mu = a / (a + b)
        variance = (a * b) / ((a + b) ** 2 * (a + b + 1.0))
        sigma = math.sqrt(variance)
        denom = math.sqrt(max(norm_cost, COST_FLOOR)) + EPSILON

        lower = conf * max(0.0, mu - z * sigma) / denom
        upper = conf * min(1.0, mu + z * sigma) / denom

        q_list.append(q)
        norm_cost_list.append(norm_cost)
        lower_list.append(lower)
        upper_list.append(upper)

    coverage = [0.0] * n
    remaining = list(range(n))
    order = []

    for _ in range(n):
        # 3. Select history anchor from remaining: highest q, then lexicographically smallest test_id
        anchor = min(remaining, key=lambda idx: (-q_list[idx], ids[idx]))

        # 4. Safe candidates: upper[t] + 1e-12 >= lower[anchor]
        safe = [idx for idx in remaining if upper_list[idx] + GAIN_TOLERANCE >= lower_list[anchor]]

        # 5. Marginal facility-location coverage gain
        marginal = {}
        for idx in safe:
            gain = sum(max(k[i, idx] - coverage[i], 0.0) for i in range(n)) / n
            marginal[idx] = gain

        # 6. Cost-aware semantic density
        density = {}
        for idx in safe:
            c_denom = math.sqrt(max(norm_cost_list[idx], COST_FLOOR))
            density[idx] = marginal[idx] / c_denom

        # 7. Normalization
        max_q = max(q_list[idx] for idx in remaining)
        q_relative = {}
        for idx in safe:
            q_relative[idx] = (q_list[idx] / max_q) if max_q > 0.0 else 0.0

        max_density = max(density[idx] for idx in safe)
        sem_relative = {}
        for idx in safe:
            sem_relative[idx] = (density[idx] / max_density) if max_density > 0.0 else 0.0

        # 8. Combined utility
        utility = {}
        for idx in safe:
            utility[idx] = (1.0 - sem_weight) * q_relative[idx] + sem_weight * sem_relative[idx]

        # 9. Selection: highest utility desc, then highest q desc, then lexicographically smallest test_id asc
        best_idx = None
        best_u = -1e18
        best_q_val = -1e18
        for idx in safe:
            u = utility[idx]
            qi = q_list[idx]
            ti = ids[idx]
            if best_idx is None:
                best_idx, best_u, best_q_val = idx, u, qi
            elif u > best_u + GAIN_TOLERANCE:
                best_idx, best_u, best_q_val = idx, u, qi
            elif abs(u - best_u) <= GAIN_TOLERANCE:
                if qi > best_q_val + GAIN_TOLERANCE:
                    best_idx, best_u, best_q_val = idx, u, qi
                elif abs(qi - best_q_val) <= GAIN_TOLERANCE:
                    if ti < ids[best_idx]:
                        best_idx, best_u, best_q_val = idx, u, qi

        order.append(ids[best_idx])

        # 10. Update coverage
        for i in range(n):
            if k[i, best_idx] > coverage[i]:
                coverage[i] = float(k[i, best_idx])

        remaining.remove(best_idx)

    return tuple(order)


def rank_ugcs(
    snapshot,
    test_ids: Sequence[str],
    kernel,
    semantic_weight: float = SEMANTIC_WEIGHT_DEFAULT,
    z_value: float = Z_VALUE_DEFAULT,
) -> tuple[str, ...]:
    """NumPy-vectorized implementation of Uncertainty-Guarded Cost-aware Semantic ranking.

    Guaranteed to produce identical permutations and tie-breaks as rank_ugcs_reference.
    """
    ids, features_dict, k, sem_weight, z = _validate_inputs(snapshot, test_ids, kernel, semantic_weight, z_value)
    n = len(ids)
    if n == 0:
        return ()

    # Vectorized precomputation of features
    obs = np.asarray([features_dict[t].observations for t in ids], dtype=np.float64)
    fails = np.asarray([features_dict[t].failures for t in ids], dtype=np.float64)
    conf = np.asarray([features_dict[t].confidence for t in ids], dtype=np.float64)
    q = np.asarray([features_dict[t].history_cost_score for t in ids], dtype=np.float64)
    costs = np.asarray([features_dict[t].normalized_duration for t in ids], dtype=np.float64)

    a = fails + 1.0
    b = obs - fails + 1.0
    mu = a / (a + b)
    sigma = np.sqrt((a * b) / ((a + b) ** 2 * (a + b + 1.0)))
    denom = np.sqrt(np.maximum(costs, COST_FLOOR)) + EPSILON

    lowers = conf * np.maximum(0.0, mu - z * sigma) / denom
    uppers = conf * np.minimum(1.0, mu + z * sigma) / denom

    coverage = np.zeros(n, dtype=np.float64)
    remaining = list(range(n))
    order = []

    for _ in range(n):
        # 3. Select history anchor from remaining
        anchor = min(remaining, key=lambda idx: (-q[idx], ids[idx]))

        # 4. Safe candidates
        safe = [idx for idx in remaining if uppers[idx] + GAIN_TOLERANCE >= lowers[anchor]]
        safe_arr = np.asarray(safe, dtype=np.intp)

        # 5. Vectorized marginal coverage gain
        marginal = np.maximum(k[:, safe_arr] - coverage[:, None], 0.0).sum(axis=0) / n

        # 6. Cost-aware semantic density
        sqrt_costs = np.sqrt(np.maximum(costs[safe_arr], COST_FLOOR))
        density = marginal / sqrt_costs

        # 7. Normalization
        max_q = max(q[idx] for idx in remaining)
        q_rels = (q[safe_arr] / max_q) if max_q > 0.0 else np.zeros_like(density)

        max_density = density.max() if len(density) > 0 else 0.0
        sem_rels = (density / max_density) if max_density > 0.0 else np.zeros_like(density)

        # 8. Combined utility
        utilities = (1.0 - sem_weight) * q_rels + sem_weight * sem_rels

        # 9. Selection with exact tie-breaking identical to reference
        best_idx = None
        best_u = -1e18
        best_q_val = -1e18
        for pos, idx in enumerate(safe):
            u = utilities[pos]
            qi = q[idx]
            ti = ids[idx]
            if best_idx is None:
                best_idx, best_u, best_q_val = idx, u, qi
            elif u > best_u + GAIN_TOLERANCE:
                best_idx, best_u, best_q_val = idx, u, qi
            elif abs(u - best_u) <= GAIN_TOLERANCE:
                if qi > best_q_val + GAIN_TOLERANCE:
                    best_idx, best_u, best_q_val = idx, u, qi
                elif abs(qi - best_q_val) <= GAIN_TOLERANCE:
                    if ti < ids[best_idx]:
                        best_idx, best_u, best_q_val = idx, u, qi

        order.append(ids[best_idx])

        # 10. Update coverage
        np.maximum(coverage, k[:, best_idx], out=coverage)
        remaining.remove(best_idx)

    return tuple(order)
