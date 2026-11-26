"""Facility location + modular objective, ordered by (lazy) greedy.

    F(S)  = fl_weight * FL(S) + sum_{t in S} modular[t]
    FL(S) = sum_u max_{s in S} sim[u, s]          (FL(empty) = 0)

* FALCON:     fl_weight = 1,          modular = 0
* HC-FALCON:  fl_weight = alpha / n,  modular = (1 - alpha) * q

Marginal gain of t given S (``cur[u] = max_{s in S} sim[u, s]``):

    dF(t | S) = fl_weight * sum_u max(0, sim[u, t] - cur[u]) + modular[t]

Running greedy until every test is selected yields a full order. With a deterministic
tie-break, its first k elements are exactly the greedy solution for budget k, so with
sim >= 0 and modular >= 0 every prefix carries the (1 - 1/e) guarantee.

Tie-break: higher score first; equal scores -> smaller ``tie_rank``; then smaller index.
``lazy_greedy`` and ``standard_greedy`` compute every gain through the same helper, so they
return identical orders when sim >= 0 (asserted in tests/test_submodular.py). With raw,
possibly negative cosine (FALCON-artifact reproduction only) gains are not guaranteed to
shrink after the first pick, so lazy evaluation is then a heuristic, exactly as in FALCON.

Optional ``denom`` turns the selection rule into the cost-benefit ratio dF(t|S) / denom[t]
(the time-budget / knapsack variant). Ratios are still non-increasing over iterations, so lazy
evaluation stays exact, but the (1 - 1/e) cardinality guarantee no longer applies.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field

import numpy as np


@dataclass
class GreedyResult:
    order: np.ndarray            # selected test indices, in selection order
    score: np.ndarray            # value used to select (gain, or gain / denom)
    gain: np.ndarray             # total marginal gain fl_weight * dFL + modular
    fl_gain: np.ndarray          # raw dFL (before fl_weight)
    modular_gain: np.ndarray     # modular[t]
    n_gain_evals: int            # number of marginal-gain evaluations
    top_covered: list = field(default_factory=list)  # per step: [(u, improvement), ...]


# --------------------------------------------------------------------------- objective


def fl_value(sim: np.ndarray, selected) -> float:
    """FL(S) = sum_u max_{s in S} sim[u, s]; 0 for the empty set."""
    selected = list(selected)
    if not selected:
        return 0.0
    sim = np.asarray(sim, dtype=np.float64)
    return float(sim[:, selected].max(axis=1).sum())


def objective(sim: np.ndarray, selected, fl_weight: float = 1.0, modular=None) -> float:
    selected = list(selected)
    value = fl_weight * fl_value(sim, selected)
    if modular is not None and selected:
        value += float(np.asarray(modular, dtype=np.float64)[selected].sum())
    return value


# --------------------------------------------------------------------------- internals


class _State:
    """Shared state so lazy and standard greedy evaluate gains identically."""

    def __init__(self, sim, fl_weight, modular, denom, tie_rank):
        sim = np.asarray(sim)
        if sim.ndim != 2 or sim.shape[0] != sim.shape[1]:
            raise ValueError(f"sim must be square, got shape {sim.shape}")
        n = sim.shape[0]
        if fl_weight < 0:
            raise ValueError("fl_weight must be >= 0")
        self.n = n
        # simT[t] is column t of sim: how similar every u is to candidate t.
        self.simT = np.ascontiguousarray(sim.T)
        self.fl_weight = float(fl_weight)

        self.modular = np.zeros(n) if modular is None else np.asarray(modular, dtype=np.float64)
        if self.modular.shape != (n,):
            raise ValueError("modular must have shape (n,)")
        if (self.modular < 0).any():
            raise ValueError("modular weights must be >= 0 (needed for monotonicity)")

        self.denom = None if denom is None else np.asarray(denom, dtype=np.float64)
        if self.denom is not None:
            if self.denom.shape != (n,) or (self.denom <= 0).any():
                raise ValueError("denom must have shape (n,) and be > 0")

        self.tie_rank = np.arange(n) if tie_rank is None else np.asarray(tie_rank)
        if self.tie_rank.shape != (n,):
            raise ValueError("tie_rank must have shape (n,)")

        self.cur = None  # None == nothing selected yet (max over the empty set)
        self.n_evals = 0

    def fl_gain(self, t: int) -> float:
        col = self.simT[t]
        if self.cur is None:
            # Empty S: gain is the column sum. Identical to sum(max(0, col - 0)) when col >= 0,
            # and matches the FALCON artifact when raw cosine is used.
            return float(col.sum(dtype=np.float64))
        return float(np.maximum(col - self.cur, 0.0).sum())

    def evaluate(self, t: int):
        self.n_evals += 1
        g_fl = self.fl_gain(t)
        gain = self.fl_weight * g_fl + self.modular[t]
        score = gain / self.denom[t] if self.denom is not None else gain
        return score, gain, g_fl

    def select(self, t: int, explain_top: int):
        col = self.simT[t].astype(np.float64)
        top = []
        if explain_top > 0:
            base = np.zeros(self.n) if self.cur is None else self.cur
            improvement = np.maximum(col - base, 0.0)
            k = min(explain_top, self.n)
            idx = np.argpartition(-improvement, k - 1)[:k]
            idx = idx[np.lexsort((idx, -improvement[idx]))]
            top = [(int(u), float(improvement[u])) for u in idx if improvement[u] > 0]
        self.cur = col.copy() if self.cur is None else np.maximum(self.cur, col)
        return top


def _result(state, order, score, gain, flg, top):
    return GreedyResult(
        order=np.asarray(order, dtype=np.int64),
        score=np.asarray(score),
        gain=np.asarray(gain),
        fl_gain=np.asarray(flg),
        modular_gain=state.modular[np.asarray(order, dtype=np.int64)] if order else np.array([]),
        n_gain_evals=state.n_evals,
        top_covered=top,
    )


# --------------------------------------------------------------------------- algorithms


def lazy_greedy(
    sim: np.ndarray,
    fl_weight: float = 1.0,
    modular=None,
    denom=None,
    tie_rank=None,
    budget: int | None = None,
    explain_top: int = 0,
) -> GreedyResult:
    """Minoux's lazy greedy. Same output as :func:`standard_greedy`, far fewer gain evaluations."""
    st = _State(sim, fl_weight, modular, denom, tie_rank)
    budget = st.n if budget is None else min(budget, st.n)

    heap = []
    stamp = np.zeros(st.n, dtype=np.int64)   # iteration at which the cached score was computed
    cache = {}
    for t in range(st.n):
        score, gain, g_fl = st.evaluate(t)
        cache[t] = (gain, g_fl)
        heap.append((-score, st.tie_rank[t], t))
    heapq.heapify(heap)

    order, scores, gains, flg, tops = [], [], [], [], []
    for it in range(budget):
        while True:
            neg_score, tr, t = heap[0]
            if stamp[t] == it:
                heapq.heappop(heap)
                break
            score, gain, g_fl = st.evaluate(t)
            cache[t] = (gain, g_fl)
            stamp[t] = it
            heapq.heapreplace(heap, (-score, tr, t))
        gain, g_fl = cache[t]
        order.append(t)
        scores.append(-neg_score)
        gains.append(gain)
        flg.append(g_fl)
        tops.append(st.select(t, explain_top))
    return _result(st, order, scores, gains, flg, tops)


def standard_greedy(
    sim: np.ndarray,
    fl_weight: float = 1.0,
    modular=None,
    denom=None,
    tie_rank=None,
    budget: int | None = None,
    explain_top: int = 0,
) -> GreedyResult:
    """Plain greedy: re-evaluate every remaining candidate each round. O(n^3); for checks/timing."""
    st = _State(sim, fl_weight, modular, denom, tie_rank)
    budget = st.n if budget is None else min(budget, st.n)
    remaining = set(range(st.n))

    order, scores, gains, flg, tops = [], [], [], [], []
    for _ in range(budget):
        best_key, best = None, None
        for t in remaining:
            score, gain, g_fl = st.evaluate(t)
            key = (-score, st.tie_rank[t], t)
            if best_key is None or key < best_key:
                best_key, best = key, (t, score, gain, g_fl)
        t, score, gain, g_fl = best
        remaining.remove(t)
        order.append(t)
        scores.append(score)
        gains.append(gain)
        flg.append(g_fl)
        tops.append(st.select(t, explain_top))
    return _result(st, order, scores, gains, flg, tops)


def greedy_order(sim, method: str = "lazy", **kwargs) -> GreedyResult:
    if method == "lazy":
        return lazy_greedy(sim, **kwargs)
    if method == "standard":
        return standard_greedy(sim, **kwargs)
    raise ValueError(f"unknown greedy method {method!r}")
