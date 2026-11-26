import itertools
import math

import numpy as np
import pytest

from hcfalcon.similarity import isolate, similarity_from_embeddings
from hcfalcon.submodular import fl_value, lazy_greedy, objective, standard_greedy

# FALCON paper, Example 1 (Sec. IV-A), scaled by 10 so every gain is an exact integer and the
# step-2 tie between t3 and t4 is a true tie (broken by index -> t3, as in the paper).
FALCON_SIM = np.array(
    [
        [10, 9, 2, 1],
        [9, 10, 3, 2],
        [2, 3, 10, 8],
        [1, 2, 8, 10],
    ],
    dtype=np.float64,
)


def test_falcon_paper_example_order_and_gains():
    res = lazy_greedy(FALCON_SIM)
    assert res.order.tolist() == [1, 2, 3, 0]          # <t2, t3, t4, t1>
    assert res.fl_gain.tolist() == [24, 13, 2, 1]       # 2.4, 1.3, 0.2, 0.1 in the paper


def test_hcfalcon_worked_example_from_analysis_doc():
    # phan-tich-de-tai-1.md, Sec. 5.4: alpha = 0.5, q = (0, 0.04, 0, 0.3) -> <t4, t2, t3, t1>
    alpha, n = 0.5, 4
    q = np.array([0.0, 0.04, 0.0, 0.30])
    sim = FALCON_SIM / 10.0
    for algo in (lazy_greedy, standard_greedy):
        res = algo(sim, fl_weight=alpha / n, modular=(1 - alpha) * q)
        assert res.order.tolist() == [3, 1, 2, 0]
        np.testing.assert_allclose(res.gain[:3], [0.4125, 0.22, 0.025], atol=1e-12)


def _random_instance(rng):
    n = int(rng.integers(2, 40))
    kind = rng.integers(0, 3)
    if kind == 0:      # cosine of random embeddings, clipped
        sim = similarity_from_embeddings(rng.normal(size=(n, 8)), "clip", dtype=np.float64)
    elif kind == 1:    # many exact ties: small integer similarities
        sim = rng.integers(0, 4, size=(n, n)).astype(np.float64)
        np.fill_diagonal(sim, 4.0)
    else:              # duplicated tests (identical rows/columns)
        base = rng.normal(size=(max(1, n // 3), 6))
        emb = base[rng.integers(0, len(base), size=n)]
        sim = similarity_from_embeddings(emb, "clip", dtype=np.float64)
    modular = None
    if rng.random() < 0.7:
        modular = rng.random(n) * rng.choice([0.0, 0.1, 1.0, 10.0])
        modular[rng.random(n) < 0.4] = 0.0
    denom = rng.uniform(0.1, 5.0, size=n) if rng.random() < 0.3 else None
    tie_rank = rng.permutation(n) if rng.random() < 0.5 else None
    fl_weight = float(rng.choice([1.0, 1.0 / n, 0.0, 0.37]))
    return dict(sim=sim, fl_weight=fl_weight, modular=modular, denom=denom, tie_rank=tie_rank)


def test_lazy_equals_standard_on_random_instances():
    rng = np.random.default_rng(20261126)
    for _ in range(200):
        inst = _random_instance(rng)
        lazy = lazy_greedy(**inst)
        std = standard_greedy(**inst)
        assert lazy.order.tolist() == std.order.tolist()
        np.testing.assert_allclose(lazy.gain, std.gain, rtol=0, atol=1e-12)
        assert lazy.n_gain_evals <= std.n_gain_evals


def test_prefix_of_full_order_equals_budgeted_greedy():
    rng = np.random.default_rng(7)
    for _ in range(30):
        inst = _random_instance(rng)
        full = lazy_greedy(**inst).order
        k = int(rng.integers(1, len(full) + 1))
        assert lazy_greedy(budget=k, **inst).order.tolist() == full[:k].tolist()


def test_monotone_and_submodular_numerically():
    rng = np.random.default_rng(11)
    for _ in range(300):
        n = int(rng.integers(3, 15))
        sim = similarity_from_embeddings(rng.normal(size=(n, 5)), "clip", dtype=np.float64)
        w, mod = float(rng.random()), rng.random(n)
        big = set(np.flatnonzero(rng.random(n) < 0.5).tolist())
        small = {s for s in big if rng.random() < 0.5}
        outside = [x for x in range(n) if x not in big]
        if not outside:
            continue
        x = int(rng.choice(outside))
        f = lambda s: objective(sim, s, w, mod)  # noqa: E731
        assert f(small) <= f(big) + 1e-12                                       # monotone
        assert f(small | {x}) - f(small) >= f(big | {x}) - f(big) - 1e-12        # submodular


def test_greedy_meets_one_minus_one_over_e_bound():
    rng = np.random.default_rng(3)
    for _ in range(40):
        n = int(rng.integers(3, 9))
        sim = similarity_from_embeddings(rng.normal(size=(n, 4)), "clip", dtype=np.float64)
        w, mod = 1.0 / n, rng.random(n) * 0.3
        order = lazy_greedy(sim, fl_weight=w, modular=mod).order.tolist()
        for k in range(1, n + 1):
            opt = max(objective(sim, s, w, mod) for s in itertools.combinations(range(n), k))
            assert objective(sim, order[:k], w, mod) >= (1 - 1 / math.e) * opt - 1e-12


def test_lazy_saves_gain_evaluations_on_clustered_data():
    rng = np.random.default_rng(5)
    centers = rng.normal(size=(5, 16))
    emb = centers[rng.integers(0, 5, size=150)] + 0.05 * rng.normal(size=(150, 16))
    sim = similarity_from_embeddings(emb, "clip")
    lazy, std = lazy_greedy(sim), standard_greedy(sim)
    assert lazy.order.tolist() == std.order.tolist()
    assert lazy.n_gain_evals < std.n_gain_evals / 5


def test_fl_value_and_empty_set():
    assert fl_value(FALCON_SIM, []) == 0.0
    assert fl_value(FALCON_SIM, [1]) == 24.0
    assert fl_value(FALCON_SIM, [0, 1, 2, 3]) == 40.0


def test_similarity_transforms_are_non_negative():
    emb = np.array([[1.0, 0.0], [-1.0, 0.0], [0.0, 1.0]])
    clip = similarity_from_embeddings(emb, "clip", dtype=np.float64)
    shift = similarity_from_embeddings(emb, "shift", dtype=np.float64)
    assert clip.min() >= 0 and clip[0, 1] == 0.0
    assert shift.min() >= 0 and shift[0, 1] == pytest.approx(0.0) and shift[0, 2] == pytest.approx(0.5)
    np.testing.assert_allclose(np.diag(clip), 1.0)


def test_isolate_missing_embeddings():
    sim = np.full((3, 3), 0.5)
    out = isolate(sim, np.array([False, True, False]))
    assert out[1].tolist() == [0.0, 1.0, 0.0] and out[:, 1].tolist() == [0.0, 1.0, 0.0]
    assert out[0, 2] == 0.5


def test_explain_top_reports_newly_covered_tests():
    res = lazy_greedy(FALCON_SIM, explain_top=2)
    first = res.top_covered[0]          # picking t2 first: covers t2 (10) and t1 (9) the most
    assert [u for u, _ in first] == [1, 0]
    assert all(imp > 0 for step in res.top_covered for _, imp in step)


def test_input_validation():
    with pytest.raises(ValueError):
        lazy_greedy(FALCON_SIM, modular=np.array([0.0, -1.0, 0.0, 0.0]))
    with pytest.raises(ValueError):
        lazy_greedy(FALCON_SIM, denom=np.array([1.0, 0.0, 1.0, 1.0]))
    with pytest.raises(ValueError):
        lazy_greedy(np.ones((2, 3)))
