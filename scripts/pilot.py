"""Week-6 pilot and go/no-go #1 on one project (plan §3, week 6).

Steps, in this order (nothing from the eval split feeds a choice):

1. warm-up: start from ``configs/tuned/<project>-<dataset>.yaml`` (``tune_warmup.py``), then try the
   pre-defined variants of the plan, each over the full alpha grid, on the warm-up split only:
   tuned | gamma = 1 | ratio selection dF / c^gamma | ratio + gamma = 1 | Beta prior for new tests
   (only if the tuned estimator is not already Beta). The best (variant, alpha) is locked;
   then, for direction B, prop_eta x alpha on top of it (``paper/preregistration-B.md``);
2. eval: rank every TSR with the locked HC-FALCON, the pre-registered default configuration
   (``configs/default.yaml``), the ablations, rank fusion and the LRTS baselines;
3. paired tests on the eval split (Wilcoxon + Holm + Cliff's delta, median change);
4. diagnostics, reported but never used for choices: APFDc over alpha on the eval split, overhead
   relative to the test-suite duration, and why the semantic part helps or not (where FALCON puts the
   failing tests, how central they are, how long FALCON's first picks run).

    python scripts/pilot.py --project activemq --dataset deconf
    ->  results/pilot/<project>/*.csv, results/pilot/<project>/pilot.json, configs/tuned/<project>-<dataset>-locked.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from hcfalcon.hc_falcon import HCFalconPrioritizer, SimilarityProvider, config_from_yaml, make_method
from hcfalcon.lrts.embeddings import TSRVectors
from hcfalcon.lrts.loader import LRTSSource
from hcfalcon.prioritizers import LRTS_BASELINES, paper_name
from hcfalcon.rolling import run_rolling, summarize
from hcfalcon.stats import paired

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_experiment import load_config  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
COMPARE = ["FALCON", "History", "History+Cost", "RankBlend", "RRF", "cbt_LastFail_Asc", "hcbt_LastFail_Asc",
           "cbt_FailCount_Desc", "QTF", "Random"]


def warmup_variants(cfg):
    v = {"tuned": cfg, "gamma=1": replace(cfg, score=replace(cfg.score, gamma=1.0)),
         "ratio": replace(cfg, selection="ratio"),
         "ratio+gamma=1": replace(cfg, selection="ratio", score=replace(cfg.score, gamma=1.0))}
    if cfg.est.estimator != "beta":
        v["beta-prior"] = replace(cfg, est=replace(cfg.est, estimator="beta"))
    return v


def run_grid(src, provider, base_variants, alphas, dataset, warm, splits):
    cands, meta = [], {}
    for vname, vcfg in base_variants.items():
        for a in alphas:
            label = f"{vname}|alpha={a:g}"
            cands.append(HCFalconPrioritizer(replace(vcfg, alpha=float(a)), provider, name=label))
            meta[label] = (vname, float(a))
    raw = run_rolling(src, cands, datasets=(dataset,), seeds=1, warmup_fraction=warm, splits=splits)
    g = raw.groupby("method")["apfdc_u"].agg(["mean", "median", "size"])
    rows = [{"variant": meta[m][0], "alpha": meta[m][1], "apfdc_u_mean": g.loc[m, "mean"],
             "apfdc_u_median": g.loc[m, "median"], "n_tsr": int(g.loc[m, "size"])} for m in g.index]
    order = {k: i for i, k in enumerate(base_variants)}
    return pd.DataFrame(rows).sort_values(["variant", "alpha"], key=lambda s: s.map(order) if s.name == "variant" else s)


def run_prop_grid(src, provider, cfg, alphas, etas, dataset, warm, splits):
    """Direction B: prop_eta x alpha on top of a locked configuration."""
    cands, meta = [], {}
    for e in etas:
        for a in alphas:
            label = f"eta={e:g}|alpha={a:g}"
            c = replace(cfg, alpha=float(a), score=replace(cfg.score, prop_eta=float(e)))
            cands.append(HCFalconPrioritizer(c, provider, name=label))
            meta[label] = (float(e), float(a))
    raw = run_rolling(src, cands, datasets=(dataset,), seeds=1, warmup_fraction=warm, splits=splits)
    g = raw.groupby("method")["apfdc_u"].agg(["mean", "median", "size"])
    rows = [{"eta": meta[m][0], "alpha": meta[m][1], "apfdc_u_mean": g.loc[m, "mean"],
             "apfdc_u_median": g.loc[m, "median"], "n_tsr": int(g.loc[m, "size"])} for m in g.index]
    return pd.DataFrame(rows).sort_values(["eta", "alpha"]).reset_index(drop=True)


def diagnostics(src, provider, raw_eval_keys, cfg, dataset):
    """Where FALCON (alpha = 1) puts failing tests, their centrality, and the cost of its first picks."""
    falcon = HCFalconPrioritizer(replace(cfg, alpha=1.0, selection="gain"), provider, name="FALCON")
    rows = []

    def grab(row, method, seed, order, ctx):
        key = (row.pr_name, int(row.build_id), str(row.stage_id))
        run = src.read(row)
        excl = src.exclusions(row, dataset)
        failing = np.array([o == 1 and t not in excl for t, o in zip(run.names, run.outcome)])
        if not failing.any():
            return
        n = len(order)
        pos = np.empty(n)
        pos[order] = np.arange(n)
        sim, found = provider.get(ctx.key, ctx.names)
        cent = (sim.sum(1) - 1) / max(n - 1, 1)
        cost = falcon.last["est"]["cost"]
        k = max(1, int(round(0.1 * n)))
        rows.append({"pr_name": key[0], "build_id": key[1], "n_tests": n,
                     "fail_pos_pct": float(pos[failing].mean() / max(n - 1, 1)),
                     "fail_centrality_pct": float((cent[failing][:, None] > cent[None, :]).mean()),
                     "cost_first10pct_over_median": float(np.median(cost[order[:k]]) / np.median(cost)),
                     "time_share_first10pct": float(run.duration[order[:k]].sum() / max(run.duration.sum(), 1e-9))})

    run_rolling(src, [falcon], datasets=(dataset,), seeds=1, on_rank=grab, only_keys=raw_eval_keys)
    return pd.DataFrame(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--dataset", default="deconf")
    ap.add_argument("--config", type=Path, default=ROOT / "configs" / "default.yaml")
    ap.add_argument("--tuned", type=Path, default=None)
    args = ap.parse_args(argv)
    tuned_path = args.tuned or ROOT / "configs" / "tuned" / f"{args.project}-{args.dataset}.yaml"
    out = ROOT / "results" / "pilot" / args.project
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    default_raw = load_config(args.config)
    tuned_raw = load_config(args.config, tuned_path)
    warm = float(default_raw["protocol"]["warmup_fraction"])
    alphas = [float(a) for a in default_raw["tuning_grid"]["alpha"]]
    default_cfg, tuned_cfg = config_from_yaml(default_raw), config_from_yaml(tuned_raw)
    src = LRTSSource(args.project)
    provider = SimilarityProvider(TSRVectors(args.project), transform=tuned_cfg.sim_transform)

    # 1. warm-up: pre-defined variants x alpha
    variants = warmup_variants(tuned_cfg)
    wgrid = run_grid(src, provider, variants, alphas, args.dataset, warm, ("warmup",))
    wgrid.to_csv(out / "warmup_variants.csv", index=False)
    best = wgrid.loc[wgrid["apfdc_u_mean"].idxmax()]  # first max = earlier variant / smaller alpha
    locked = replace(variants[best["variant"]], alpha=float(best["alpha"]))
    print(f"[warm-up] best {best['variant']} alpha={best['alpha']:g} mean={best['apfdc_u_mean']:.4f} "
          f"(n={best['n_tsr']}); best alpha>0: "
          + str(wgrid[wgrid.alpha > 0].sort_values("apfdc_u_mean").iloc[-1][["variant", "alpha", "apfdc_u_mean"]].to_dict()))
    locked_doc = {"objective": {"alpha": locked.alpha, "cost_exponent": locked.score.gamma,
                                "selection": locked.selection, "rankblend_beta": locked.beta},
                  "history": {"estimator": locked.est.estimator, "decay_lambda": locked.est.decay_lambda,
                              "confidence_kappa": locked.est.kappa},
                  "locked_from": {"variant": best["variant"], "warmup_mean": float(best["apfdc_u_mean"]),
                                  "n_tsr": int(best["n_tsr"])}}
    with open(ROOT / "configs" / "tuned" / f"{args.project}-{args.dataset}-locked.yaml", "w", encoding="utf-8") as fh:
        yaml.safe_dump(locked_doc, fh, sort_keys=False)

    # 1b. warm-up, direction B (paper/preregistration-B.md): prop_eta x alpha on top of the locked variant
    etas = [float(e) for e in default_raw["tuning_grid"]["prop_eta"]]
    pgrid = run_prop_grid(src, provider, locked, alphas, etas, args.dataset, warm, ("warmup",))
    pgrid.to_csv(out / "warmup_prop.csv", index=False)
    bestp = pgrid.loc[pgrid["apfdc_u_mean"].idxmax()]  # first max = smaller eta, then smaller alpha
    locked_prop = replace(locked, alpha=float(bestp["alpha"]), score=replace(locked.score, prop_eta=float(bestp["eta"])))
    print(f"[warm-up, prop] best eta={bestp['eta']:g} alpha={bestp['alpha']:g} mean={bestp['apfdc_u_mean']:.4f}")
    prop_doc = {**locked_doc, "objective": {**locked_doc["objective"], "alpha": locked_prop.alpha,
                                            "prop_eta": locked_prop.score.prop_eta,
                                            "prop_lambda": locked_prop.prop_lambda,
                                            "prop_quantile": locked_prop.prop_quantile},
                "locked_from": {**locked_doc["locked_from"], "prop_warmup_mean": float(bestp["apfdc_u_mean"])}}
    with open(ROOT / "configs" / "tuned" / f"{args.project}-{args.dataset}-locked-prop.yaml", "w",
              encoding="utf-8") as fh:
        yaml.safe_dump(prop_doc, fh, sort_keys=False)

    # 2. eval: locked + pre-registered default + ablations + baselines
    prios = []
    for m in ["HC-FALCON", "FALCON", "FALCON-ratio", "History", "History+Cost", "FL+History", "HC-FALCON-noconf",
              "RankBlend", "RRF"]:
        prios.append(make_method(m, locked, provider))
    prios += [make_method(m, locked_prop, provider) for m in ("HC-FALCON-prop", "History+Cost+Prop")]
    p_def = make_method("HC-FALCON", default_cfg, provider)
    p_def.name = "HC-FALCON(default)"
    prios.append(p_def)
    prios += [make_method(m, locked, provider) for m in LRTS_BASELINES]
    raw = run_rolling(src, prios, datasets=("deconf", "all", "firstfail"), seeds=10, warmup_fraction=warm)
    raw.to_csv(ROOT / "results" / "raw" / f"{args.project}-pilot.csv.gz", index=False)
    summ = summarize(raw, metrics=("apfdc_u", "apfdc_s", "rapfdc_u", "ttff_pct", "det10_u", "det25_u", "det50_u"),
                     split="eval")
    summ.to_csv(out / "eval_summary.csv", index=False)

    # 3. paired tests on eval
    tests = pd.concat([paired(raw, m, COMPARE + (["HC-FALCON"] if m == "HC-FALCON-prop" else []), dataset=d)
                       .assign(dataset=d) for m in ("HC-FALCON", "HC-FALCON(default)", "HC-FALCON-prop")
                       for d in ("deconf", "all", "firstfail")], ignore_index=True)
    tests["baseline_name"] = tests["baseline"].map(paper_name)
    tests.to_csv(out / "paired_tests.csv", index=False)

    # 4. diagnostics (eval split; reported only)
    acurve = run_grid(src, provider, {"locked": locked}, alphas, args.dataset, warm, ("eval",))
    acurve.to_csv(out / "eval_alpha_curve.csv", index=False)
    ecurve = run_prop_grid(src, provider, locked_prop, [locked_prop.alpha], etas, args.dataset, warm, ("eval",))
    ecurve.to_csv(out / "eval_eta_curve.csv", index=False)
    ev = raw[(raw.split == "eval") & (raw.dataset == args.dataset)]
    keys = {(r.pr_name, int(r.build_id), str(r.stage)) for r in ev.itertuples()}
    diag = diagnostics(src, provider, keys, locked, args.dataset)
    diag.to_csv(out / "falcon_diagnostics.csv", index=False)
    tsr_dur = (src.index.assign(stage=src.index.stage_id.astype(str))
               .set_index(["pr_name", "build_id", "stage"])["test_suite_duration_s"])
    hc = ev[ev.method == "HC-FALCON(default)"].set_index(["pr_name", "build_id", "stage"])
    overhead = (hc["sim_time_s"] + hc["greedy_time_s"]) / tsr_dur.reindex(hc.index)

    summary = {
        "project": args.project, "dataset": args.dataset, "seconds": round(time.time() - t0, 1),
        "warmup_best": {"variant": best["variant"], "alpha": float(best["alpha"]),
                        "apfdc_u_mean": float(best["apfdc_u_mean"]), "n_tsr": int(best["n_tsr"])},
        "locked_config": asdict(locked),
        "warmup_prop_best": {"eta": float(bestp["eta"]), "alpha": float(bestp["alpha"]),
                             "apfdc_u_mean": float(bestp["apfdc_u_mean"])},
        "eval_n_tsr": int(ev.groupby("method").size().max()),
        "overhead_median_pct_of_tsr": float(overhead.median() * 100),
        "overhead_max_pct_of_tsr": float(overhead.max() * 100),
        "rank_time_median_s": float((hc["sim_time_s"] + hc["greedy_time_s"]).median()),
        "falcon_fail_pos_pct_mean": float(diag["fail_pos_pct"].mean()),
        "falcon_fail_centrality_pct_mean": float(diag["fail_centrality_pct"].mean()),
        "falcon_cost_first10pct_over_median": float(diag["cost_first10pct_over_median"].median()),
        "falcon_time_share_first10pct": float(diag["time_share_first10pct"].median()),
    }
    with open(out / "pilot.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, default=str)

    pd.set_option("display.width", 220)
    d = summ[summ.dataset == args.dataset].set_index("method")[["n_tsr", "apfdc_u", "apfdc_s", "ttff_pct", "det25_u"]]
    print(d.sort_values("apfdc_u", ascending=False).round(4).to_string())
    t = tests[tests.dataset == args.dataset][["method", "baseline_name", "n_tsr", "median_rel_change",
                                              "median_paired_diff", "wins", "losses", "p_holm", "cliffs_delta",
                                              "magnitude"]]
    print(t.round(4).to_string(index=False))
    print(acurve[["alpha", "apfdc_u_mean"]].round(4).to_string(index=False))
    print(ecurve[["eta", "alpha", "apfdc_u_mean"]].round(4).to_string(index=False))
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
