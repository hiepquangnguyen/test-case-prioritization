"""Test-class vectors for LRTS TSRs, assembled locally from method embeddings computed on Colab.

Chain: (TSR, test class) -> blob(s) of the class file (``tsr_tests.csv.gz``) -> method ids
(``blobs.jsonl.gz``) -> method vectors (``data/embeddings/lrts/<project>/<model>_methods.npz``, from
``notebooks/embed_colab.ipynb`` mode b).

A class vector is the mean of its L2-normalised method vectors (``configs/default.yaml``:
``class_vector: mean_of_methods``). When a class name exists in several modules the candidate files are
averaged. Classes without source (e.g. tests shipped in a dependency jar) get a zero vector and
``found=False``; the similarity layer isolates them (sim 0 to others, 1 to itself).
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

from hcfalcon.lrts.loader import ROOT
from hcfalcon.similarity import l2_normalize

SOURCE = ROOT / "data" / "lrts" / "source"
EMB = ROOT / "data" / "embeddings" / "lrts"


def method_vectors_path(project: str, model: str = "unixcoder", root: Path = EMB) -> Path:
    return Path(root) / project / f"{model}_methods.npz"


def load_method_vectors(path: Path) -> dict[str, np.ndarray]:
    z = np.load(path, allow_pickle=False)
    vecs = l2_normalize(z["vectors"].astype(np.float32))
    return dict(zip(z["ids"].tolist(), vecs))


def load_blob_methods(project: str, root: Path = SOURCE) -> dict[str, list[str]]:
    out = {}
    with gzip.open(Path(root) / project / "blobs.jsonl.gz", "rt", encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            out[r["blob"]] = r["method_ids"]
    return out


def blob_vectors(blob_methods: dict, method_vecs: dict) -> dict[str, np.ndarray]:
    """Blob -> mean of its method vectors (blobs whose methods are all unembedded are left out)."""
    out = {}
    for b, ids in blob_methods.items():
        vs = [method_vecs[i] for i in ids if i in method_vecs]
        if vs:
            out[b] = np.mean(vs, axis=0).astype(np.float32)
    return out


class TSRVectors:
    """``get(pr_name, build_id, stage_id, names) -> (emb (n, d) float32, found (n,) bool)``."""

    def __init__(self, project: str, model: str = "unixcoder", source_root: Path = SOURCE, emb_root: Path = EMB):
        self.project = project
        mv = load_method_vectors(method_vectors_path(project, model, emb_root))
        self.dim = len(next(iter(mv.values())))
        self.blobs = blob_vectors(load_blob_methods(project, source_root), mv)
        tests = pd.read_csv(Path(source_root) / project / "tsr_tests.csv.gz", dtype={"stage_id": str},
                            keep_default_na=False)
        self.map = {}
        for (pr, b, s), g in tests.groupby(["pr_name", "build_id", "stage_id"], sort=False):
            self.map[(pr, int(b), str(s))] = dict(zip(g["testclass"], g["blobs"]))

    def class_vector(self, blobs: str):
        vs = [self.blobs[b] for b in blobs.split(";") if b and b in self.blobs] if blobs else []
        return np.mean(vs, axis=0) if vs else None

    def get(self, pr_name, build_id, stage_id, names):
        m = self.map.get((pr_name, int(build_id), str(stage_id)), {})
        emb = np.zeros((len(names), self.dim), dtype=np.float32)
        found = np.zeros(len(names), dtype=bool)
        for i, t in enumerate(names):
            v = self.class_vector(m.get(t, ""))
            if v is not None:
                emb[i], found[i] = v, True
        return emb, found

    def coverage(self) -> pd.DataFrame:
        """Share of test classes with a vector, per TSR."""
        rows = []
        for (pr, b, s), m in self.map.items():
            got = sum(self.class_vector(x) is not None for x in m.values())
            rows.append({"pr_name": pr, "build_id": b, "stage_id": s, "n_tests": len(m),
                         "emb_coverage": got / len(m) if m else float("nan")})
        return pd.DataFrame(rows)
