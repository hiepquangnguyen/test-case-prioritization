"""Semantic failure propagation: raise q for tests that look like tests which failed recently.

    s(t) = max_{u in T_b, u != t, F_u > 0}  k(sim[t, u]) * lambda ** (last_failure_u - 1)
    k(x) = max(0, (x - tau) / (1 - tau))

- ``tau`` is the ``quantile`` (default 0.95) of the off-diagonal similarities among the tests of the
  current TSR that have source, so only close neighbours count (median cosine on ActiveMQ is ~0.28, which
  would otherwise make every test a "neighbour" of every failure);
- ``last_failure_u`` is the LRTS feature: 1 if u failed in its last run, so a failure k runs ago weighs
  ``lambda ** (k - 1)``;
- the test itself is excluded: its own history is already in p.

Everything comes from the past (F_u, last_failure_u) and from source code of the current build, so no
outcome of the TSR being ranked is used. s(t) is in [0, 1], depends only on t (not on the selected set), and
enters q additively (``scoring.score``), so the objective stays monotone submodular.

Pre-registered in ``paper/preregistration-B.md`` before any Jackrabbit Oak / HBase data was used.
"""

from __future__ import annotations

import numpy as np


def neighbour_threshold(sim: np.ndarray, found: np.ndarray, quantile: float) -> float:
    idx = np.flatnonzero(found)
    if len(idx) < 2:
        return 1.0
    sub = sim[np.ix_(idx, idx)]
    iu = np.triu_indices(len(idx), 1)
    return float(np.quantile(sub[iu], quantile))


def propagation_score(sim: np.ndarray, found: np.ndarray, feats: dict, lam: float = 0.8,
                      quantile: float = 0.95) -> tuple[np.ndarray, np.ndarray]:
    """(s, source): s[t] as above, source[t] = index of the neighbour giving the max (-1 if s[t] = 0)."""
    n = len(sim)
    s, src = np.zeros(n), np.full(n, -1, dtype=np.int64)
    failed_before = (feats["failure_count"] > 0) & np.asarray(found, bool)
    if not failed_before.any():
        return s, src
    tau = neighbour_threshold(sim, found, quantile)
    if tau >= 1.0:
        return s, src
    U = np.flatnonzero(failed_before)
    w = lam ** (np.maximum(feats["last_failure"][U], 1.0) - 1.0)
    K = np.clip((sim[:, U].astype(np.float64) - tau) / (1.0 - tau), 0.0, None) * w[None, :]
    K[U, np.arange(len(U))] = 0.0  # a test does not propagate to itself
    j = K.argmax(axis=1)
    s = K[np.arange(n), j]
    src = np.where(s > 0, U[j], -1)
    return s, src
