"""Time-ordered (rolling) evaluation on CI history.

For each (project, stage), TSRs are visited in ``build_timestamp`` order:

1. read the TSR's test names; take history features as of strictly before its timestamp;
2. every prioritizer ranks the tests (``seeds`` times if it breaks ties randomly);
3. on each dataset version where the TSR has a surviving failure, score the order;
4. only after all TSRs with that timestamp have been ranked, add their results to the history.

All TSRs update the history, whether or not they are scored. The first ``warmup_fraction`` of each
stage's TSRs (by position in time) are tagged ``split="warmup"`` and reserved for tuning.

A *source* provides ``project``, ``index`` (DataFrame with pr_name, build_id, stage_id,
build_timestamp), ``read(row) -> Run`` and ``exclusions(row, dataset) -> frozenset``: see
``hcfalcon.lrts.loader.LRTSSource`` and ``MemorySource`` (tests, synthetic data).
"""

from __future__ import annotations

import math
import time
import zlib
from collections import defaultdict
from dataclasses import dataclass

import numpy as np
import pandas as pd

from hcfalcon.history import HistoryStore
from hcfalcon.lrts.loader import Run
from hcfalcon.metrics import evaluate_order
from hcfalcon.prioritizers import RankContext

DURATION_OFFSET = 0.001  # LRTS adds 1 ms to every recorded duration before scoring
METRICS = ("n_tests", "n_fail", "total_time", "apfd_u", "apfd_s", "apfdc_u", "apfdc_s", "rapfdc_u",
           "rapfdc_s", "ttff_s", "ttff_pct", "det10_u", "det25_u", "det50_u")


@dataclass
class MemorySource:
    """In-memory source: ``runs[(pr, build, stage)] = Run``; ``excl[dataset][key] = set`` (default empty)."""

    project: str
    index: pd.DataFrame
    runs: dict
    excl: dict | None = None

    def read(self, row) -> Run:
        return self.runs[(row.pr_name, int(row.build_id), str(row.stage_id))]

    def exclusions(self, row, dataset: str) -> frozenset:
        if not self.excl or dataset not in self.excl:
            return frozenset()
        return frozenset(self.excl[dataset].get((row.pr_name, int(row.build_id), str(row.stage_id)), ()))


def ordered_stage_index(index: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Per stage, TSRs sorted by build timestamp (stable on the index order for ties)."""
    out = {}
    for stage, df in index.groupby("stage_id", sort=True):
        out[str(stage)] = df.sort_values("build_timestamp", kind="stable").reset_index(drop=True)
    return out


def tsr_rng(seed: int, pr_name: str, build_id: int, stage: str) -> np.random.Generator:
    """Reproducible random stream per (seed, TSR). Sharing one stream per seed across TSRs would give
    identical permutations to TSRs of equal size and correlate their results."""
    return np.random.default_rng([seed, zlib.crc32(f"{pr_name}|{int(build_id)}|{stage}".encode())])


def scored_on(run: Run, excluded: frozenset) -> bool:
    return any(o == 1 and t not in excluded for t, o in zip(run.names, run.outcome))


def run_rolling(source, prioritizers, datasets=("all", "deconf", "firstfail"), seeds: int = 10,
                warmup_fraction: float = 0.2, leak: bool = False, on_rank=None,
                splits=("warmup", "eval"), only_keys=None) -> pd.DataFrame:
    """One row per (TSR, dataset, method) with metrics averaged over seeds.

    ``splits`` restricts which TSRs are ranked and scored (all TSRs still update the history);
    ``splits=("warmup",)`` stops each stage after its warm-up part, for tuning. ``only_keys`` (a set of
    (pr_name, build_id, stage_id)) restricts ranking further, e.g. for leakage checks.
    ``leak=True`` updates the history with a TSR *before* ranking it. It exists only so the leakage
    tests can show the pipeline would notice; never use it for results.
    ``on_rank(row, method, seed, order, ctx)`` is called for every ranking (tests, explanations).
    """
    rows = []
    for stage, sdf in ordered_stage_index(source.index).items():
        hist = HistoryStore()
        n_warm = math.ceil(warmup_fraction * len(sdf))
        for _, group in sdf.groupby("build_timestamp", sort=True):
            if "eval" not in splits and group.index.min() >= n_warm:
                break
            runs = [(row, source.read(row)) for row in group.itertuples()]
            if leak:
                for row, run in runs:
                    hist.update(run.names, run.duration, run.outcome, row.build_timestamp)
            for row, run in runs:
                split = "warmup" if row.Index < n_warm else "eval"
                if split not in splits:
                    continue
                if only_keys is not None and (row.pr_name, int(row.build_id), stage) not in only_keys:
                    continue
                excl = {d: source.exclusions(row, d) for d in datasets}
                todo = [d for d in datasets if scored_on(run, excl[d])]
                if not todo:
                    continue
                ts = row.build_timestamp
                feats = hist.features(run.names, as_of=None if leak else ts)
                hstats = hist.stats()
                key = (row.pr_name, int(row.build_id), stage)
                base = {
                    "project": source.project, "stage": stage, "pr_name": row.pr_name,
                    "build_id": int(row.build_id), "timestamp": ts, "position": int(row.Index),
                    "split": split,
                    "n_new_tests": int((~feats["known"]).sum()),
                }
                dur = run.duration + DURATION_OFFSET
                failed = run.outcome == 1
                masks = {d: np.fromiter((t in excl[d] for t in run.names), bool, len(run)) for d in todo}
                for p in prioritizers:
                    n_seeds = seeds if getattr(p, "stochastic", False) else 1
                    acc = defaultdict(list)
                    for seed in range(n_seeds):
                        ctx = RankContext(names=run.names, features=feats,
                                          rng=tsr_rng(seed, row.pr_name, row.build_id, stage),
                                          project=source.project, stage=stage, timestamp=ts,
                                          key=key, history_stats=hstats)
                        t0 = time.perf_counter()
                        order = p.rank(ctx)
                        acc["rank_time_s"].append(time.perf_counter() - t0)
                        for k, v in (getattr(p, "last_stats", None) or {}).items():
                            acc[("stat", k)].append(v)
                        if on_rank is not None:
                            on_rank(row, p.name, seed, order, ctx)
                        for d in todo:
                            m = evaluate_order(dur[order], failed[order], exclude=masks[d][order])
                            for k in METRICS:
                                acc[(d, k)].append(m[k])
                    rt = float(np.mean(acc["rank_time_s"]))
                    extra = {k[1]: float(np.mean(v)) for k, v in acc.items() if isinstance(k, tuple) and k[0] == "stat"}
                    for d in todo:
                        rows.append({**base, "dataset": d, "method": p.name, "n_seeds": n_seeds,
                                     **{k: float(np.mean(acc[(d, k)])) for k in METRICS},
                                     "rank_time_s": rt, **extra})
            if not leak:
                for row, run in runs:
                    hist.update(run.names, run.duration, run.outcome, row.build_timestamp)
    return pd.DataFrame(rows)


def summarize(raw: pd.DataFrame, metrics=("apfdc_u", "apfdc_s", "apfd_u"), split=None) -> pd.DataFrame:
    """Mean of each metric per (project, dataset, method) over scored TSRs."""
    df = raw if split is None else raw[raw["split"] == split]
    g = df.groupby(["project", "dataset", "method"])
    out = g[list(metrics)].mean()
    out.insert(0, "n_tsr", g.size())
    return out.reset_index()
