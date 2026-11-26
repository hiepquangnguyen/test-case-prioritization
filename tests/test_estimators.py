import numpy as np
import pytest

from hcfalcon.estimators import EstimatorConfig, beta_p, estimate, prior_mean, wilson_lower
from hcfalcon.history import HistoryStore
from hcfalcon.scoring import ScoreConfig, score


def store_with(seq):
    """seq: list of (names, durations, outcomes) in time order."""
    h = HistoryStore(decay_lambdas=(0.5, 0.9))
    for t, (n, d, o) in enumerate(seq):
        h.update(n, d, o, timestamp=t)
    return h


def test_history_decay_and_stickiness_counts():
    h = store_with([(["A", "B"], [1, 2], [1, 0]), (["A", "B"], [1, 2], [1, 0]), (["A", "B"], [3, 2], [0, 1])])
    f = h.features(["A", "B", "NEW"])
    # A: fail, fail, pass -> decayed fails with lambda 0.5: 1*0.25 + 1*0.5 + 0 = 0.75; runs 0.25+0.5+1
    assert f["decay_fail_0.5"][0] == pytest.approx(0.75) and f["decay_runs_0.5"][0] == pytest.approx(1.75)
    # A transitions: F->F (fail), F->P (pass) ; B: P->P (pass), P->F (fail)
    assert (f["n_after_fail"][0], f["f_after_fail"][0], f["n_after_pass"][0]) == (2, 1, 0)
    assert (f["n_after_pass"][1], f["f_after_pass"][1], f["n_after_fail"][1]) == (2, 1, 0)
    assert f["mean_duration"][0] == pytest.approx(5 / 3) and f["last_outcome"][1] == 1
    assert f["ema_duration"][0] == pytest.approx(0.3 * 3 + 0.7 * 1)
    assert not f["known"][2] and f["run_count"][2] == 0
    s = h.stats()
    assert (s["runs"], s["fails"], s["n_after_fail"], s["f_after_fail"], s["n_after_pass"], s["f_after_pass"]) == \
        (6, 3, 2, 1, 2, 1)


def test_beta_prior_and_wilson():
    assert beta_p([0], [0], mu=0.1, strength=2)[0] == pytest.approx(0.1)          # new test -> prior mean
    assert beta_p([3], [10], mu=0.1, strength=2)[0] == pytest.approx(3.2 / 12)
    assert wilson_lower([0], [10])[0] == 0.0 and wilson_lower([3], [0])[0] == 0.0
    assert wilson_lower([5], [10])[0] == pytest.approx(0.2366, abs=1e-4)
    assert wilson_lower([5], [10])[0] < wilson_lower([50], [100])[0] < 0.5       # shrinks with less data


@pytest.mark.parametrize("estimator", ["beta", "decay", "stickiness", "wilson"])
def test_estimate_ranges_and_new_tests(estimator):
    h = store_with([(["A", "B", "C"], [1, 10, 3], [1, 0, 0])] * 3 + [(["A", "B", "C"], [1, 10, 3], [0, 0, 1])])
    feats, stats = h.features(["A", "B", "C", "NEW"]), h.stats()
    est = estimate(feats, stats, EstimatorConfig(estimator=estimator, decay_lambda=0.9))
    assert ((est["p"] >= 0) & (est["p"] <= 1)).all() and (est["cost"] > 0).all()
    assert est["p"][0] > est["p"][1]            # A failed 3 of 4 times, B never
    if estimator == "wilson":
        assert (est["conf"] == 1).all()
    else:
        assert est["conf"][3] == 0 and est["conf"][0] == pytest.approx(4 / 7)
    assert est["cost"][3] == pytest.approx(np.median(est["cost"][:3]))  # new test: median known cost
    assert np.median(est["cost_norm"]) == pytest.approx(1.0)


def test_stickiness_uses_the_last_outcome():
    # transitions: after a pass 2 fails in 6 runs, after a fail 3 fails in 4 runs; last run failed
    h = store_with([(["A"], [1], [o]) for o in [0, 0, 0, 1, 1, 1, 0, 0, 0, 1, 1]])
    cfg = EstimatorConfig(estimator="stickiness", prior_strength=2.0)
    feats, stats = h.features(["A"]), h.stats()
    p_now = estimate(feats, stats, cfg)["p"][0]
    as_if_passed = dict(feats, last_outcome=np.zeros(1))
    p_if_pass = estimate(as_if_passed, stats, cfg)["p"][0]
    mu = 5 / 11
    pool_ff, pool_fp = (3 + 2 * mu) / (4 + 2), (2 + 2 * mu) / (6 + 2)  # pooled = this test's own counts here
    assert p_now == pytest.approx((3 + 2 * pool_ff) / (4 + 2))
    assert p_if_pass == pytest.approx((2 + 2 * pool_fp) / (6 + 2))
    assert p_now > p_if_pass


def test_decay_weighs_recent_failures_more():
    old = store_with([(["A"], [1], [1])] + [(["A"], [1], [0])] * 5)
    new = store_with([(["A"], [1], [0])] * 5 + [(["A"], [1], [1])])
    cfg = EstimatorConfig(estimator="decay", decay_lambda=0.5)
    p_old = estimate(old.features(["A"]), old.stats(), cfg)["p"][0]
    p_new = estimate(new.features(["A"]), new.stats(), cfg)["p"][0]
    assert p_new > p_old and prior_mean(old.stats()) == prior_mean(new.stats())


def test_score_variants():
    est = {"p": np.array([0.5, 0.5, 0.0]), "conf": np.array([1.0, 0.5, 1.0]),
           "cost_norm": np.array([4.0, 1.0, 1.0])}
    raw = score(est, ScoreConfig(q_norm="none"))
    assert raw == pytest.approx([0.5 / (2 + 1e-3), 0.25 / (1 + 1e-3), 0.0])
    assert score(est, ScoreConfig(q_norm="max")).max() == pytest.approx(1.0)
    assert score(est, ScoreConfig(use_cost=False, q_norm="none")) == pytest.approx([0.5, 0.25, 0.0])
    assert score(est, ScoreConfig(use_conf=False, use_cost=False, q_norm="none")) == pytest.approx([0.5, 0.5, 0.0])
    assert (score(est, ScoreConfig(gamma=1.0)) >= 0).all()
    with pytest.raises(ValueError):
        EstimatorConfig(estimator="nope")
