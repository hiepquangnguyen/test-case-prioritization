"""History/cost score q_b(t) >= 0, the modular part of the HC-FALCON objective.

    q = (conf * p + eta * s) / (c_norm ** gamma + eps)

``s`` is the semantic failure propagation score (``hcfalcon.propagation``, ``est["prop"]``); with
``prop_eta = 0`` (default) this is the original q = conf * p / (c_norm ** gamma + eps).
Switches give the ablations of ``topic1.md``: ``use_cost=False`` drops the denominator (history only),
``use_conf=False`` sets conf = 1. ``q_norm="max"`` divides by the largest q of the TSR so that q is in
[0, 1] like FL(S)/|T_b|, which keeps alpha comparable across TSRs and projects. Every variant keeps
q >= 0, so the objective stays monotone submodular.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ScoreConfig:
    use_cost: bool = True
    use_conf: bool = True
    gamma: float = 0.5
    epsilon: float = 1e-3
    q_norm: str = "max"  # max | none
    prop_eta: float = 0.0  # weight of the semantic failure propagation score

    def __post_init__(self):
        if self.q_norm not in ("max", "none"):
            raise ValueError(f"unknown q_norm {self.q_norm!r}")
        if self.gamma < 0 or self.epsilon <= 0 or self.prop_eta < 0:
            raise ValueError("need gamma >= 0, epsilon > 0 and prop_eta >= 0")


def score(est: dict, cfg: ScoreConfig) -> np.ndarray:
    q = est["p"] * (est["conf"] if cfg.use_conf else 1.0)
    if cfg.prop_eta > 0:
        if "prop" not in est:
            raise KeyError("prop_eta > 0 needs est['prop'] (hcfalcon.propagation)")
        q = q + cfg.prop_eta * est["prop"]
    if cfg.use_cost:
        q = q / (est["cost_norm"] ** cfg.gamma + cfg.epsilon)
    q = np.asarray(q, dtype=np.float64)
    if cfg.q_norm == "max":
        m = float(q.max()) if len(q) else 0.0
        if m > 0:
            q = q / m
    return np.clip(q, 0.0, None)
