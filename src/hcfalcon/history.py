"""Per-test execution history, updated strictly after each TSR has been ranked.

One ``HistoryStore`` per (project, stage), fed TSRs in ``build_timestamp`` order. The LRTS features
(``evaluation/extract_hist_features.py``) are reproduced exactly:

==================  ===========================================================================
failure_count       number of past failing runs
last_failure        runs since the last failure (1 = failed last time; counts up from 0 for a test
                    that never failed, as in LRTS)
transition_count    number of outcome changes (the state before the first run is "pass")
last_transition     runs since the last transition
average_duration    mean past duration, rounded to 3 decimals as LRTS writes it
last_duration       duration of the last run
run_count           number of past runs
==================  ===========================================================================

A test never seen before gets all zeros (LRTS does the same). HC-FALCON's estimators (week 5) add
fields here; they must also be computed from past runs only.

Leakage guard: ``update`` requires non-decreasing timestamps and ``features(as_of=t)`` requires every
stored run to be strictly older than ``t``. The rolling loop ranks all TSRs sharing a timestamp before
updating with any of them.
"""

from __future__ import annotations

import math

import numpy as np

FEATURES = ("failure_count", "last_failure", "transition_count", "last_transition",
            "average_duration", "last_duration", "run_count")


class LeakageError(AssertionError):
    """A ranking would see information from its own or a later build."""


class HistoryStore:
    __slots__ = ("_h", "last_timestamp", "n_updates")

    def __init__(self):
        # name -> [failure_count, last_failure, transition_count, last_transition,
        #          average_duration, last_duration, run_count, last_outcome]
        self._h: dict[str, list] = {}
        self.last_timestamp = -math.inf
        self.n_updates = 0

    def __len__(self) -> int:
        return len(self._h)

    def __contains__(self, name) -> bool:
        return name in self._h

    def features(self, names, as_of: float | None = None) -> dict[str, np.ndarray]:
        """LRTS features of ``names`` from the runs stored so far (zeros for unseen tests)."""
        if as_of is not None and not self.last_timestamp < as_of:
            raise LeakageError(f"history holds a run at t={self.last_timestamp} >= ranking time {as_of}")
        n = len(names)
        out = {k: np.zeros(n, dtype=np.float64) for k in FEATURES}
        known = np.zeros(n, dtype=bool)
        cols = [out[k] for k in FEATURES]
        for i, t in enumerate(names):
            rec = self._h.get(t)
            if rec is None:
                continue
            known[i] = True
            for j, col in enumerate(cols):
                col[i] = rec[j]
        out["average_duration"] = np.round(out["average_duration"], 3)
        out["known"] = known
        return out

    def update(self, names, durations, outcomes, timestamp: float) -> None:
        """Add one finished TSR (LRTS ``update_history``)."""
        if timestamp < self.last_timestamp:
            raise LeakageError(f"update at t={timestamp} after a run at t={self.last_timestamp}")
        h = self._h
        for t, d, o in zip(names, durations, outcomes):
            d, o = float(d), int(o)
            rec = h.get(t)
            if rec is None:
                rec = h[t] = [0, 0, 0, 0, 0.0, 0.0, 0, 0]
            fc, lf, tc, lt, avg, _, rc, lo = rec
            rec[0] = fc + (o == 1)
            rec[1] = 1 if o == 1 else lf + 1
            rec[2] = tc + (o != lo)
            rec[3] = lt + 1 if o == lo else 1
            rec[4] = (avg * rc + d) / (rc + 1)
            rec[5] = d
            rec[6] = rc + 1
            rec[7] = o
        self.last_timestamp = timestamp
        self.n_updates += 1
