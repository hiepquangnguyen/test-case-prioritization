"""Leakage checks for the rolling evaluation (version 1).

Guards that run on every experiment:

- ``RankContext`` has no outcomes or durations of the TSR being ranked (by construction);
- ``HistoryStore.features(as_of=t)`` raises ``LeakageError`` if any stored run is not strictly older
  than ``t``; ``update`` refuses timestamps that go backwards.

Checks run in tests and on real data before reporting results:

- ``check_prefix_invariance``: the order produced for TSR b must not change when every TSR after b is
  removed, or when their outcomes and durations are scrambled;
- ``leak_sensitivity``: deliberately feeding each TSR's own results into the history before ranking must
  raise APFDc clearly, which shows the metrics would reveal a leak if one slipped in.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from hcfalcon.history import LeakageError
from hcfalcon.lrts.loader import Run
from hcfalcon.rolling import run_rolling

__all__ = ["LeakageError", "check_prefix_invariance", "leak_sensitivity"]


@dataclass
class _CutSource:
    """View of a source: TSRs after ``cutoff`` are dropped (mode="drop") or scrambled (mode="scramble")."""

    base: object
    cutoff: float
    mode: str
    seed: int = 0

    @property
    def project(self):
        return self.base.project

    @property
    def index(self) -> pd.DataFrame:
        idx = self.base.index
        return idx[idx["build_timestamp"] <= self.cutoff] if self.mode == "drop" else idx

    def read(self, row) -> Run:
        run = self.base.read(row)
        if self.mode != "scramble" or row.build_timestamp <= self.cutoff:
            return run
        rng = np.random.default_rng((self.seed, int(row.build_id), len(run)))
        return Run(names=run.names, duration=rng.permutation(run.duration) * rng.uniform(0.1, 10),
                   outcome=rng.permutation(1 - run.outcome).astype(np.int8),
                   last_outcome=run.last_outcome)

    def exclusions(self, row, dataset):
        return self.base.exclusions(row, dataset)


def _build(prioritizer, source):
    """A prioritizer, or a factory ``f(source) -> prioritizer`` for methods that precompute anything from
    the data (fitted statistics, embeddings): the factory is rerun on each modified view."""
    is_factory = isinstance(prioritizer, type) or not hasattr(prioritizer, "rank")
    return prioritizer(source) if is_factory else prioritizer


def _orders(source, prioritizer, targets, seed, datasets):
    prioritizer = _build(prioritizer, source)
    got = {}

    def grab(row, method, s, order, ctx):
        key = (row.pr_name, int(row.build_id), str(row.stage_id))
        if s == seed and key in targets:
            got[key] = np.asarray(order).copy()

    run_rolling(source, [prioritizer], datasets=datasets, seeds=seed + 1, on_rank=grab, only_keys=set(targets))
    return got


def check_prefix_invariance(source, prioritizer, targets, seed: int = 0, datasets=("all",)) -> pd.DataFrame:
    """For each target key (pr_name, build_id, stage_id), compare its order on the full history with
    the order when the future is dropped and when it is scrambled. All must be identical.

    ``prioritizer`` is a prioritizer or a factory ``f(source) -> prioritizer`` (see ``_build``)."""
    idx = source.index
    rows = []
    full = _orders(source, prioritizer, set(targets), seed, datasets)
    for key in targets:
        sel = idx[(idx["pr_name"] == key[0]) & (idx["build_id"].astype(int) == key[1])
                  & (idx["stage_id"].astype(str) == key[2])]
        if sel.empty or key not in full:
            rows.append({"key": key, "ranked": False, "same_when_dropped": None, "same_when_scrambled": None})
            continue
        cutoff = float(sel["build_timestamp"].iloc[0])
        dropped = _orders(_CutSource(source, cutoff, "drop"), prioritizer, {key}, seed, datasets)
        scrambled = _orders(_CutSource(source, cutoff, "scramble", seed), prioritizer, {key}, seed, datasets)
        rows.append({"key": key, "ranked": True,
                     "same_when_dropped": bool(np.array_equal(full[key], dropped.get(key))),
                     "same_when_scrambled": bool(np.array_equal(full[key], scrambled.get(key)))})
    return pd.DataFrame(rows)


def leak_sensitivity(source, prioritizer, dataset: str = "all", seeds: int = 1) -> dict:
    """Mean APFDc-FFMapU without and with the deliberate leak."""
    prioritizer = _build(prioritizer, source)
    clean = run_rolling(source, [prioritizer], datasets=(dataset,), seeds=seeds)
    leaked = run_rolling(source, [prioritizer], datasets=(dataset,), seeds=seeds, leak=True)
    return {"clean": float(clean["apfdc_u"].mean()), "leaked": float(leaked["apfdc_u"].mean()),
            "n_tsr": int(len(clean))}
