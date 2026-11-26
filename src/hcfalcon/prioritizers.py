"""Test prioritizers behind one interface: ``rank(ctx) -> permutation of range(len(ctx.names))``.

A ``RankContext`` carries only what is known *before* the TSR runs: test names and history features.
Outcomes and durations of the current run are never in it, so a prioritizer cannot leak them.

Baselines replicate LRTS ``evaluation/eval_tcp.py`` exactly. Every technique sorts ascending by
``prio = base * hybrid`` and breaks ties with a per-test uniform draw (``tie="random"``); results are
averaged over seeds. ``tie="duration_name"`` gives the deterministic order of our protocol
(shorter last duration first, then name).

==========================  =================================  ================================
id (LRTS name)              paper name                         base score (ascending)
==========================  =================================  ================================
Random                      Random                             U(0, 1)
QTF                         QTF                                last_duration + eps
QTF(Avg)                    QTF-Avg                            average_duration + eps
LastFail_Asc                LatestFail                         last_failure + eps
FailCount_Desc              MostFail                           1 / (failure_count + eps)
LastTrans_Asc               LatestTrans                        last_transition + eps
TransCount_Desc             MostTrans                          1 / (transition_count + eps)
==========================  =================================  ================================

Prefix ``cbt_`` (cost-cognizant, CC) multiplies by ``last_duration + eps``; prefix ``hcbt_``
(cost-history-cognizant, CCH) multiplies by ``(last_duration + eps) / (failure_count + eps)``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

EPS = 1e-6  # LRTS ``epsilon``

BASE_SCORES = {
    "QTF": lambda f: f["last_duration"] + EPS,
    "QTF(Avg)": lambda f: f["average_duration"] + EPS,
    "LastFail_Asc": lambda f: f["last_failure"] + EPS,
    "FailCount_Desc": lambda f: 1 / (f["failure_count"] + EPS),
    "LastTrans_Asc": lambda f: f["last_transition"] + EPS,
    "TransCount_Desc": lambda f: 1 / (f["transition_count"] + EPS),
}
HYBRIDS = {
    "cbt_": lambda f: f["last_duration"] + EPS,
    # same float operations as LRTS: 1 / ((fc + eps) / (ld + eps))
    "hcbt_": lambda f: 1 / ((f["failure_count"] + EPS) / (f["last_duration"] + EPS)),
}
PAPER_NAMES = {
    "Random": "Random", "QTF": "QTF", "QTF(Avg)": "QTF-Avg",
    "LastFail_Asc": "LatestFail", "FailCount_Desc": "MostFail",
    "LastTrans_Asc": "LatestTrans", "TransCount_Desc": "MostTrans",
}
#: baselines checked against LRTS ``eval_outcome`` (week 3)
LRTS_BASELINES = ["Random", "QTF", "QTF(Avg)", "LastFail_Asc", "FailCount_Desc", "LastTrans_Asc",
                  "TransCount_Desc", "cbt_LastFail_Asc", "cbt_FailCount_Desc", "hcbt_LastFail_Asc"]


@dataclass
class RankContext:
    names: np.ndarray                 # test class names of the TSR being ranked
    features: dict                    # HistoryStore.features(names)
    rng: np.random.Generator
    project: str = ""
    stage: str = ""
    timestamp: float = float("nan")
    extra: dict = field(default_factory=dict)  # embeddings etc. (week 4+)


def paper_name(method: str) -> str:
    for prefix, tag in (("hcbt_", "+CCH"), ("cbt_", "+CC")):
        if method.startswith(prefix):
            return PAPER_NAMES[method[len(prefix):]] + tag
    return PAPER_NAMES.get(method, method)


def deterministic_tie(ctx: RankContext) -> np.ndarray:
    """Rank of (last_duration, name) per test: shorter first, then lexicographic."""
    order = np.lexsort((ctx.names, ctx.features["last_duration"]))
    rank = np.empty(len(order), dtype=np.float64)
    rank[order] = np.arange(len(order))
    return rank


class HeuristicPrioritizer:
    """LRTS time / history baselines and their CC / CCH hybrids."""

    def __init__(self, method: str, tie: str = "random"):
        if tie not in ("random", "duration_name"):
            raise ValueError(f"unknown tie-break {tie!r}")
        hybrid, base = None, method
        for prefix in HYBRIDS:
            if method.startswith(prefix):
                hybrid, base = prefix, method[len(prefix):]
        if base != "Random" and base not in BASE_SCORES:
            raise ValueError(f"unknown baseline {method!r}")
        if base == "Random" and hybrid:
            raise ValueError("Random has no hybrid variant")
        self.name, self.base, self.hybrid, self.tie = method, base, hybrid, tie
        self.stochastic = tie == "random"

    def scores(self, ctx: RankContext) -> np.ndarray:
        n = len(ctx.names)
        if self.base == "Random":
            return ctx.rng.random(n)
        s = BASE_SCORES[self.base](ctx.features)
        return s * HYBRIDS[self.hybrid](ctx.features) if self.hybrid else s

    def rank(self, ctx: RankContext) -> np.ndarray:
        prio = self.scores(ctx)
        tie = ctx.rng.random(len(prio)) if self.tie == "random" else deterministic_tie(ctx)
        return np.lexsort((tie, prio))


def make_prioritizer(method: str, **kwargs):
    return HeuristicPrioritizer(method, **kwargs)
