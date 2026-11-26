"""HC-FALCON and the methods built from the same ingredients.

    F_b(S) = alpha * FL_b(S) / |T_b| + (1 - alpha) * sum_{t in S} q_b(t)

ordered by lazy greedy (``hcfalcon.submodular``), with the deterministic tie-break of the protocol:
shorter estimated cost first, then name. ``q`` comes from ``hcfalcon.estimators`` + ``hcfalcon.scoring``;
the similarity is ``max(0, cos)`` of test-class vectors, with tests lacking source isolated.

Named methods (``make_method``):

======================  ====================================================================
FALCON                  alpha = 1 (semantic diversity only, same embeddings)
History                 alpha = 0, q = conf * p                     (ablation: history only)
History+Cost            alpha = 0, q = conf * p / (c^gamma + eps)   (ablation: history + cost)
FL+History              alpha from config, no cost in q
HC-FALCON               full model
HC-FALCON-noconf        full model with conf = 1
HC-FALCON-ratio         full model, cost-benefit selection dF / c^gamma (knapsack-style, no 1-1/e)
RankBlend               beta * rank_FALCON + (1 - beta) * rank_History+Cost
RRF                     reciprocal rank fusion of the same two rankings (k = 60)
<LRTS baseline id>      e.g. hcbt_LastFail_Asc (see ``hcfalcon.prioritizers``)
======================  ====================================================================
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field, replace

import numpy as np

from hcfalcon.estimators import EstimatorConfig, estimate
from hcfalcon.prioritizers import LRTS_BASELINES, HeuristicPrioritizer, RankContext
from hcfalcon.scoring import ScoreConfig, score
from hcfalcon.similarity import similarity_from_embeddings
from hcfalcon.submodular import GreedyResult, lazy_greedy

HC_METHODS = ("FALCON", "History", "History+Cost", "FL+History", "HC-FALCON", "HC-FALCON-noconf",
              "HC-FALCON-ratio", "RankBlend", "RRF")


@dataclass(frozen=True)
class HCConfig:
    alpha: float = 0.5
    est: EstimatorConfig = field(default_factory=EstimatorConfig)
    score: ScoreConfig = field(default_factory=ScoreConfig)
    selection: str = "gain"       # gain | ratio
    sim_transform: str = "clip"
    beta: float = 0.5             # RankBlend weight of the FALCON ranking
    rrf_k: float = 60.0

    def __post_init__(self):
        if not 0.0 <= self.alpha <= 1.0:
            raise ValueError("alpha must be in [0, 1]")
        if self.selection not in ("gain", "ratio"):
            raise ValueError(f"unknown selection {self.selection!r}")

    def digest(self) -> str:
        return hashlib.sha1(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()[:10]


def config_from_yaml(cfg: dict) -> HCConfig:
    """``configs/default.yaml`` -> HCConfig."""
    obj, hist, simc = cfg.get("objective", {}), cfg.get("history", {}), cfg.get("similarity", {})
    est = EstimatorConfig(
        estimator=hist.get("estimator", "decay"), decay_lambda=float(hist.get("decay_lambda", 0.9)),
        prior_strength=float(hist.get("beta_prior_strength", 2.0)), kappa=float(hist.get("confidence_kappa", 3.0)),
        duration=hist.get("duration", "average"), new_test_duration=hist.get("new_test_duration", "median"))
    sc = ScoreConfig(gamma=float(obj.get("cost_exponent", 0.5)), epsilon=float(obj.get("epsilon", 1e-3)),
                     q_norm=obj.get("q_norm", "max"))
    return HCConfig(alpha=float(obj.get("alpha", 0.5)), est=est, score=sc, selection=obj.get("selection", "gain"),
                    sim_transform=simc.get("transform", "clip"), beta=float(obj.get("rankblend_beta", 0.5)))


class SimilarityProvider:
    """Similarity matrix of the TSR being ranked, computed once and shared by all methods.

    ``vectors.get(pr_name, build_id, stage_id, names) -> (emb, found)`` (``lrts.embeddings.TSRVectors``).
    Also holds a per-TSR memo so that methods sharing a sub-ranking (RankBlend uses FALCON's) reuse it.
    """

    def __init__(self, vectors, transform: str = "clip"):
        self.vectors, self.transform = vectors, transform
        self._key, self._sim, self._found, self.memo = None, None, None, {}
        self.last_seconds = 0.0

    def _check(self, key, names):
        if key != self._key:
            self._key, self._sim, self._found, self.memo = key, None, None, {}
            self._names = names

    def get(self, key, names):
        self._check(key, names)
        if self._sim is None:
            t0 = time.perf_counter()
            emb, found = self.vectors.get(*key, names)
            self._sim = similarity_from_embeddings(emb, transform=self.transform, missing=~found)
            self._found = found
            self.last_seconds = time.perf_counter() - t0
        return self._sim, self._found

    def found(self, key, names):
        self._check(key, names)
        if self._found is None:
            _, self._found = self.vectors.get(*key, names)
        return self._found


def tie_rank(cost: np.ndarray, names: np.ndarray) -> np.ndarray:
    order = np.lexsort((names, cost))
    rank = np.empty(len(order), dtype=np.int64)
    rank[order] = np.arange(len(order))
    return rank


class HCFalconPrioritizer:
    """Lazy greedy on F_b. Keeps the last ranking's internals in ``last`` (for explanations)."""

    stochastic = False

    def __init__(self, cfg: HCConfig, provider: SimilarityProvider | None, name: str = "HC-FALCON",
                 explain_top: int = 0):
        if cfg.alpha > 0 and provider is None:
            raise ValueError("alpha > 0 needs a SimilarityProvider")
        self.cfg, self.provider, self.name, self.explain_top = cfg, provider, name, explain_top
        self._memo_key = ("hc", cfg.digest())
        self.last, self.last_stats = None, {}

    def rank(self, ctx: RankContext) -> np.ndarray:
        cfg, n = self.cfg, len(ctx.names)
        if self.provider is not None and not self.explain_top:
            hit = self.provider.memo.get(self._memo_key) if self.provider._key == ctx.key else None
            if hit is not None:
                self.last, self.last_stats = hit
                return self.last["result"].order

        est = estimate(ctx.features, ctx.history_stats, cfg.est)
        q = score(est, cfg.score)
        ties = tie_rank(est["cost"], ctx.names)
        denom = est["cost_norm"] ** cfg.score.gamma if cfg.selection == "ratio" else None
        t_sim = 0.0
        t0 = time.perf_counter()
        if cfg.alpha == 0.0:
            s = q if denom is None else q / denom
            order = np.lexsort((np.arange(n), ties, -s))
            res = GreedyResult(order=order, score=s[order], gain=q[order], fl_gain=np.zeros(n),
                               modular_gain=q[order], n_gain_evals=0, top_covered=[[] for _ in range(n)])
            found = self.provider.found(ctx.key, ctx.names) if self.provider is not None else np.ones(n, bool)
        else:
            sim, found = self.provider.get(ctx.key, ctx.names)
            t_sim = self.provider.last_seconds
            t0 = time.perf_counter()
            modular = (1.0 - cfg.alpha) * q if cfg.alpha < 1.0 else None
            res = lazy_greedy(sim, fl_weight=cfg.alpha / n, modular=modular, denom=denom, tie_rank=ties,
                              explain_top=self.explain_top)
        t_greedy = time.perf_counter() - t0
        self.last = {"result": res, "est": est, "q": q, "found": found, "names": ctx.names, "alpha": cfg.alpha,
                     "n": n}
        self.last_stats = {"sim_time_s": t_sim, "greedy_time_s": t_greedy, "n_gain_evals": res.n_gain_evals,
                           "emb_coverage": float(np.mean(found)) if n else float("nan")}
        if self.provider is not None:
            self.provider.memo[self._memo_key] = (self.last, self.last_stats)
        return res.order


class RankFusionPrioritizer:
    """RankBlend / RRF of FALCON (alpha = 1) and History+Cost (alpha = 0) rankings."""

    stochastic = False

    def __init__(self, cfg: HCConfig, provider: SimilarityProvider, mode: str = "blend", name: str | None = None):
        if mode not in ("blend", "rrf"):
            raise ValueError(f"unknown fusion mode {mode!r}")
        self.cfg, self.mode = cfg, mode
        self.name = name or ("RankBlend" if mode == "blend" else "RRF")
        self.falcon = HCFalconPrioritizer(replace(cfg, alpha=1.0), provider, name="FALCON")
        self.hist = HCFalconPrioritizer(replace(cfg, alpha=0.0), provider, name="History+Cost")
        self.last_stats = {}

    def rank(self, ctx: RankContext) -> np.ndarray:
        n = len(ctx.names)
        r1, r2 = np.empty(n), np.empty(n)
        r1[self.falcon.rank(ctx)] = np.arange(n)
        r2[self.hist.rank(ctx)] = np.arange(n)
        ties = tie_rank(self.hist.last["est"]["cost"], ctx.names)
        if self.mode == "blend":
            s = self.cfg.beta * r1 + (1.0 - self.cfg.beta) * r2
        else:
            s = -(1.0 / (self.cfg.rrf_k + r1 + 1) + 1.0 / (self.cfg.rrf_k + r2 + 1))
        self.last_stats = dict(self.falcon.last_stats)
        return np.lexsort((ties, s))


def make_method(name: str, cfg: HCConfig, provider: SimilarityProvider | None, explain_top: int = 0):
    """Prioritizer for a method name (see module docstring)."""
    if name in LRTS_BASELINES:
        return HeuristicPrioritizer(name, tie="random")
    variants = {
        "FALCON": replace(cfg, alpha=1.0),
        "History": replace(cfg, alpha=0.0, score=replace(cfg.score, use_cost=False)),
        "History+Cost": replace(cfg, alpha=0.0),
        "FL+History": replace(cfg, score=replace(cfg.score, use_cost=False)),
        "HC-FALCON": cfg,
        "HC-FALCON-noconf": replace(cfg, score=replace(cfg.score, use_conf=False)),
        "HC-FALCON-ratio": replace(cfg, selection="ratio"),
    }
    if name in variants:
        v = variants[name]
        return HCFalconPrioritizer(v, provider if v.alpha > 0 or provider else None, name=name,
                                   explain_top=explain_top)
    if name == "RankBlend":
        return RankFusionPrioritizer(cfg, provider, "blend")
    if name == "RRF":
        return RankFusionPrioritizer(cfg, provider, "rrf")
    raise ValueError(f"unknown method {name!r}; known: {HC_METHODS + tuple(LRTS_BASELINES)}")
