"""Prioritization metrics: APFD, APFDc, relative APFDc, TTFF, detection within time budgets.

APFD / APFDc reproduce the LRTS artifact (``artifact/evaluation/eval_metric.py``,
``FaultDetectionMetric`` + ``compute_metrics``):

* tests whose failures are "confounding" for the chosen dataset version (flaky / frequently
  failing) are REMOVED from the ordered list before scoring, so neither their position nor
  their duration counts;
* ``"unique"`` mapping (FFMapU): every failing test is its own fault;
  ``"same"`` mapping (FFMapS): all failures in one test-suite run are a single fault.

LRTS adds 0.001 s to every duration when loading (Maven/Gradle report 0.000 s); the LRTS loader
does that, not this module.

Deliberate deviation: LRTS's ``other_metric()`` returns as "TTFF" only the duration of the first
failing test. Here TTFF is the cumulative time from the start of the run until the first
failing test finishes, which is what "time to first failure" means.

rAPFDc = APFDc / APFDc of the oracle order (failing tests first, shortest first; that order is
optimal for both mappings).
"""

from __future__ import annotations

import numpy as np

MAPPINGS = ("unique", "same")
DEFAULT_BUDGETS = (0.10, 0.25, 0.50)


def _arrays(durations, failed, exclude=None):
    d = np.asarray(durations, dtype=np.float64)
    f = np.asarray(failed, dtype=bool)
    if d.shape != f.shape or d.ndim != 1:
        raise ValueError("durations and failed must be 1-D arrays of equal length")
    if exclude is not None:
        keep = ~np.asarray(exclude, dtype=bool)
        d, f = d[keep], f[keep]
    if (d < 0).any():
        raise ValueError("durations must be >= 0")
    return d, f


def _fault_positions(f: np.ndarray, mapping: str) -> np.ndarray:
    """0-based positions of the tests that reveal each fault."""
    pos = np.flatnonzero(f)
    if mapping == "unique":
        return pos
    if mapping == "same":
        return pos[:1]
    raise ValueError(f"unknown mapping {mapping!r}; expected one of {MAPPINGS}")


def apfd(failed, mapping: str = "unique", exclude=None) -> float:
    _, f = _arrays(np.zeros(len(failed)), failed, exclude)
    pos = _fault_positions(f, mapping)
    if len(pos) == 0:
        return float("nan")
    n, m = len(f), len(pos)
    return float(1.0 - (pos + 1).sum() / (n * m) + 1.0 / (2 * n))


def apfdc(durations, failed, mapping: str = "unique", exclude=None) -> float:
    d, f = _arrays(durations, failed, exclude)
    pos = _fault_positions(f, mapping)
    if len(pos) == 0:
        return float("nan")
    total = d.sum()
    if total <= 0:
        return float("nan")
    suffix = np.cumsum(d[::-1])[::-1]          # suffix[i] = sum(d[i:])
    costs = suffix[pos] - d[pos] / 2.0
    return float(costs.sum() / (len(pos) * total))


def oracle_order(durations, failed) -> np.ndarray:
    """Indices: failing tests first by ascending duration, then passing tests (stable)."""
    d = np.asarray(durations, dtype=np.float64)
    f = np.asarray(failed, dtype=bool)
    fail_idx = np.flatnonzero(f)
    fail_idx = fail_idx[np.argsort(d[fail_idx], kind="stable")]
    return np.concatenate([fail_idx, np.flatnonzero(~f)])


def rapfdc(durations, failed, mapping: str = "unique", exclude=None) -> float:
    d, f = _arrays(durations, failed, exclude)
    value = apfdc(d, f, mapping)
    if np.isnan(value):
        return value
    opt = oracle_order(d, f)
    return float(value / apfdc(d[opt], f[opt], mapping))


def ttff(durations, failed, exclude=None) -> tuple[float, float]:
    """(seconds, fraction of total run time) until the first failing test finishes."""
    d, f = _arrays(durations, failed, exclude)
    pos = np.flatnonzero(f)
    if len(pos) == 0:
        return float("nan"), float("nan")
    seconds = float(d[: pos[0] + 1].sum())
    total = float(d.sum())
    return seconds, (seconds / total if total > 0 else float("nan"))


def detected_within(durations, failed, fraction: float, mapping: str = "unique", exclude=None) -> float:
    """Share of faults revealed once ``fraction`` of the total run time has elapsed."""
    d, f = _arrays(durations, failed, exclude)
    pos = _fault_positions(f, mapping)
    if len(pos) == 0:
        return float("nan")
    finish = np.cumsum(d)
    limit = fraction * finish[-1]
    return float(np.mean(finish[pos] <= limit + 1e-12))


def evaluate_order(durations, failed, exclude=None, budgets=DEFAULT_BUDGETS) -> dict:
    """All metrics for one prioritized test-suite run (inputs already in priority order)."""
    d, f = _arrays(durations, failed, exclude)
    out = {
        "n_tests": int(len(d)),
        "n_fail": int(f.sum()),
        "total_time": float(d.sum()),
    }
    for m, tag in (("unique", "u"), ("same", "s")):
        out[f"apfd_{tag}"] = apfd(f, m)
        out[f"apfdc_{tag}"] = apfdc(d, f, m)
        out[f"rapfdc_{tag}"] = rapfdc(d, f, m)
    out["ttff_s"], out["ttff_pct"] = ttff(d, f)
    for b in budgets:
        out[f"det{int(round(b * 100))}_u"] = detected_within(d, f, b, "unique")
    return out
