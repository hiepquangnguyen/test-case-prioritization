import zlib
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from hcfalcon.estimators import estimate
from hcfalcon.explain import explanation_table, render
from hcfalcon.hc_falcon import (HCConfig, RankFusionPrioritizer, SimilarityProvider, config_from_yaml, make_method,
                                tie_rank)
from hcfalcon.history import HistoryStore
from hcfalcon.lrts.loader import Run
from hcfalcon.prioritizers import RankContext
from hcfalcon.rolling import MemorySource, run_rolling
from hcfalcon.scoring import score
from hcfalcon.similarity import similarity_from_embeddings
from hcfalcon.submodular import lazy_greedy

ROOT = Path(__file__).resolve().parents[1]


class FakeVectors:
    """Deterministic 6-d vectors from the test name; names containing 'nosrc' have no source."""

    def get(self, pr, build, stage, names):
        emb = np.array([np.random.default_rng(zlib.crc32(n.encode())).normal(size=6) for n in names])
        found = np.array(["nosrc" not in n for n in names])
        emb[~found] = 0
        return emb, found


def context(n=12, seed=0):
    rng = np.random.default_rng(seed)
    names = np.array([f"T{i:02d}" for i in range(n - 1)] + ["X_nosrc"])
    h = HistoryStore()
    for t in range(15):
        h.update(names[:-2], rng.exponential(2.0, n - 2), (rng.random(n - 2) < 0.15).astype(int), timestamp=t)
    return RankContext(names=names, features=h.features(names, as_of=99), rng=np.random.default_rng(1),
                       key=("PR-1", 1, "s"), history_stats=h.stats())


def test_hc_falcon_is_lazy_greedy_on_the_documented_objective():
    ctx, cfg = context(), HCConfig(alpha=0.4)
    p = make_method("HC-FALCON", cfg, SimilarityProvider(FakeVectors()))
    order = p.rank(ctx)
    emb, found = FakeVectors().get(*ctx.key, ctx.names)
    sim = similarity_from_embeddings(emb, "clip", missing=~found)
    est = estimate(ctx.features, ctx.history_stats, cfg.est)
    q = score(est, cfg.score)
    ref = lazy_greedy(sim, fl_weight=0.4 / len(sim), modular=0.6 * q, tie_rank=tie_rank(est["cost"], ctx.names))
    assert order.tolist() == ref.order.tolist()
    assert p.last_stats["emb_coverage"] == pytest.approx(11 / 12)
    assert sim[-1, :-1].max() == 0 and sim[-1, -1] == 1  # test without source is isolated


def test_extremes_and_rank_fusion():
    ctx, cfg = context(seed=3), HCConfig(alpha=0.5)
    prov = SimilarityProvider(FakeVectors())
    falcon = make_method("FALCON", cfg, prov).rank(ctx)
    hist = make_method("History+Cost", cfg, prov).rank(ctx)
    est = estimate(ctx.features, ctx.history_stats, cfg.est)
    q = score(est, cfg.score)
    assert hist.tolist() == np.lexsort((np.arange(len(q)), tie_rank(est["cost"], ctx.names), -q)).tolist()
    emb, found = FakeVectors().get(*ctx.key, ctx.names)
    sim = similarity_from_embeddings(emb, "clip", missing=~found)
    assert falcon.tolist() == lazy_greedy(sim, fl_weight=1 / len(sim), tie_rank=tie_rank(est["cost"], ctx.names)).order.tolist()
    assert RankFusionPrioritizer(replace(cfg, beta=1.0), prov).rank(ctx).tolist() == falcon.tolist()
    assert RankFusionPrioritizer(replace(cfg, beta=0.0), prov).rank(ctx).tolist() == hist.tolist()
    rrf = make_method("RRF", cfg, prov).rank(ctx)
    assert sorted(rrf.tolist()) == list(range(len(q)))


def test_method_registry_and_yaml_config():
    with open(ROOT / "configs" / "default.yaml", encoding="utf-8") as fh:
        cfg = config_from_yaml(yaml.safe_load(fh))
    assert cfg.alpha == 0.5 and cfg.est.estimator == "decay" and cfg.score.gamma == 0.5 and cfg.score.q_norm == "max"
    prov = SimilarityProvider(FakeVectors())
    for name in ("FALCON", "History", "History+Cost", "FL+History", "HC-FALCON", "HC-FALCON-noconf",
                 "HC-FALCON-ratio", "RankBlend", "RRF", "hcbt_LastFail_Asc"):
        order = make_method(name, cfg, prov).rank(context())
        assert sorted(order.tolist()) == list(range(12)), name
    with pytest.raises(ValueError):
        make_method("Nope", cfg, prov)
    assert make_method("History", cfg, None).rank(context()) is not None  # alpha = 0 needs no embeddings
    with pytest.raises(ValueError):
        HCConfig(alpha=1.5)


def test_explanation_parts_add_up():
    ctx, cfg = context(), HCConfig(alpha=0.5)
    p = make_method("HC-FALCON", cfg, SimilarityProvider(FakeVectors()), explain_top=3)
    p.rank(ctx)
    t = explanation_table(p.last, k=5, outcome=np.zeros(12, int))
    assert list(t["position"]) == [1, 2, 3, 4, 5]
    assert np.allclose(t["semantic_part"] + t["history_cost_part"], t["gain"])
    assert (t["gain"].diff().dropna() <= 1e-12).all()  # greedy gains never increase
    assert "newly covers" in render(t) and not any(row["test"].rsplit(".")[-1] + " (" in row["covers"]
                                                   for row in t.to_dict("records"))


def test_rolling_end_to_end_with_hc_falcon():
    rng = np.random.default_rng(0)
    names = np.array([f"T{i:02d}" for i in range(20)])
    index = pd.DataFrame({"pr_name": [f"P{i}" for i in range(25)], "build_id": 1, "stage_id": "s",
                          "build_timestamp": np.arange(25, dtype=float)})
    runs = {}
    for i in range(25):
        out = (rng.random(20) < 0.05).astype(np.int8)
        out[[2, 9]] |= (rng.random(2) < 0.7).astype(np.int8)
        runs[(f"P{i}", 1, "s")] = Run(names=names, duration=rng.exponential(1, 20), outcome=out,
                                      last_outcome=np.zeros(20, np.int8))
    prov = SimilarityProvider(FakeVectors())
    prios = [make_method(m, HCConfig(alpha=0.3), prov) for m in ("HC-FALCON", "FALCON", "RankBlend")]
    raw = run_rolling(MemorySource("syn", index, runs), prios, datasets=("all",))
    assert {"sim_time_s", "greedy_time_s", "n_gain_evals", "emb_coverage"} <= set(raw.columns)
    s = raw.groupby("method").apfdc_u.mean()
    assert s["HC-FALCON"] > s["FALCON"]  # history finds the two chronic failures
    warm = run_rolling(MemorySource("syn", index, runs), prios[:1], datasets=("all",), splits=("warmup",))
    assert set(warm.split) == {"warmup"} and warm.position.max() < 5
