"""Write readable HC-FALCON explanations for a few TSRs (week-5 checkpoint).

    python scripts/explain_tsr.py --project activemq [--tuned configs/tuned/activemq-deconf.yaml] [--n 3] [--top 15]

Picks ``--n`` evenly spaced eval TSRs scored on DeConf (or ``--tsr PR-123:1:single`` explicitly) and
writes results/explain/<project>/<pr>_<build>_<stage>.{csv,txt}. The "FAILED/passed" mark is the real
outcome, revealed after the run; it is shown only to judge the explanation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

from hcfalcon.explain import explanation_table, render, share_semantic
from hcfalcon.hc_falcon import SimilarityProvider, config_from_yaml, make_method
from hcfalcon.lrts.embeddings import TSRVectors
from hcfalcon.lrts.loader import LRTSSource
from hcfalcon.rolling import run_rolling

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_experiment import load_config  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--config", type=Path, default=ROOT / "configs" / "default.yaml")
    ap.add_argument("--tuned", type=Path, default=None)
    ap.add_argument("--method", default="HC-FALCON")
    ap.add_argument("--tsr", nargs="*", default=None, help="PR-123:1:single ...")
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args(argv)

    raw_cfg = load_config(args.config, args.tuned)
    cfg = config_from_yaml(raw_cfg)
    src = LRTSSource(args.project)
    warm = float(raw_cfg["protocol"]["warmup_fraction"])
    if args.tsr:
        targets = [(p, int(b), s) for p, b, s in (x.split(":", 2) for x in args.tsr)]
    else:
        idx = src.index.sort_values("build_timestamp", kind="stable")
        keys = [(r.pr_name, int(r.build_id), str(r.stage_id)) for r in idx.itertuples()]
        n_warm = int(np.ceil(warm * len(keys)))
        scored = [k for k in keys[n_warm:] if src.labels.scored(*k, "deconf")]
        targets = [scored[i] for i in np.linspace(0, len(scored) - 1, args.n).round().astype(int)]

    provider = SimilarityProvider(TSRVectors(args.project), transform=cfg.sim_transform)
    prio = make_method(args.method, cfg, provider, explain_top=3)
    out_dir = ROOT / "results" / "explain" / args.project
    out_dir.mkdir(parents=True, exist_ok=True)
    wanted = set(targets)

    def grab(row, method, seed, order, ctx):
        key = (row.pr_name, int(row.build_id), str(row.stage_id))
        if key not in wanted:
            return
        run = src.read(row)
        table = explanation_table(prio.last, k=args.top, outcome=run.outcome)
        failed_pos = (np.flatnonzero(run.outcome[order] == 1) + 1).tolist()
        header = (f"{args.project} {key[0]} build {key[1]} stage {key[2]} | {args.method} alpha={cfg.alpha} "
                  f"estimator={cfg.est.estimator} | {len(order)} tests, failing tests at positions {failed_pos} | "
                  f"semantic share of the first 10 gains: {share_semantic(prio.last):.2f}")
        stem = f"{key[0]}_{key[1]}_{key[2]}"
        table.to_csv(out_dir / f"{stem}.csv", index=False)
        (out_dir / f"{stem}.txt").write_text(render(table, header) + "\n", encoding="utf-8")
        print(render(table.head(8), header), "\n")

    run_rolling(src, [prio], datasets=("all", "deconf"), seeds=1, warmup_fraction=warm, on_rank=grab)
    print(f"explanations -> {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
