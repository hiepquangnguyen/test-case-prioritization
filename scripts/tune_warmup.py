"""Choose HC-FALCON hyper-parameters on the warm-up split only (first 20% of each stage's TSRs).

Staged search (``configs/default.yaml: tuning_grid``), each stage keeping the winners of the previous:
1. alpha;  2. p estimator (beta, decay lambda in {0.8, 0.9, 0.95}, stickiness);  3. kappa;  4. gamma;
then 5. the RankBlend weight beta with the chosen estimator, so the rank-mixing baseline gets the same
tuning budget. The criterion is mean APFDc-FFMapU over the warm-up TSRs scored on ``--dataset``;
ties keep the earlier (default-closer) value.

    python scripts/tune_warmup.py --project activemq --dataset deconf
    ->  configs/tuned/<project>-<dataset>.yaml, results/tuning/<project>-<dataset>.csv

The eval split is never ranked here.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from hcfalcon.hc_falcon import HCFalconPrioritizer, RankFusionPrioritizer, SimilarityProvider, config_from_yaml
from hcfalcon.lrts.embeddings import TSRVectors
from hcfalcon.lrts.loader import LRTSSource
from hcfalcon.rolling import run_rolling

ROOT = Path(__file__).resolve().parents[1]


def evaluate(src, provider, candidates, dataset, warmup):
    """candidates: {label: prioritizer} -> {label: (mean apfdc_u, n_tsr)} on the warm-up split."""
    for label, p in candidates.items():
        p.name = label
    raw = run_rolling(src, list(candidates.values()), datasets=(dataset,), seeds=1, warmup_fraction=warmup,
                      splits=("warmup",))
    g = raw.groupby("method")["apfdc_u"]
    return {label: (float(g.mean().get(label, np.nan)), int(g.size().get(label, 0))) for label in candidates}


def pick(results: dict, order: list):
    best = max(order, key=lambda k: (results[k][0], -order.index(k)))
    return best


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--dataset", default="deconf")
    ap.add_argument("--config", type=Path, default=ROOT / "configs" / "default.yaml")
    ap.add_argument("--index", choices=["artifact", "drive"], default="artifact")
    args = ap.parse_args(argv)

    with open(args.config, encoding="utf-8") as fh:
        raw_cfg = yaml.safe_load(fh)
    grid, warm = raw_cfg["tuning_grid"], float(raw_cfg["protocol"]["warmup_fraction"])
    cfg = config_from_yaml(raw_cfg)
    t0 = time.time()
    src = LRTSSource(args.project, source=args.index)
    provider = SimilarityProvider(TSRVectors(args.project), transform=cfg.sim_transform)
    log = []

    def stage(name, variants):
        nonlocal cfg
        cands = {label: HCFalconPrioritizer(c, provider) for label, c in variants.items()}
        res = evaluate(src, provider, cands, args.dataset, warm)
        best = pick(res, list(variants))
        for label, (m, n) in res.items():
            log.append({"stage": name, "candidate": label, "apfdc_u_warmup": m, "n_tsr": n, "chosen": label == best})
        cfg = variants[best]
        print(f"[{name}] " + "  ".join(f"{k}={v[0]:.4f}" for k, v in res.items()) + f"  -> {best}")

    stage("alpha", {f"alpha={a:g}": replace(cfg, alpha=float(a)) for a in grid["alpha"]})
    est_variants = {}
    for e in grid["estimator"]:
        e = dict(e)
        name = e.pop("name")
        label = name + (f"(lambda={e['decay_lambda']:g})" if "decay_lambda" in e else "")
        est_variants[label] = replace(cfg, est=replace(cfg.est, estimator=name, **e))
    stage("estimator", est_variants)
    stage("kappa", {f"kappa={k:g}": replace(cfg, est=replace(cfg.est, kappa=float(k))) for k in grid["confidence_kappa"]})
    stage("gamma", {f"gamma={g:g}": replace(cfg, score=replace(cfg.score, gamma=float(g))) for g in grid["cost_exponent"]})

    betas = [round(float(b), 2) for b in np.linspace(0, 1, 11)]
    fus = {f"beta={b:g}": RankFusionPrioritizer(replace(cfg, beta=b), provider, "blend") for b in betas}
    res = evaluate(src, provider, fus, args.dataset, warm)
    best_beta = float(pick(res, list(fus)).split("=")[1])
    for label, (m, n) in res.items():
        log.append({"stage": "rankblend_beta", "candidate": label, "apfdc_u_warmup": m, "n_tsr": n,
                    "chosen": label == f"beta={best_beta:g}"})
    print("[rankblend_beta] " + "  ".join(f"{k}={v[0]:.4f}" for k, v in res.items()) + f"  -> beta={best_beta:g}")

    tuned = {
        "objective": {"alpha": cfg.alpha, "cost_exponent": cfg.score.gamma, "rankblend_beta": best_beta},
        "history": {"estimator": cfg.est.estimator, "decay_lambda": cfg.est.decay_lambda,
                    "confidence_kappa": cfg.est.kappa},
        "tuned_on": {"project": args.project, "dataset": args.dataset, "split": "warmup",
                     "warmup_fraction": warm, "index": args.index,
                     "n_tsr": int(max(r["n_tsr"] for r in log))},
    }
    out_cfg = ROOT / "configs" / "tuned" / f"{args.project}-{args.dataset}.yaml"
    out_log = ROOT / "results" / "tuning" / f"{args.project}-{args.dataset}.csv"
    out_cfg.parent.mkdir(parents=True, exist_ok=True)
    out_log.parent.mkdir(parents=True, exist_ok=True)
    with open(out_cfg, "w", encoding="utf-8") as fh:
        yaml.safe_dump(tuned, fh, sort_keys=False)
    pd.DataFrame(log).to_csv(out_log, index=False)
    print(f"tuned config -> {out_cfg}  ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
