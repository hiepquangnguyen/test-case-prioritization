"""Run methods on one LRTS project with the rolling protocol and save one row per (TSR, dataset, method).

    python scripts/run_experiment.py --project activemq --methods all --tag pilot
    python scripts/run_experiment.py --project activemq --methods HC-FALCON FALCON hcbt_LastFail_Asc \
        --tuned configs/tuned/activemq-deconf.yaml

Output: results/raw/<project>-<tag>.csv.gz (gitignored) and a summary on the eval split printed and saved
to results/summary/<project>-<tag>.csv. The configuration (after --tuned overrides) is stored next to the
summary so every number can be traced back.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd
import yaml

from hcfalcon.hc_falcon import HC_METHODS, SimilarityProvider, config_from_yaml, make_method
from hcfalcon.lrts.embeddings import TSRVectors
from hcfalcon.lrts.loader import LRTSSource
from hcfalcon.prioritizers import LRTS_BASELINES
from hcfalcon.rolling import run_rolling, summarize

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METHODS = list(HC_METHODS) + LRTS_BASELINES


def load_config(path: Path, tuned: Path | None = None) -> dict:
    with open(path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    if tuned is not None:
        with open(tuned, encoding="utf-8") as fh:
            over = yaml.safe_load(fh) or {}
        for section, values in over.items():
            if isinstance(values, dict):
                cfg.setdefault(section, {}).update(values)
    return cfg


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--methods", nargs="+", default=["all"])
    ap.add_argument("--datasets", nargs="+", default=["deconf", "all", "firstfail"])
    ap.add_argument("--config", type=Path, default=ROOT / "configs" / "default.yaml")
    ap.add_argument("--tuned", type=Path, default=None, help="YAML with overrides chosen on the warm-up split")
    ap.add_argument("--index", choices=["artifact", "drive"], default="artifact")
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--tag", default="run")
    args = ap.parse_args(argv)

    raw_cfg = load_config(args.config, args.tuned)
    cfg = config_from_yaml(raw_cfg)
    methods = DEFAULT_METHODS if args.methods == ["all"] else args.methods
    t0 = time.time()
    src = LRTSSource(args.project, source=args.index)
    provider = SimilarityProvider(TSRVectors(args.project), transform=cfg.sim_transform)
    prios = [make_method(m, cfg, provider) for m in methods]
    raw = run_rolling(src, prios, datasets=tuple(args.datasets), seeds=args.seeds,
                      warmup_fraction=float(raw_cfg["protocol"]["warmup_fraction"]))
    raw["config"] = cfg.digest()
    print(f"{args.project}: {len(raw)} rows in {time.time() - t0:.0f}s")

    raw_dir, sum_dir = ROOT / "results" / "raw", ROOT / "results" / "summary"
    raw_dir.mkdir(parents=True, exist_ok=True)
    sum_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(raw_dir / f"{args.project}-{args.tag}.csv.gz", index=False)
    summ = summarize(raw, metrics=("apfdc_u", "apfdc_s", "rapfdc_u", "apfd_u", "ttff_pct", "det10_u", "det25_u",
                                   "det50_u", "rank_time_s"), split="eval")
    summ.to_csv(sum_dir / f"{args.project}-{args.tag}.csv", index=False)
    with open(sum_dir / f"{args.project}-{args.tag}.config.json", "w", encoding="utf-8") as fh:
        json.dump({"args": {k: str(v) for k, v in vars(args).items()}, "config": raw_cfg, "digest": cfg.digest()},
                  fh, indent=2, default=str)
    order = {m: i for i, m in enumerate(methods)}
    summ = summ.sort_values(["dataset", "method"], key=lambda s: s.map(order) if s.name == "method" else s)
    with pd.option_context("display.width", 200, "display.float_format", "{:.4f}".format):
        print(summ.drop(columns=["project"]).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
