import math
import sys
from pathlib import Path

import numpy as np
import pytest

from hcfalcon import metrics as M

# Example from the LRTS artifact (eval_metric.test_cases): a(1,F) b(2) c(4) d(3,F) e(2)
DUR = [1.0, 2.0, 4.0, 3.0, 2.0]
FAIL = [True, False, False, True, False]


def test_hand_computed_values():
    assert M.apfd(FAIL, "unique") == pytest.approx(0.6)        # 1 - (1+4)/(5*2) + 1/10
    assert M.apfd(FAIL, "same") == pytest.approx(0.9)          # 1 - 1/5 + 1/10
    assert M.apfdc(DUR, FAIL, "unique") == pytest.approx(15 / 24)   # (11.5 + 3.5) / (2*12)
    assert M.apfdc(DUR, FAIL, "same") == pytest.approx(11.5 / 12)
    assert M.ttff(DUR, FAIL) == pytest.approx((1.0, 1 / 12))
    assert M.detected_within(DUR, FAIL, 0.5) == pytest.approx(0.5)   # finish 1 <= 6, 10 > 6
    assert M.detected_within(DUR, FAIL, 1.0) == pytest.approx(1.0)
    # oracle: a(1), d(3) first -> (11.5 + 9.5) / 24
    assert M.rapfdc(DUR, FAIL, "unique") == pytest.approx((15 / 24) / (21 / 24))
    assert M.rapfdc(DUR, FAIL, "same") == pytest.approx(1.0)


def test_ttff_is_cumulative_not_lrts_first_failure_duration():
    # failing test at position 3 (0-based 2): TTFF = 5 + 1 + 2, not just 2
    seconds, frac = M.ttff([5.0, 1.0, 2.0, 2.0], [False, False, True, False])
    assert seconds == 8.0 and frac == pytest.approx(0.8)


def test_no_failure_gives_nan():
    for value in (
        M.apfd([False, False]),
        M.apfdc([1.0, 2.0], [False, False]),
        M.rapfdc([1.0, 2.0], [False, False]),
        M.ttff([1.0, 2.0], [False, False])[0],
    ):
        assert math.isnan(value)


def test_exclude_removes_confounding_tests_entirely():
    exclude = [False, False, False, True, False]   # d is a confounding failure
    # remaining a(1,F) b(2) c(4) e(2): total 9, only a fails at position 1
    assert M.apfdc(DUR, FAIL, "unique", exclude) == pytest.approx((9 - 0.5) / 9)
    assert M.apfd(FAIL, "unique", exclude) == pytest.approx(1 - 1 / 4 + 1 / 8)


def test_oracle_order_scores_one_and_beats_random_orders():
    rng = np.random.default_rng(0)
    for _ in range(200):
        n = int(rng.integers(2, 30))
        d = rng.exponential(10.0, size=n) + 0.001
        f = rng.random(n) < 0.2
        if not f.any():
            f[rng.integers(n)] = True
        opt = M.oracle_order(d, f)
        for m in M.MAPPINGS:
            assert M.rapfdc(d[opt], f[opt], m) == pytest.approx(1.0)
            perm = rng.permutation(n)
            assert M.apfdc(d[perm], f[perm], m) <= M.apfdc(d[opt], f[opt], m) + 1e-12


def _lrts_reference(durations, failed, mapping):
    """Line-by-line restatement of LRTS FaultDetectionMetric.APFD/APFDc (python sums)."""
    tfis = [i + 1 for i, x in enumerate(failed) if x]
    if mapping == "same":
        tfis = tfis[:1]
    num_bugs = sum(failed) if mapping == "unique" else 1
    n = len(failed)
    a = 1 - sum(tfis) / (num_bugs * n) + 1 / (2 * n)
    costs = [sum(durations[p - 1:]) - durations[p - 1] / 2 for p in tfis]
    c = sum(costs) / (num_bugs * sum(durations))
    return a, c


def test_parity_with_lrts_formulas_on_random_runs():
    rng = np.random.default_rng(42)
    for _ in range(500):
        n = int(rng.integers(1, 200))
        d = (rng.exponential(5.0, size=n) + 0.001).tolist()
        f = (rng.random(n) < rng.uniform(0.01, 0.3)).tolist()
        if not any(f):
            f[int(rng.integers(n))] = True
        for m in M.MAPPINGS:
            ref_apfd, ref_apfdc = _lrts_reference(d, f, m)
            assert M.apfd(f, m) == pytest.approx(ref_apfd, rel=1e-12, abs=1e-12)
            assert M.apfdc(d, f, m) == pytest.approx(ref_apfdc, rel=1e-9, abs=1e-12)


LRTS_EVAL = Path(__file__).resolve().parents[1] / "external" / "LRTS" / "artifact" / "evaluation"


@pytest.mark.external
@pytest.mark.skipif(not (LRTS_EVAL / "eval_metric.py").exists(), reason="LRTS artifact not cloned")
def test_parity_with_lrts_artifact_code():
    sys.path.insert(0, str(LRTS_EVAL.parent))
    sys.path.insert(0, str(LRTS_EVAL))
    import eval_metric  # noqa: E402  (LRTS code)
    import eval_utils  # noqa: E402

    rng = np.random.default_rng(1)
    for _ in range(200):
        n = int(rng.integers(1, 150))
        d = rng.exponential(5.0, size=n) + 0.001
        f = rng.random(n) < 0.15
        if not f.any():
            f[rng.integers(n)] = True
        tests = [eval_utils.Test(f"T{i}", float(d[i]), int(f[i]), 0) for i in range(n)]
        ref = eval_metric.compute_metrics(tests)
        for m, tag in (("uniqueBug", "unique"), ("sameBug", "same")):
            assert M.apfd(f, tag) == pytest.approx(ref[f"APFD_{m}"], abs=1e-12)
            assert M.apfdc(d, f, tag) == pytest.approx(ref[f"APFDc_{m}"], rel=1e-9)


def test_evaluate_order_keys():
    out = M.evaluate_order(DUR, FAIL)
    for key in ("apfd_u", "apfd_s", "apfdc_u", "apfdc_s", "rapfdc_u", "ttff_s", "ttff_pct",
                "det10_u", "det25_u", "det50_u", "n_tests", "n_fail", "total_time"):
        assert key in out
    assert out["n_fail"] == 2 and out["total_time"] == 12.0
