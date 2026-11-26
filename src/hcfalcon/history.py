"""Per-test execution history, updated strictly after each TSR has been ranked.

One ``HistoryStore`` per (project, stage), fed TSRs in ``build_timestamp`` order.

LRTS features (``evaluation/extract_hist_features.py``), reproduced exactly:

==================  ===========================================================================
failure_count       number of past failing runs (F)
last_failure        runs since the last failure (1 = failed last time; counts up from 0 for a test
                    that never failed, as in LRTS)
transition_count    number of outcome changes (the state before the first run is "pass")
last_transition     runs since the last transition
average_duration    mean past duration, rounded to 3 decimals as LRTS writes it
last_duration       duration of the last run
run_count           number of past runs (N)
==================  ===========================================================================

Extra fields for the HC-FALCON estimators (``hcfalcon.estimators``):

==================  ===========================================================================
mean_duration       unrounded mean past duration
ema_duration        exponential moving average of durations (weight ``ema_alpha`` on the newest)
last_outcome        outcome of the last run (0 for unseen tests)
n_after_fail / f_after_fail   runs whose previous run failed / of those, failing (stickiness)
n_after_pass / f_after_pass   same after a passing run (a test's first run is not counted)
decay_fail_<l>      sum over past runs of l^age * fail, age 0 = most recent run of that test
decay_runs_<l>      sum over past runs of l^age
==================  ===========================================================================

``stats()`` gives stage-level totals (all tests, all past runs) for priors and pooled rates.

A test never seen before gets all zeros. Leakage guard: ``update`` requires non-decreasing
timestamps and ``features(as_of=t)`` requires every stored run to be strictly older than ``t``. The
rolling loop ranks all TSRs sharing a timestamp before updating with any of them.
"""

from __future__ import annotations

import math

import numpy as np

FEATURES = ("failure_count", "last_failure", "transition_count", "last_transition",
            "average_duration", "last_duration", "run_count")
DEFAULT_LAMBDAS = (0.8, 0.9, 0.95)

# record layout (index into the per-test list)
_FC, _LF, _TC, _LT, _AVG, _LD, _RC, _LO, _EMA, _NAF, _FAF, _NAP, _FAP = range(13)
_BASE_FIELDS = ("failure_count", "last_failure", "transition_count", "last_transition", "mean_duration",
                "last_duration", "run_count", "last_outcome", "ema_duration", "n_after_fail", "f_after_fail",
                "n_after_pass", "f_after_pass")


class LeakageError(AssertionError):
    """A ranking would see information from its own or a later build."""


class HistoryStore:
    __slots__ = ("_h", "last_timestamp", "n_updates", "lambdas", "ema_alpha", "_fields", "_zero", "_tot")

    def __init__(self, decay_lambdas=DEFAULT_LAMBDAS, ema_alpha: float = 0.3):
        self._h: dict[str, list] = {}
        self.last_timestamp = -math.inf
        self.n_updates = 0
        self.lambdas = tuple(float(x) for x in decay_lambdas)
        self.ema_alpha = float(ema_alpha)
        self._fields = (_BASE_FIELDS + tuple(f"decay_fail_{lam:g}" for lam in self.lambdas)
                        + tuple(f"decay_runs_{lam:g}" for lam in self.lambdas))
        self._zero = [0.0] * len(self._fields)
        # runs, fails, n_after_fail, f_after_fail, n_after_pass, f_after_pass
        self._tot = [0, 0, 0, 0, 0, 0]

    def __len__(self) -> int:
        return len(self._h)

    def __contains__(self, name) -> bool:
        return name in self._h

    def features(self, names, as_of: float | None = None) -> dict[str, np.ndarray]:
        """Features of ``names`` from the runs stored so far (zeros for unseen tests)."""
        if as_of is not None and not self.last_timestamp < as_of:
            raise LeakageError(f"history holds a run at t={self.last_timestamp} >= ranking time {as_of}")
        h, zero = self._h, self._zero
        rows = [h.get(t, zero) for t in names]
        arr = np.array(rows, dtype=np.float64).reshape(len(rows), len(self._fields))
        out = {f: arr[:, j] for j, f in enumerate(self._fields)}
        out["average_duration"] = np.round(out["mean_duration"], 3)
        out["known"] = out["run_count"] > 0
        return out

    def stats(self) -> dict:
        runs, fails, naf, faf, nap, fap = self._tot
        return {"runs": runs, "fails": fails, "n_after_fail": naf, "f_after_fail": faf,
                "n_after_pass": nap, "f_after_pass": fap, "n_tests": len(self._h)}

    def update(self, names, durations, outcomes, timestamp: float) -> None:
        """Add one finished TSR (LRTS ``update_history`` plus the extra fields)."""
        if timestamp < self.last_timestamp:
            raise LeakageError(f"update at t={timestamp} after a run at t={self.last_timestamp}")
        h, lams, a, tot = self._h, self.lambdas, self.ema_alpha, self._tot
        nl = len(lams)
        for t, d, o in zip(names, durations, outcomes):
            d, o = float(d), int(o)
            rec = h.get(t)
            if rec is None:
                rec = h[t] = list(self._zero)
            rc, lo = rec[_RC], rec[_LO]
            fail = o == 1
            if rc > 0:  # stickiness: transition from the previous run of this test
                if lo == 1:
                    rec[_NAF] += 1
                    rec[_FAF] += fail
                    tot[2] += 1
                    tot[3] += fail
                else:
                    rec[_NAP] += 1
                    rec[_FAP] += fail
                    tot[4] += 1
                    tot[5] += fail
            rec[_FC] += fail
            rec[_LF] = 1 if fail else rec[_LF] + 1
            rec[_TC] += o != lo
            rec[_LT] = rec[_LT] + 1 if o == lo else 1
            rec[_AVG] = (rec[_AVG] * rc + d) / (rc + 1)
            rec[_EMA] = d if rc == 0 else a * d + (1 - a) * rec[_EMA]
            rec[_LD] = d
            rec[_RC] = rc + 1
            rec[_LO] = o
            for j, lam in enumerate(lams):
                rec[13 + j] = lam * rec[13 + j] + fail
                rec[13 + nl + j] = lam * rec[13 + nl + j] + 1.0
            tot[0] += 1
            tot[1] += fail
        self.last_timestamp = timestamp
        self.n_updates += 1
