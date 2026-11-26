"""Confounding-failure labels of LRTS, recomputed from the processed data.

The Drive release ships only ``test_class.csv.zip``. LRTS derives the labels behind its dataset versions
with ``artifact/extract_filtered_test_result.py``; this module re-implements that script, quirks included,
so our DeConf / FirstFail TSR sets and exclusions match ``eval_outcome``:

- **jira**: the test class matches (``str.endswith``) a flaky test from ``flaky_test/flaky_tests.csv``
  whose fix is later than the build; labelled when the test failed or transitioned.
- **freqfail**: per (project, stage), tests whose failure count over the whole index exceeds
  ``round(mean, 2) + 3 * round(std, 2)``; labelled when the test failed or transitioned.
- **stageunique**: the test failed in this stage but not in every stage of the same build.
- **first**: not the first failure of this test in this (project, stage); FirstFail keeps first failures.

These labels look at the whole dataset (future builds included). They are used **only** to decide which
failures count when scoring, never as features (``paper/decisions.md``, leakage rule).

Only the "for_fail" labels are needed: a TSR is scored on a dataset version iff at least one failed test
survives the union of that version's filters (LRTS reports NaN APFDc otherwise).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from hcfalcon.lrts.loader import ARTIFACT, DATA, DATASETS, build_stage_runs, read_tsr

FILTERS = ("jira", "stageunique", "freqfail", "first")
FLAKY_CSV = ARTIFACT / "flaky_test" / "flaky_tests.csv"


def _split_flaky(test: str):
    """LRTS ``process_jira_flaky_test_helper``: 'Cls#method' | '[param]method' | 'Cls'."""
    tokens = test.split("#")
    if len(tokens) == 2:
        return tokens
    if "[" in tokens[0]:
        return [None, tokens[0]]
    return [tokens[0], None]


def jira_flaky_classes(path: Path = FLAKY_CSV) -> pd.DataFrame:
    """Flaky test classes per project with the earliest fix timestamp (LRTS ``process_jira_flaky_tests``)."""
    df = pd.read_csv(path)
    cms = [_split_flaky(t) for t in df["flaky_test"].tolist()]
    df.insert(2, "testclass", [x[0] for x in cms])
    df.insert(3, "testmethod", [x[1] for x in cms])
    df = df.sort_values(["project", "fix_timestamp"], ascending=True)
    df = df.drop(["flaky_test", "testmethod"], axis=1)
    df = df.drop_duplicates(subset=["project", "testclass"]).dropna()
    return df[["project", "testclass", "fix_timestamp"]].reset_index(drop=True)


def freqfail_outliers(fail_counts: dict) -> set:
    """Tests failing more often than mean + 3 std of the per-test failure counts (LRTS ``get_outlier``)."""
    if not fail_counts:
        return set()
    s = pd.Series(fail_counts, dtype=float)
    mean, std = round(s.mean(), 2), round(s.std(), 2)  # pandas std: ddof=1, NaN for one test
    return set(s[s > mean + 3 * std].index)


def label_run(names, outcome, last_outcome, jira, common, prev_common, frequent) -> dict[str, np.ndarray]:
    """Per-test 0/1 "for_fail" labels of one TSR (LRTS ``label_test``, which uses suffix matching)."""
    jira, common, prev_common, frequent = tuple(jira), tuple(common), tuple(prev_common), tuple(frequent)
    n = len(names)
    out = {f: np.zeros(n, dtype=np.int8) for f in ("jira", "freqfail", "stageunique")}
    for i, (t, o, lo) in enumerate(zip(names, outcome, last_outcome)):
        if o == 1 or o != lo:
            if jira and t.endswith(jira):
                out["jira"][i] = 1
            if frequent and t.endswith(frequent):
                out["freqfail"][i] = 1
        if o == 1 and not (common and t.endswith(common)):
            out["stageunique"][i] = 1
    return out


@dataclass
class Labels:
    """Excluded failing tests per TSR and filter, plus helpers to build dataset-version exclusions."""

    by_filter: dict = field(default_factory=dict)  # (pr, build, stage) -> {filter: frozenset(names)}
    failed: dict = field(default_factory=dict)     # (pr, build, stage) -> frozenset(failed names)

    def exclusion(self, pr_name, build_id, stage_id, dataset: str) -> frozenset:
        per = self.by_filter[(pr_name, int(build_id), str(stage_id))]
        out = frozenset()
        for f in DATASETS[dataset]:
            out = out | per[f]
        return out

    def scored(self, pr_name, build_id, stage_id, dataset: str) -> bool:
        """True iff at least one failure survives the version's filters (APFDc is defined)."""
        key = (pr_name, int(build_id), str(stage_id))
        return bool(self.failed[key] - self.exclusion(*key, dataset))

    def counts(self) -> pd.DataFrame:
        """Per TSR, #failed tests NOT removed by each single filter (``dataset_filter.csv`` convention:
        for 'first' the count of first failures)."""
        rows = []
        for (pr, b, s), per in self.by_filter.items():
            fails = self.failed[(pr, b, s)]
            row = {"pr_name": pr, "build_id": b, "stage_id": s, "num_fail_class": len(fails)}
            for f in ("jira", "freqfail", "stageunique"):
                row[f"num_fail_class+{f}_for_fail"] = len(fails - per[f])
            row["num_fail_class+first_failure"] = len(fails - per["first"])
            rows.append(row)
        return pd.DataFrame(rows)


def compute_labels(index: pd.DataFrame, data_root: Path = DATA, flaky_csv: Path = FLAKY_CSV) -> Labels:
    """Labels for every TSR of ``index`` (one or more projects, LRTS ``dataset.csv`` schema)."""
    index = index.copy()
    index["build_id"] = index["build_id"].astype(int)
    index["stage_id"] = index["stage_id"].astype(str)
    flaky = jira_flaky_classes(flaky_csv)

    def run(row):
        return read_tsr(row.project, row.pr_name, int(row.build_id), str(row.stage_id), Path(data_root))

    # freqfail: failure counts per (project, stage) over the index
    counts = defaultdict(lambda: defaultdict(int))
    for row in index.itertuples():
        r = run(row)
        for t in r.names[r.outcome == 1]:
            counts[(row.project, row.stage_id)][t] += 1
    frequent = {k: freqfail_outliers(v) for k, v in counts.items()}

    # builds in LRTS order: sorted by (project, build_timestamp), one entry per (project, pr, build)
    builds = (index.sort_values(["project", "build_timestamp"], kind="stable")
              [["project", "pr_name", "build_id", "build_timestamp"]]
              .drop_duplicates(subset=["project", "pr_name", "build_id"]))

    in_index = set(zip(index["project"], index["pr_name"], index["build_id"], index["stage_id"]))
    labels = Labels()
    first_seen = defaultdict(set)  # (project, stage) -> tests that already failed
    prev_project = None
    for b in builds.itertuples():
        stages = build_stage_runs(b.project, b.pr_name, int(b.build_id), Path(data_root))
        fail_sets = [set(r.names[r.outcome == 1]) for r in stages.values()]
        common = set.intersection(*fail_sets) if fail_sets else set()
        # LRTS quirk: "prev" common failures are the *current* build's, except for a project's first build
        prev_common = common if prev_project == b.project else set()
        prev_project = b.project
        jira = flaky[(flaky["project"] == b.project) & (flaky["fix_timestamp"] > b.build_timestamp)]
        jira = jira["testclass"].tolist()

        for stage, r in stages.items():
            lab = label_run(r.names, r.outcome, r.last_outcome, jira, common, prev_common,
                            frequent.get((b.project, stage), set()))
            failed = r.outcome == 1
            seen = first_seen[(b.project, stage)]
            not_first = np.zeros(len(r), dtype=bool)
            for i in np.flatnonzero(failed):
                t = r.names[i]
                if t in seen:
                    not_first[i] = True
                else:
                    seen.add(t)
            if (b.project, b.pr_name, int(b.build_id), stage) not in in_index:
                continue
            key = (b.pr_name, int(b.build_id), stage)
            labels.failed[key] = frozenset(r.names[failed])
            labels.by_filter[key] = {
                "jira": frozenset(r.names[lab["jira"] == 1]),
                "freqfail": frozenset(r.names[lab["freqfail"] == 1]),
                "stageunique": frozenset(r.names[lab["stageunique"] == 1]),
                "first": frozenset(r.names[not_first]),
            }
    return labels


def validate_against_artifact(project: str, labels: Labels, filter_index: pd.DataFrame) -> pd.DataFrame:
    """Share of TSRs whose per-filter failure counts equal LRTS ``dataset_filter.csv``."""
    ours = labels.counts()
    ref = filter_index[filter_index["project"] == project]
    cols = ["num_fail_class", "num_fail_class+jira_for_fail", "num_fail_class+freqfail_for_fail",
            "num_fail_class+stageunique_for_fail", "num_fail_class+first_failure"]
    m = ours.merge(ref[["pr_name", "build_id", "stage_id"] + cols], on=["pr_name", "build_id", "stage_id"],
                   suffixes=("", "_ref"), how="inner")
    return pd.DataFrame({
        "column": cols,
        "match": [(m[c] == m[c + "_ref"]).mean() for c in cols],
        "n_tsr": len(m),
        "n_ours": len(ours),
    })
