import numpy as np
import pandas as pd

from hcfalcon.leakage import check_prefix_invariance, leak_sensitivity
from hcfalcon.lrts.loader import Run
from hcfalcon.prioritizers import HeuristicPrioritizer
from hcfalcon.rolling import MemorySource


def synthetic_source(n_tsr=30, n_tests=25, seed=0):
    rng = np.random.default_rng(seed)
    names = np.array([f"T{i:02d}" for i in range(n_tests)])
    index = pd.DataFrame({"pr_name": [f"P{i}" for i in range(n_tsr)], "build_id": 1, "stage_id": "s",
                          "build_timestamp": np.arange(n_tsr, dtype=float)})
    runs = {}
    for i in range(n_tsr):
        out = (rng.random(n_tests) < 0.05).astype(np.int8)
        out[i % n_tests] = 1  # every TSR has a failure, at a moving position
        runs[(f"P{i}", 1, "s")] = Run(names=names, duration=rng.exponential(1.0, n_tests), outcome=out,
                                      last_outcome=np.zeros(n_tests, np.int8))
    return MemorySource("syn", index, runs)


class PeekingPrioritizer:
    """Cheats: ranks by failures summed over the whole dataset, future included."""

    name, stochastic = "Peeking", False

    def __init__(self, source):
        self.source = source

    def rank(self, ctx):
        total = sum(self.source.read(r).outcome.astype(float) for r in self.source.index.itertuples())
        return np.lexsort((ctx.names, -total))


def test_prefix_invariance_holds_for_baselines():
    src = synthetic_source()
    targets = [(f"P{i}", 1, "s") for i in (3, 12, 25)]
    for method in ("LastFail_Asc", "hcbt_LastFail_Asc", "Random"):
        res = check_prefix_invariance(src, HeuristicPrioritizer(method), targets)
        assert res.ranked.all() and res.same_when_dropped.all() and res.same_when_scrambled.all(), method


def test_prefix_invariance_catches_a_prioritizer_that_peeks():
    # passed as a factory, so it is rebuilt from each modified view of the data
    res = check_prefix_invariance(synthetic_source(), PeekingPrioritizer, [("P5", 1, "s"), ("P10", 1, "s")])
    assert res.ranked.all()
    assert not res.same_when_dropped.all() and not res.same_when_scrambled.all()


def test_deliberate_leak_is_visible_in_apfdc():
    out = leak_sensitivity(synthetic_source(), HeuristicPrioritizer("LastFail_Asc", tie="duration_name"))
    assert out["leaked"] > out["clean"] + 0.2
