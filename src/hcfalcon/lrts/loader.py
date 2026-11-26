"""Read the processed LRTS dataset (Cheng et al., ISSTA 2024).

Layout (``data/lrts/long_running_test_suites``)::

    dataset.csv                                   one row per test-suite run (TSR)
    processed_test_result/<project>/<pr>_build<id>/stage_<stage>/test_class.csv.zip
        testclass, duration, outcome (0 pass / 1 fail), last_outcome

The TSR index comes from ``external/LRTS/artifact/metadata/dataset.csv`` by default: it is the set the
paper and ``eval_outcome`` were computed on (57,437 TSRs up to 2023-07). The Drive ``dataset.csv`` is a
superset that runs to 2024-04 (``source="drive"``); see ``paper/decisions.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "lrts" / "long_running_test_suites"
ARTIFACT = ROOT / "external" / "LRTS" / "artifact"
TEST_CLASS_CSV = "test_class.csv.zip"

#: dataset version -> LRTS filters whose labelled failures are removed before scoring
DATASETS = {
    "all": (),
    "deconf": ("jira", "stageunique", "freqfail"),
    "firstfail": ("first", "jira", "stageunique"),
}
#: folder names used by LRTS ``eval_outcome``
DATASET_FOLDERS = {
    "all": "d_nofilter",
    "deconf": "d_jira_stageunique_freqfail",
    "firstfail": "d_first_jira_stageunique",
}
KEY = ["pr_name", "build_id", "stage_id"]


@dataclass(frozen=True)
class Run:
    """Results of one test-suite run, in the order the CSV lists them (not a priority order)."""

    names: np.ndarray        # str, test class names
    duration: np.ndarray     # float64 seconds, as recorded (no offset)
    outcome: np.ndarray      # int8, 1 = fail
    last_outcome: np.ndarray  # int8, outcome of the same test in the previous build of this PR/stage

    def __len__(self) -> int:
        return len(self.names)

    @classmethod
    def from_frame(cls, df: pd.DataFrame) -> "Run":
        arrays = (
            df["testclass"].to_numpy(dtype=object).astype(str),
            df["duration"].to_numpy(dtype=np.float64, copy=True),
            df["outcome"].to_numpy(dtype=np.int8, copy=True),
            df["last_outcome"].to_numpy(dtype=np.int8, copy=True),
        )
        for a in arrays:
            a.setflags(write=False)  # runs are cached and shared: never mutate in place
        return cls(*arrays)


def load_index(source: str = "artifact", projects=None) -> pd.DataFrame:
    """TSR metadata (project, pr_name, build_id, stage_id, build_timestamp, num_fail_class, ...)."""
    if source == "artifact":
        path = ARTIFACT / "metadata" / "dataset.csv"
    elif source == "drive":
        path = DATA / "dataset.csv"
    else:
        raise ValueError(f"unknown index source {source!r}")
    df = pd.read_csv(path)
    df["build_id"] = df["build_id"].astype(int)
    df["stage_id"] = df["stage_id"].astype(str)
    if projects is not None:
        projects = [projects] if isinstance(projects, str) else list(projects)
        df = df[df["project"].isin(projects)]
    return df.reset_index(drop=True)


def load_filter_index() -> pd.DataFrame:
    """LRTS ``dataset_filter.csv``: per-TSR failure counts after each filter (used to validate labels)."""
    df = pd.read_csv(ARTIFACT / "metadata" / "dataset_filter.csv")
    df["build_id"] = df["build_id"].astype(int)
    df["stage_id"] = df["stage_id"].astype(str)
    return df


def build_dir(project: str, pr_name: str, build_id: int, data_root: Path = DATA) -> Path:
    return Path(data_root) / "processed_test_result" / project / f"{pr_name}_build{int(build_id)}"


def tsr_path(project: str, pr_name: str, build_id: int, stage_id: str, data_root: Path = DATA) -> Path:
    return build_dir(project, pr_name, build_id, data_root) / f"stage_{stage_id}" / TEST_CLASS_CSV


@lru_cache(maxsize=4096)
def read_tsr(project: str, pr_name: str, build_id: int, stage_id: str, data_root: Path = DATA) -> Run:
    return Run.from_frame(pd.read_csv(tsr_path(project, pr_name, build_id, stage_id, data_root)))


def build_stage_runs(project: str, pr_name: str, build_id: int, data_root: Path = DATA) -> dict[str, Run]:
    """Every stage of one build found on disk (LRTS globs the folder, not the index)."""
    out = {}
    for p in sorted(build_dir(project, pr_name, build_id, data_root).glob(f"stage_*/{TEST_CLASS_CSV}")):
        stage = p.parent.name[len("stage_"):]
        out[stage] = read_tsr(project, pr_name, int(build_id), stage, data_root)
    return out


class LRTSSource:
    """TSR index + run reader + per-dataset exclusion sets for one project (input to ``rolling``)."""

    def __init__(self, project: str, source: str = "artifact", data_root: Path = DATA, labels=None):
        from hcfalcon.lrts.filters import compute_labels

        self.project = project
        self.data_root = Path(data_root)
        self.index = load_index(source, project)
        if self.index.empty:
            raise ValueError(f"no TSRs for project {project!r} in index {source!r}")
        self.labels = labels if labels is not None else compute_labels(self.index, self.data_root)

    def read(self, row) -> Run:
        return read_tsr(self.project, row.pr_name, int(row.build_id), str(row.stage_id), self.data_root)

    def exclusions(self, row, dataset: str) -> frozenset:
        return self.labels.exclusion(row.pr_name, int(row.build_id), str(row.stage_id), dataset)
