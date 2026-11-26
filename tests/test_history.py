import numpy as np
import pytest

from hcfalcon.history import FEATURES, HistoryStore, LeakageError


def lrts_reference(sequence):
    """Verbatim logic of LRTS evaluation/extract_hist_features.py: features emitted before each update."""
    history, emitted = {}, []
    for test, duration, outcome in sequence:
        if test not in history:
            history[test] = {"failure_count": 0, "last_failure": 0, "transition_count": 0, "last_transition": 0,
                             "average_duration": 0, "last_duration": 0, "run_count": 0, "last_outcome": 0}
        d = history[test]
        new_average = (d["average_duration"] * d["run_count"] + duration) / (d["run_count"] + 1)
        emitted.append((test, d["failure_count"], d["last_failure"], d["transition_count"], d["last_transition"],
                        round(d["average_duration"], 3), d["last_duration"]))
        if outcome == 1:
            d["failure_count"] += 1
        d["last_failure"] = 1 if outcome == 1 else d["last_failure"] + 1
        d["last_transition"] = d["last_transition"] + 1 if outcome == d["last_outcome"] else 1
        if outcome != d["last_outcome"]:
            d["transition_count"] += 1
        d["run_count"] += 1
        d["last_outcome"] = outcome
        d["last_duration"] = duration
        d["average_duration"] = new_average
    return emitted


def test_hand_sequence():
    h = HistoryStore()
    seq = [(0, 1.0), (1, 2.0), (1, 3.0), (0, 4.0)]
    expect = [  # fc, lf, tc, lt, avg, last, runs  (before each run)
        (0, 0, 0, 0, 0.0, 0.0, 0),
        (0, 1, 0, 1, 1.0, 1.0, 1),
        (1, 1, 1, 1, 1.5, 2.0, 2),
        (2, 1, 1, 2, 2.0, 3.0, 3),
        (2, 2, 2, 1, 2.5, 4.0, 4),
    ]
    for t, ((o, d), exp) in enumerate(zip(seq + [(0, 0.0)], expect)):
        f = h.features(["A"], as_of=t)
        assert tuple(f[k][0] for k in FEATURES) == pytest.approx(exp)
        assert f["known"][0] == (t > 0)
        if t < len(seq):
            h.update(["A"], [d], [o], timestamp=t)


def test_matches_lrts_reference_on_random_histories():
    rng = np.random.default_rng(1)
    pool = [f"T{i}" for i in range(12)]
    h, seq = HistoryStore(), []
    for b in range(80):
        names = list(rng.choice(pool, size=rng.integers(3, 10), replace=False))
        durs = np.round(rng.exponential(2.0, len(names)), 3)
        outs = (rng.random(len(names)) < 0.25).astype(int)
        f = h.features(names, as_of=b)
        got = [(t, *(f[k][i] for k in FEATURES[:-1])) for i, t in enumerate(names)]
        exp = lrts_reference(seq + list(zip(names, durs, outs)))[len(seq):]
        assert [g[0] for g in got] == [e[0] for e in exp]
        np.testing.assert_allclose(np.array([g[1:] for g in got], float), np.array([e[1:] for e in exp], float))
        h.update(names, durs, outs, timestamp=b)
        seq += list(zip(names, durs, outs))


def test_new_test_gets_zeros_and_average_is_rounded():
    h = HistoryStore()
    h.update(["A"], [1.0], [0], 0)
    h.update(["A"], [1.0005], [0], 1)
    f = h.features(["A", "NEW"], as_of=2)
    assert f["average_duration"][0] == 1.0  # (1 + 1.0005) / 2 = 1.00025 -> 1.0
    assert all(f[k][1] == 0 for k in FEATURES) and not f["known"][1]


def test_leakage_guards():
    h = HistoryStore()
    h.update(["A"], [1.0], [1], timestamp=10)
    with pytest.raises(LeakageError):
        h.features(["A"], as_of=10)  # a run at the ranking time itself
    with pytest.raises(LeakageError):
        h.update(["A"], [1.0], [0], timestamp=9)
    h.features(["A"], as_of=10.5)
