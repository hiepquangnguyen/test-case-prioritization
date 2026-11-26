"""Week-3 checkpoint: our LRTS baselines must reproduce LRTS ``eval_outcome`` within 0.01 APFDc.

Three levels of agreement, per project:
1. filter labels: per-TSR failure counts after each filter vs ``metadata/dataset_filter.csv``;
2. TSR sets: the scored TSRs of each dataset version equal those in ``eval_outcome``;
3. metrics: mean APFDc-FFMapU / -FFMapS / APFD per (dataset, technique), and the mean absolute per-TSR
   difference (both sides averaged over 10 random tie-breaks, so small per-TSR noise is expected).

Verdict per (dataset, technique), TSR sets must be identical in all cases:
- ``match``: |mean diff| <= 0.01;
- ``noise``: |mean diff| > 0.01 but <= 3 standard errors of the per-TSR differences. This happens when
  random tie-breaking decides most of the order (Random; MostFail / MostTrans on FirstFail, where every
  first failure has failure_count 0), so LRTS's own 10-seed mean is uncertain by more than 0.01;
- ``lrts-leak``: QTF(Avg) only. LRTS's published QTF(Avg) results use an average duration that includes
  the *current* run (the repository code does not; the outcomes were likely produced by an older
  version). We keep the clean definition and confirm the explanation by recomputing LRTS's leaky variant,
  which must match ``eval_outcome`` per TSR (mean |diff| < 0.002);
- ``FAIL``: anything else.
Per-TSR values of LRTS are rounded to 3 decimals, which alone gives differences up to 0.0005.

    python scripts/check_lrts_parity.py --projects activemq
    ->  results/parity/<project>.csv, results/raw/parity-<project>.csv.gz
"""

import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from hcfalcon.lrts.filters import validate_against_artifact
from hcfalcon.lrts.loader import ARTIFACT, DATASET_FOLDERS, LRTSSource, load_filter_index
from hcfalcon.metrics import apfdc
from hcfalcon.prioritizers import EPS, LRTS_BASELINES, HeuristicPrioritizer, paper_name
from hcfalcon.rolling import DURATION_OFFSET, ordered_stage_index, run_rolling, scored_on, tsr_rng

ROOT = Path(__file__).resolve().parents[1]
OUTCOME = ARTIFACT / "evaluation" / "eval_outcome"
TOL = 0.01
LRTS_METRICS = {"apfdc_u": "APFDc_uniqueBug", "apfdc_s": "APFDc_sameBug", "apfd_u": "APFD_uniqueBug"}


def lrts_per_tsr(project, dataset, method):
    path = OUTCOME / DATASET_FOLDERS[dataset] / project / f"{method}.csv.zip"
    df = pd.read_csv(path)
    df["build_id"] = df["build_id"].astype(int)
    df["stage_id"] = df["stage_id"].astype(str)
    per = df.groupby(["pr_name", "build_id", "stage_id"])[list(LRTS_METRICS.values())].mean().dropna()
    return per.rename(columns={v: k for k, v in LRTS_METRICS.items()}).reset_index()


def lrts_leaky_qtf_avg(src, datasets=("all", "deconf", "firstfail"), seeds=10) -> pd.DataFrame:
    """Per-TSR APFDc-FFMapU of QTF(Avg) as LRTS's eval_outcome computed it: the average duration
    includes the run being ranked. For explaining the published numbers only, never as a baseline."""
    rows = []
    for stage, sdf in ordered_stage_index(src.index).items():
        total, count = defaultdict(float), defaultdict(int)
        for row in sdf.itertuples():
            run = src.read(row)
            for d in datasets:
                excl = src.exclusions(row, d)
                if not scored_on(run, excl):
                    continue
                avg = np.array([round((total[t] + x) / (count[t] + 1), 3) for t, x in zip(run.names, run.duration)])
                keep = np.array([t not in excl for t in run.names])
                vals = []
                for s in range(seeds):
                    o = np.lexsort((tsr_rng(s, row.pr_name, row.build_id, stage).random(len(run)), avg + EPS))
                    vals.append(apfdc(run.duration[o] + DURATION_OFFSET, run.outcome[o] == 1, exclude=~keep[o]))
                rows.append({"dataset": d, "pr_name": row.pr_name, "build_id": int(row.build_id),
                             "stage_id": stage, "apfdc_u": float(np.mean(vals))})
            for t, x in zip(run.names, run.duration):
                total[t] += x
                count[t] += 1
    return pd.DataFrame(rows)


def check_project(project, seeds, out_dir):
    t0 = time.time()
    src = LRTSSource(project)
    v = validate_against_artifact(project, src.labels, load_filter_index())
    print(f"[{project}] filter labels vs dataset_filter.csv ({v.n_tsr[0]} TSR):",
          ", ".join(f"{c.replace('num_fail_class+', '')}={m:.4f}" for c, m in zip(v.column, v.match)))

    prios = [HeuristicPrioritizer(m, tie="random") for m in LRTS_BASELINES]
    raw = run_rolling(src, prios, seeds=seeds)
    raw_dir = ROOT / "results" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(raw_dir / f"parity-{project}.csv.gz", index=False)
    print(f"[{project}] rolling done in {time.time() - t0:.0f}s, {len(raw)} rows")

    rows = []
    for (dataset, method), ours in raw.groupby(["dataset", "method"]):
        ours = ours.rename(columns={"stage": "stage_id"})
        ref = lrts_per_tsr(project, dataset, method)
        key = ["pr_name", "build_id", "stage_id"]
        m = ours.merge(ref, on=key, how="outer", suffixes=("", "_lrts"), indicator=True)
        both = m[m["_merge"] == "both"]
        row = {"project": project, "dataset": dataset, "method": method, "paper_name": paper_name(method),
               "n_ours": int((m["_merge"] != "right_only").sum()), "n_lrts": len(ref),
               "n_only_ours": int((m["_merge"] == "left_only").sum()),
               "n_only_lrts": int((m["_merge"] == "right_only").sum())}
        for k in LRTS_METRICS:
            row[f"{k}_ours"] = ours[k].mean()
            row[f"{k}_lrts"] = ref[k].mean()
            row[f"{k}_diff"] = row[f"{k}_ours"] - row[f"{k}_lrts"]
            per = both[k] - both[f"{k}_lrts"]
            row[f"{k}_mad_per_tsr"] = per.abs().mean()
            row[f"{k}_se_diff"] = per.std(ddof=1) / len(per) ** 0.5 if len(per) > 1 else float("nan")
        rows.append(row)
    res = pd.DataFrame(rows)

    leaky = lrts_leaky_qtf_avg(src)
    res["lrts_leaky_variant_mad"] = np.nan
    for dataset, g in leaky.groupby("dataset"):
        ref = lrts_per_tsr(project, dataset, "QTF(Avg)")
        m = g.merge(ref, on=["pr_name", "build_id", "stage_id"], suffixes=("", "_lrts"))
        res.loc[(res["dataset"] == dataset) & (res["method"] == "QTF(Avg)"), "lrts_leaky_variant_mad"] = \
            (m["apfdc_u"] - m["apfdc_u_lrts"]).abs().mean()

    same_set = (res["n_only_ours"] == 0) & (res["n_only_lrts"] == 0)
    gap = res["apfdc_u_diff"].abs()
    res["verdict"] = "FAIL"
    res.loc[same_set & (gap <= 3 * res["apfdc_u_se_diff"]), "verdict"] = "noise"
    res.loc[same_set & (res["lrts_leaky_variant_mad"] < 0.002) & (gap > TOL), "verdict"] = "lrts-leak"
    res.loc[same_set & (gap <= TOL), "verdict"] = "match"
    res["note"] = ""
    res.loc[~same_set, "note"] = ("TSR sets differ: " + res["n_only_ours"].astype(str) + " only ours, "
                                  + res["n_only_lrts"].astype(str) + " only LRTS")
    res["pass"] = res["verdict"] != "FAIL"
    out_dir.mkdir(parents=True, exist_ok=True)
    res.to_csv(out_dir / f"{project}.csv", index=False)

    show = res[["dataset", "paper_name", "n_ours", "n_lrts", "apfdc_u_ours", "apfdc_u_lrts", "apfdc_u_diff",
                "apfdc_u_mad_per_tsr", "apfdc_u_se_diff", "apfdc_s_diff", "verdict"]]
    with pd.option_context("display.width", 200, "display.float_format", "{:.4f}".format):
        print(show.to_string(index=False))
    counts = res["verdict"].value_counts().to_dict()
    print(f"[{project}] match={counts.get('match', 0)} noise={counts.get('noise', 0)} "
          f"lrts-leak={counts.get('lrts-leak', 0)} FAIL={counts.get('FAIL', 0)} (of {len(res)}; tolerance {TOL})")
    q = res[res["method"] == "QTF(Avg)"][["dataset", "apfdc_u_mad_per_tsr", "lrts_leaky_variant_mad"]]
    print(f"[{project}] QTF(Avg) per-TSR |diff| vs LRTS: clean (ours) vs LRTS's leaky variant\n"
          + q.to_string(index=False, float_format="{:.4f}".format))
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--projects", nargs="+", default=["activemq"])
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "parity")
    args = ap.parse_args(argv)
    ok = True
    for p in args.projects:
        ok &= bool(check_project(p, args.seeds, args.out)["pass"].all())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
