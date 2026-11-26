"""Per-project APFDc of LRTS baselines, read from the LRTS artifact's own eval_outcome.

These are the week-3 / week-7 parity targets: our re-implementation of each baseline must land
within 0.01 of these means on the same dataset version and the same TSRs.

LRTS naming: ``cbt_X`` = X + cost-cognizant (CC), ``hcbt_X`` = X + cost-history-cognizant (CCH),
``LastFail_Asc`` = LatestFail, ``FailCount_Desc`` = MostFail. Values are averaged over the 10
seeds per TSR first, then over TSRs with at least one (non-confounding) failure.

    python scripts/lrts_reference_targets.py  ->  results/reference/lrts_targets.csv
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTCOME = ROOT / "external" / "LRTS" / "artifact" / "evaluation" / "eval_outcome"
DATASETS = {"deconf": "d_jira_stageunique_freqfail", "all": "d_nofilter", "firstfail": "d_first_jira_stageunique"}
PROJECTS = ["activemq", "jackrabbit-oak", "hbase", "hadoop", "karaf"]
TECHNIQUES = ["Random", "QTF", "QTF(Avg)", "LastFail_Asc", "FailCount_Desc", "LastTrans_Asc",
              "TransCount_Desc", "cbt_LastFail_Asc", "cbt_FailCount_Desc", "hcbt_LastFail_Asc", "ML_fall"]
METRICS = ["APFDc_uniqueBug", "APFDc_sameBug", "APFD_uniqueBug"]


def main():
    rows = []
    for label, folder in DATASETS.items():
        for project in PROJECTS:
            for tech in TECHNIQUES:
                path = OUTCOME / folder / project / f"{tech}.csv.zip"
                if not path.exists():
                    continue
                df = pd.read_csv(path)
                per_tsr = df.groupby(["pr_name", "build_id", "stage_id"])[METRICS].mean().dropna()
                row = {"dataset": label, "project": project, "technique": tech, "n_tsr": len(per_tsr)}
                row.update({m: round(per_tsr[m].mean(), 4) for m in METRICS})
                rows.append(row)
    out = ROOT / "results" / "reference" / "lrts_targets.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"{len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
