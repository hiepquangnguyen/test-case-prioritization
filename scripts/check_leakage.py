"""Leakage checks on one project with its locked configurations (pre-registration §3, step 4).

For HC-FALCON and HC-FALCON-prop (``configs/tuned/<project>-<dataset>-locked[-prop].yaml``):
- prefix invariance on ``--n`` DeConf-scored TSRs spread over time: the order must not change when all later
  TSRs are dropped or scrambled;
- deliberate leak: feeding each TSR's own results into the history first must raise APFDc clearly.

    python scripts/check_leakage.py --project hbase
    ->  results/pilot/<project>/leakage.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from hcfalcon.hc_falcon import SimilarityProvider, config_from_yaml, make_method
from hcfalcon.leakage import check_prefix_invariance, leak_sensitivity
from hcfalcon.lrts.embeddings import TSRVectors
from hcfalcon.lrts.loader import LRTSSource

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_experiment import load_config  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--dataset", default="deconf")
    ap.add_argument("--n", type=int, default=4)
    args = ap.parse_args(argv)
    t0 = time.time()
    tuned = ROOT / "configs" / "tuned"
    cfgs = {"HC-FALCON": config_from_yaml(load_config(ROOT / "configs" / "default.yaml",
                                                      tuned / f"{args.project}-{args.dataset}-locked.yaml")),
            "HC-FALCON-prop": config_from_yaml(load_config(ROOT / "configs" / "default.yaml",
                                                           tuned / f"{args.project}-{args.dataset}-locked-prop.yaml"))}
    src = LRTSSource(args.project)
    tv = TSRVectors(args.project)
    ts = src.index.assign(stage_id=src.index.stage_id.astype(str)).set_index(["pr_name", "build_id", "stage_id"]).build_timestamp
    keys = sorted([k for k in src.labels.failed if src.labels.scored(*k, args.dataset)], key=lambda k: ts[k])
    targets = [keys[i] for i in np.linspace(3, len(keys) - 2, args.n).round().astype(int)]
    out = {"project": args.project, "targets": [list(map(str, k)) for k in targets]}
    for name, cfg in cfgs.items():
        r = check_prefix_invariance(src, make_method(name, cfg, SimilarityProvider(tv)), targets, datasets=(args.dataset,))
        out[name] = {"ranked": bool(r.ranked.all()), "same_when_dropped": bool(r.same_when_dropped.all()),
                     "same_when_scrambled": bool(r.same_when_scrambled.all())}
        print(name, out[name], f"({time.time() - t0:.0f}s)")
    leak = leak_sensitivity(src, make_method("HC-FALCON-prop", cfgs["HC-FALCON-prop"], SimilarityProvider(tv)),
                            dataset=args.dataset)
    out["leak_sensitivity"] = leak
    out["passed"] = all(out[m]["ranked"] and out[m]["same_when_dropped"] and out[m]["same_when_scrambled"]
                        for m in cfgs) and leak["leaked"] > leak["clean"] + 0.05
    print("leak", leak, "PASSED" if out["passed"] else "FAILED")
    dest = ROOT / "results" / "pilot" / args.project / "leakage.json"
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return 0 if out["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
