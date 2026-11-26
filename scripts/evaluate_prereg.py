"""Apply the decision rule of paper/preregistration-B.md to the pilot outputs.

A method *wins* against a baseline on a project (eval split, DeConf, APFDc-FFMapU) when
p_Holm < 0.05, Cliff's delta >= 0.147 (positive, not negligible) and the median is >= 3% higher.

    H1  HC-FALCON-prop wins History+Cost
    H2  HC-FALCON wins History+Cost
    H3  HC-FALCON or HC-FALCON-prop wins FALCON and History
    H4  HC-FALCON or HC-FALCON-prop wins LatestFail+CCH
    GO  (H1 or H2) and H3 on every primary project

    python scripts/evaluate_prereg.py --primary jackrabbit-oak hbase [--secondary hadoop karaf] [--dev activemq]
    ->  results/prereg/evaluation.csv, results/prereg/decision.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P_MAX, DELTA_MIN, MEDIAN_MIN = 0.05, 0.147, 0.03


def wins(row) -> bool:
    return bool(row["p_holm"] < P_MAX and row["cliffs_delta"] >= DELTA_MIN and row["median_rel_change"] >= MEDIAN_MIN)


def project_hypotheses(project: str, dataset: str = "deconf") -> tuple[dict, pd.DataFrame]:
    t = pd.read_csv(ROOT / "results" / "pilot" / project / "paired_tests.csv")
    t = t[t["dataset"] == dataset].copy()
    t["wins_rule"] = t.apply(wins, axis=1)  # "wins" / "losses" are counts of TSRs
    w = {(r.method, r.baseline): r.wins_rule for r in t.itertuples()}

    def win(method, base):
        return w.get((method, base), False)

    hc = ("HC-FALCON", "HC-FALCON-prop")
    h = {
        "H1": win("HC-FALCON-prop", "History+Cost"),
        "H2": win("HC-FALCON", "History+Cost"),
        "H3": any(win(m, "FALCON") and win(m, "History") for m in hc),
        "H4": any(win(m, "hcbt_LastFail_Asc") for m in hc),
    }
    keep = t[t["method"].isin(hc) & t["baseline"].isin(["History+Cost", "FALCON", "History", "hcbt_LastFail_Asc"])]
    return h, keep.assign(project=project)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--primary", nargs="+", default=["jackrabbit-oak", "hbase"])
    ap.add_argument("--secondary", nargs="*", default=[])
    ap.add_argument("--dev", nargs="*", default=["activemq"])
    args = ap.parse_args(argv)

    out = ROOT / "results" / "prereg"
    out.mkdir(parents=True, exist_ok=True)
    rows, tables = {}, []
    for role, projects in (("primary", args.primary), ("secondary", args.secondary), ("development", args.dev)):
        for p in projects:
            if not (ROOT / "results" / "pilot" / p / "paired_tests.csv").exists():
                print(f"{p}: no pilot results, skipped")
                continue
            h, tab = project_hypotheses(p)
            rows[p] = {"role": role, **h}
            tables.append(tab.assign(role=role))
    summary = pd.DataFrame(rows).T
    detail = pd.concat(tables, ignore_index=True)
    cols = ["role", "project", "method", "baseline", "n_tsr", "mean_apfdc_u", "baseline_mean_apfdc_u",
            "median_rel_change", "wins", "losses", "p_holm", "cliffs_delta", "magnitude", "wins_rule"]
    detail[cols].to_csv(out / "evaluation.csv", index=False)

    prim = summary[summary["role"] == "primary"]
    go = bool(len(prim) == len(args.primary) and ((prim["H1"] | prim["H2"]) & prim["H3"]).all())
    decision = {"GO": go, "per_project": summary.to_dict(orient="index"),
                "rule": "GO iff (H1 or H2) and H3 on every primary project",
                "criteria": {"p_holm_max": P_MAX, "cliffs_delta_min": DELTA_MIN, "median_rel_change_min": MEDIAN_MIN}}
    with open(out / "decision.json", "w", encoding="utf-8") as fh:
        json.dump(decision, fh, indent=2, default=bool)
    pd.set_option("display.width", 200)
    print(summary.to_string())
    print(detail[["project", "method", "baseline", "mean_apfdc_u", "baseline_mean_apfdc_u", "median_rel_change",
                  "p_holm", "cliffs_delta", "wins_rule"]].round(4).to_string(index=False))
    print("DECISION:", "GO" if go else "NO-GO (negative-result report)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
