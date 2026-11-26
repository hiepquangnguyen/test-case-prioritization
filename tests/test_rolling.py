import numpy as np
import pandas as pd
import pytest

from hcfalcon.lrts.loader import Run
from hcfalcon.prioritizers import HeuristicPrioritizer
from hcfalcon.rolling import MemorySource, run_rolling, summarize


def run(names, outcome, duration=None):
    n = len(names)
    return Run(names=np.array(names), duration=np.asarray(duration if duration is not None else [1.0] * n, float),
               outcome=np.asarray(outcome, np.int8), last_outcome=np.zeros(n, np.int8))


def toy_source(excl=None):
    index = pd.DataFrame({"pr_name": ["P1", "P2", "P3", "P4"], "build_id": [1, 1, 1, 1],
                          "stage_id": ["s"] * 4, "build_timestamp": [10.0, 20.0, 20.0, 30.0]})
    runs = {
        ("P1", 1, "s"): run(["a", "b", "c"], [0, 1, 0]),
        ("P2", 1, "s"): run(["a", "b", "c"], [0, 1, 0]),
        ("P3", 1, "s"): run(["a", "b", "c"], [1, 0, 0]),
        ("P4", 1, "s"): run(["a", "b", "c", "d"], [0, 1, 0, 1]),
    }
    return MemorySource("toy", index, runs, excl)


def test_features_come_only_from_strictly_older_tsrs_and_ties_are_batched():
    seen = {}

    def spy(row, method, seed, order, ctx):
        seen[row.pr_name] = dict(zip(ctx.names, ctx.features["failure_count"]))

    run_rolling(toy_source(), [HeuristicPrioritizer("LastFail_Asc", tie="duration_name")],
                datasets=("all",), on_rank=spy)
    assert seen["P1"] == {"a": 0, "b": 0, "c": 0}
    assert seen["P2"] == seen["P3"] == {"a": 0, "b": 1, "c": 0}  # same timestamp: neither sees the other
    assert seen["P4"] == {"a": 1, "b": 2, "c": 0, "d": 0}


def test_rows_split_and_exclusions():
    excl = {"deconf": {("P3", 1, "s"): {"a"}}}  # P3's only failure is confounding
    raw = run_rolling(toy_source(excl), [HeuristicPrioritizer("QTF"), HeuristicPrioritizer("Random")],
                      datasets=("all", "deconf"), seeds=3)
    assert set(raw.groupby("dataset").pr_name.unique().map(len)) == {4, 3}
    assert "P3" not in set(raw[raw.dataset == "deconf"].pr_name)
    assert set(raw.split[raw.pr_name == "P1"]) == {"warmup"} and set(raw.split[raw.pr_name != "P1"]) == {"eval"}
    assert set(raw.n_seeds) == {3}
    p4 = raw[(raw.pr_name == "P4") & (raw.method == "QTF") & (raw.dataset == "all")].iloc[0]
    assert p4.n_new_tests == 1 and p4.n_tests == 4 and p4.n_fail == 2
    s = summarize(raw)
    assert set(s.columns) >= {"n_tsr", "apfdc_u", "apfdc_s", "apfd_u"}
    assert s.set_index(["dataset", "method"]).loc[("deconf", "QTF"), "n_tsr"] == 3


def test_lastfail_beats_random_on_persistent_failures():
    rng = np.random.default_rng(0)
    names = [f"T{i:02d}" for i in range(30)]
    index = pd.DataFrame({"pr_name": [f"P{i}" for i in range(40)], "build_id": 1, "stage_id": "s",
                          "build_timestamp": np.arange(40, dtype=float)})
    runs = {}
    for i in range(40):
        out = np.zeros(30, int)
        out[[3, 17]] = rng.random(2) < 0.8  # two chronically failing tests
        out[rng.integers(30)] |= rng.random() < 0.2
        runs[(f"P{i}", 1, "s")] = run(names, out, rng.exponential(1.0, 30))
    src = MemorySource("toy", index, runs)
    s = summarize(run_rolling(src, [HeuristicPrioritizer("LastFail_Asc"), HeuristicPrioritizer("Random")],
                              datasets=("all",), seeds=5)).set_index("method")
    assert s.loc["LastFail_Asc", "apfdc_u"] > s.loc["Random", "apfdc_u"] + 0.2


def test_random_streams_differ_per_tsr_and_are_reproducible():
    from hcfalcon.rolling import tsr_rng

    a1, a2 = tsr_rng(0, "PR-1", 1, "s").permutation(50), tsr_rng(0, "PR-1", 1, "s").permutation(50)
    b = tsr_rng(0, "PR-2", 1, "s").permutation(50)
    c = tsr_rng(1, "PR-1", 1, "s").permutation(50)
    assert (a1 == a2).all() and not (a1 == b).all() and not (a1 == c).all()


def test_duration_offset_is_applied():
    src = toy_source()
    raw = run_rolling(src, [HeuristicPrioritizer("QTF", tie="duration_name")], datasets=("all",))
    assert raw.loc[raw.pr_name == "P1", "total_time"].iloc[0] == pytest.approx(3.003)
