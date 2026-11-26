import numpy as np
import pytest

from hcfalcon.hc_falcon import HCConfig, SimilarityProvider, make_method
from hcfalcon.propagation import neighbour_threshold, propagation_score
from hcfalcon.scoring import ScoreConfig, score

from test_hc_falcon import FakeVectors, context


def toy():
    # t0 ~ t1 (0.9), t2 ~ t3 (0.8), everything else 0.1; t4 has no source
    sim = np.full((5, 5), 0.1)
    sim[0, 1] = sim[1, 0] = 0.9
    sim[2, 3] = sim[3, 2] = 0.8
    np.fill_diagonal(sim, 1.0)
    sim[4, :] = sim[:, 4] = 0.0
    sim[4, 4] = 1.0
    found = np.array([True, True, True, True, False])
    return sim, found


def test_hand_example():
    sim, found = toy()
    feats = {"failure_count": np.array([0, 2, 0, 1, 3.0]), "last_failure": np.array([5, 1, 3, 4, 1.0])}
    tau = neighbour_threshold(sim, found, 0.5)          # off-diagonal among t0..t3: [.9 .1 .1 .1 .1 .8]
    assert tau == pytest.approx(0.1)
    s, src = propagation_score(sim, found, feats, lam=0.5, quantile=0.5)
    k = lambda x: (x - tau) / (1 - tau)  # noqa: E731
    assert s[0] == pytest.approx(k(0.9) * 1.0)          # neighbour t1 failed in its last run
    assert src[0] == 1
    assert s[2] == pytest.approx(k(0.8) * 0.5 ** 3)     # neighbour t3 failed 4 runs ago
    assert s[1] == 0 and s[3] == 0                      # own failures are not propagated; others are far
    assert s[4] == 0 and src[4] == -1                   # no source: nothing in, nothing out


def test_no_failures_or_no_neighbours_gives_zero():
    sim, found = toy()
    none = {"failure_count": np.zeros(5), "last_failure": np.zeros(5)}
    assert propagation_score(sim, found, none)[0].sum() == 0
    flat = np.ones((3, 3))
    feats = {"failure_count": np.array([1.0, 0, 0]), "last_failure": np.ones(3)}
    assert propagation_score(flat, np.ones(3, bool), feats)[0].sum() == 0  # tau = 1: nobody stands out


def test_score_adds_propagation_and_stays_nonnegative():
    est = {"p": np.array([0.0, 0.2]), "conf": np.array([0.0, 1.0]), "cost_norm": np.ones(2),
           "prop": np.array([0.5, 0.0])}
    q = score(est, ScoreConfig(prop_eta=0.4, q_norm="none", use_cost=False))
    assert q == pytest.approx([0.2, 0.2])  # a new test next to a fresh failure gets credit
    with pytest.raises(KeyError):
        score({k: v for k, v in est.items() if k != "prop"}, ScoreConfig(prop_eta=0.1))
    with pytest.raises(ValueError):
        ScoreConfig(prop_eta=-1)


def test_only_prop_methods_use_propagation():
    ctx = context(seed=2)
    prov = SimilarityProvider(FakeVectors())
    cfg = HCConfig(alpha=0.3)
    cfg_prop = HCConfig(alpha=0.3, score=ScoreConfig(prop_eta=5.0), prop_quantile=0.5)
    for name in ("HC-FALCON", "History+Cost", "FALCON", "RankBlend"):
        assert make_method(name, cfg, prov).rank(ctx).tolist() == make_method(name, cfg_prop, prov).rank(ctx).tolist()
    p = make_method("HC-FALCON-prop", cfg_prop, prov)
    order = p.rank(ctx)
    assert sorted(order.tolist()) == list(range(12)) and "prop" in p.last["est"]
    assert make_method("HC-FALCON-prop", cfg, prov).rank(ctx).tolist() == make_method("HC-FALCON", cfg, prov).rank(ctx).tolist()
