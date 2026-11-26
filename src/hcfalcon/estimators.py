"""Failure probability p, confidence conf and cost c of each test, from its past runs only.

Inputs are ``HistoryStore.features(names)`` and ``HistoryStore.stats()`` (stage-level totals of the
past). F = past failures, N = past runs of the test.

p estimators (``topic1.md`` asks for the first three):

- ``beta``        (F + a) / (N + a + b) with prior mean mu = stage failure rate of the past and
                  strength s: a = mu*s, b = (1-mu)*s. A new test gets p = mu, not 0.
- ``decay``       same prior on exponentially decayed counts F_l, N_l (recent runs weigh more).
- ``stickiness``  P(fail | outcome of the test's last run), estimated per test from its own
                  transitions and smoothed towards the stage-level (pooled) transition rate.
- ``wilson``      lower bound of the Wilson score interval of F/N (DANTE-style); it already shrinks
                  for small N, so it is used with conf = 1.

conf = N / (N + kappa): 0 for a new test, -> 1 with more history.

Cost c: the test's past mean (or last / EMA) duration plus the LRTS 1 ms offset; a new test gets the
median of the known costs in the same TSR. The normalised cost is c / median(c over the TSR). Only the
current TSR's test list and the past are used.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

ESTIMATORS = ("beta", "decay", "stickiness", "wilson")
DURATION_OFFSET = 0.001


def prior_mean(stats: dict) -> float:
    """Stage failure rate of the past; 0 before any run."""
    return stats["fails"] / stats["runs"] if stats.get("runs") else 0.0


def beta_p(fails, runs, mu: float, strength: float) -> np.ndarray:
    a, b = mu * strength, (1.0 - mu) * strength
    denom = np.asarray(runs, dtype=np.float64) + a + b
    with np.errstate(invalid="ignore", divide="ignore"):
        p = (np.asarray(fails, dtype=np.float64) + a) / denom
    return np.where(denom > 0, p, mu)


def wilson_lower(fails, runs, z: float = 1.96) -> np.ndarray:
    """Lower bound of the Wilson score interval; 0 when runs = 0."""
    n = np.asarray(runs, dtype=np.float64)
    f = np.asarray(fails, dtype=np.float64)
    with np.errstate(invalid="ignore", divide="ignore"):
        ph = f / n
        centre = ph + z * z / (2 * n)
        margin = z * np.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n))
        lb = (centre - margin) / (1 + z * z / n)
    return np.where(n > 0, np.clip(lb, 0.0, 1.0), 0.0)


def stickiness_p(feats: dict, stats: dict, strength: float) -> np.ndarray:
    mu = prior_mean(stats)
    pool_ff = (stats.get("f_after_fail", 0) + mu * strength) / (stats.get("n_after_fail", 0) + strength)
    pool_fp = (stats.get("f_after_pass", 0) + mu * strength) / (stats.get("n_after_pass", 0) + strength)
    after_fail = feats["last_outcome"] == 1
    p_ff = (feats["f_after_fail"] + strength * pool_ff) / (feats["n_after_fail"] + strength)
    p_fp = (feats["f_after_pass"] + strength * pool_fp) / (feats["n_after_pass"] + strength)
    p = np.where(after_fail, p_ff, p_fp)
    return np.where(feats["run_count"] > 0, p, mu)


@dataclass(frozen=True)
class EstimatorConfig:
    estimator: str = "decay"
    decay_lambda: float = 0.9
    prior_strength: float = 2.0
    kappa: float = 3.0
    duration: str = "average"          # average | last | ema
    new_test_duration: str = "median"  # median of known costs in the TSR

    def __post_init__(self):
        if self.estimator not in ESTIMATORS:
            raise ValueError(f"unknown estimator {self.estimator!r}")
        if self.duration not in ("average", "last", "ema"):
            raise ValueError(f"unknown duration estimate {self.duration!r}")


def estimate(feats: dict, stats: dict, cfg: EstimatorConfig) -> dict[str, np.ndarray]:
    """Arrays p, conf, cost, cost_norm (all >= 0, cost > 0) for the tests of one TSR."""
    runs = feats["run_count"]
    mu = prior_mean(stats)
    if cfg.estimator == "beta":
        p = beta_p(feats["failure_count"], runs, mu, cfg.prior_strength)
    elif cfg.estimator == "decay":
        key = f"{cfg.decay_lambda:g}"
        if f"decay_fail_{key}" not in feats:
            raise KeyError(f"history has no decay counts for lambda={key}; add it to HistoryStore(decay_lambdas)")
        p = beta_p(feats[f"decay_fail_{key}"], feats[f"decay_runs_{key}"], mu, cfg.prior_strength)
    elif cfg.estimator == "stickiness":
        p = stickiness_p(feats, stats, cfg.prior_strength)
    else:
        p = wilson_lower(feats["failure_count"], runs)

    conf = np.ones_like(runs) if cfg.estimator == "wilson" else runs / (runs + cfg.kappa)

    col = {"average": "mean_duration", "last": "last_duration", "ema": "ema_duration"}[cfg.duration]
    known = runs > 0
    cost = feats[col] + DURATION_OFFSET
    fill = float(np.median(cost[known])) if known.any() else 1.0
    cost = np.where(known, cost, fill)
    med = float(np.median(cost)) if len(cost) else 1.0
    return {"p": np.clip(p, 0.0, 1.0), "conf": conf, "cost": cost,
            "cost_norm": cost / med if med > 0 else np.ones_like(cost)}
