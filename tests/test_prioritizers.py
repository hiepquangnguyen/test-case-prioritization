import numpy as np
import pytest

from hcfalcon.prioritizers import LRTS_BASELINES, HeuristicPrioritizer, RankContext, paper_name


def ctx(seed=0):
    names = np.array(["a", "b", "c", "d"])
    f = {
        "last_duration": np.array([3.0, 1.0, 2.0, 0.0]),
        "average_duration": np.array([2.0, 1.5, 2.5, 0.0]),
        "failure_count": np.array([0.0, 2.0, 1.0, 0.0]),
        "last_failure": np.array([5.0, 1.0, 2.0, 0.0]),
        "transition_count": np.array([0.0, 3.0, 1.0, 0.0]),
        "last_transition": np.array([5.0, 1.0, 3.0, 0.0]),
        "known": np.array([True, True, True, False]),
    }
    return RankContext(names=names, features=f, rng=np.random.default_rng(seed))


@pytest.mark.parametrize("method, expected", [
    ("QTF", [3, 1, 2, 0]),                 # new test (0 s) first, then by last duration
    ("QTF(Avg)", [3, 1, 0, 2]),
    ("LastFail_Asc", [3, 1, 2, 0]),        # new test has last_failure 0 -> first, as in LRTS
    ("cbt_FailCount_Desc", [1, 3, 2, 0]),  # 1/(fc+eps) * (ld+eps): b .5, d 1, c 2, a 3e6
    ("hcbt_LastFail_Asc", [3, 1, 2, 0]),   # (lf+eps) * (ld+eps)/(fc+eps)
    ("TransCount_Desc", [1, 2]),           # a and d tie at 1/eps: only the head is fixed
])
def test_lrts_formulas(method, expected):
    order = HeuristicPrioritizer(method).rank(ctx())
    assert sorted(order.tolist()) == [0, 1, 2, 3]
    assert order[:len(expected)].tolist() == expected


def test_random_tie_break_is_seeded_and_deterministic_tie_is_duration_then_name():
    p = HeuristicPrioritizer("FailCount_Desc")
    assert p.rank(ctx(7)).tolist() == p.rank(ctx(7)).tolist()
    tails = {tuple(p.rank(ctx(s))[2:]) for s in range(20)}
    assert tails == {(0, 3), (3, 0)}  # a and d tie; both orders occur
    q = HeuristicPrioritizer("FailCount_Desc", tie="duration_name")
    assert not q.stochastic and q.rank(ctx(1)).tolist() == [1, 2, 3, 0]  # d (0 s) before a (3 s)


def test_random_is_a_permutation_and_names():
    assert sorted(HeuristicPrioritizer("Random").rank(ctx(3)).tolist()) == [0, 1, 2, 3]
    assert [paper_name(m) for m in LRTS_BASELINES][-3:] == ["LatestFail+CC", "MostFail+CC", "LatestFail+CCH"]
    for bad in ("cbt_Random", "Nope", "hcbt_Nope"):
        with pytest.raises(ValueError):
            HeuristicPrioritizer(bad)
