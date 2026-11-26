"""Reproduce FALCON on the six Defects4J projects of the FALCON artifact (week 2 checkpoint).

Inputs
------
* FALCON artifact clone (default ``external/falcon-icst-2026``): ``input/<P>/fault_matrix.pickle``
  ({method_idx: [bug_ids]}) and the method count from ``input/<P>/<P>-bbox.txt``.
* Embeddings produced on Colab by ``notebooks/embed_colab.ipynb`` (mode a), unpacked to
  ``data/embeddings/d4j/<P>/<model>_test_embeddings.npy``. The notebook also stores the order
  produced by the artifact's own code (``falcon_artifact_order.npy``) so both can be compared.

APFD follows the artifact (``py/metric.py``): one ordering of the v1 test suite is scored
against every bug version at once; m = number of distinct bugs detected.

Usage
-----
    python -m hcfalcon.d4j.falcon_repro                       # all six projects, unixcoder, cosine
    python -m hcfalcon.d4j.falcon_repro --projects Chart Lang --transform clip
"""

from __future__ import annotations

import argparse
import csv
import json
import pickle
import time
from pathlib import Path

import numpy as np

from hcfalcon.similarity import euclidean_similarity, similarity_from_embeddings
from hcfalcon.submodular import lazy_greedy

ROOT = Path(__file__).resolve().parents[3]
PROJECTS = ["Chart", "Closure", "Lang", "Math", "Mockito", "Time"]

# FALCON paper, Table IV (UniXcoder + cosine) and best FAST variant per project.
PAPER_FALCON_APFD = {
    "Chart": 0.726, "Closure": 0.700, "Lang": 0.754,
    "Math": 0.622, "Mockito": 0.736, "Time": 0.794,
}
PAPER_FASTLOG_APFD = {
    "Chart": 0.637, "Closure": 0.626, "Lang": 0.529,
    "Math": 0.548, "Mockito": 0.664, "Time": 0.631,
}


def load_fault_matrix(path: Path) -> dict[int, list]:
    with open(path, "rb") as fh:
        raw = pickle.load(fh)
    return {int(k): list(v) for k, v in raw.items()}


def apfd_fault_matrix(order, faults: dict[int, list]) -> float:
    """Multi-fault APFD exactly as FALCON/FAST compute it (first detection position per bug)."""
    seen, numerator = set(), 0.0
    for pos, method in enumerate(order, start=1):
        for bug in faults.get(int(method), ()):
            if bug not in seen:
                seen.add(bug)
                numerator += pos
    n, m = len(order), len(seen)
    if m == 0:
        return 0.0
    return 1.0 - numerator / (n * m) + 1.0 / (2 * n)


def count_methods(bbox_file: Path) -> int:
    with open(bbox_file, encoding="utf-8", errors="replace") as fh:
        return sum(1 for line in fh if line.strip())


def order_agreement(a, b) -> dict:
    """How close two orders are: identical prefix length and Kendall-tau-like footrule."""
    a, b = np.asarray(a), np.asarray(b)
    same_prefix = int(np.argmax(a != b)) if (a != b).any() else len(a)
    pos_b = np.empty(len(b), dtype=np.int64)
    pos_b[b] = np.arange(len(b))
    footrule = float(np.abs(pos_b[a] - np.arange(len(a))).mean() / max(1, len(a)))
    return {"identical": bool((a == b).all()), "same_prefix": same_prefix, "norm_footrule": footrule}


def run_project(project, falcon_root: Path, emb_root: Path, model: str, metric: str, transform: str):
    inp = falcon_root / "input" / project
    emb_dir = emb_root / project
    emb_file = emb_dir / f"{model}_test_embeddings.npy"
    if not emb_file.exists():
        raise FileNotFoundError(f"{emb_file} missing: run notebooks/embed_colab.ipynb (mode a) first")
    emb = np.load(emb_file)
    n_methods = count_methods(inp / f"{project}-bbox.txt")
    if emb.shape[0] != n_methods:
        raise ValueError(f"{project}: {emb.shape[0]} embeddings vs {n_methods} test methods")
    faults = load_fault_matrix(inp / "fault_matrix.pickle")

    t0 = time.perf_counter()
    if metric == "cosine":
        sim = similarity_from_embeddings(emb, transform=transform)
    elif metric == "euclidean":
        sim = euclidean_similarity(emb).astype(np.float32)
    else:
        raise ValueError(metric)
    t_sim = time.perf_counter() - t0
    res = lazy_greedy(sim)
    t_rank = time.perf_counter() - t0 - t_sim

    row = {
        "project": project, "model": model, "metric": metric, "transform": transform,
        "n_methods": n_methods, "n_bugs": len({b for v in faults.values() for b in v}),
        "apfd": round(apfd_fault_matrix(res.order, faults), 4),
        "paper_falcon_apfd": PAPER_FALCON_APFD.get(project),
        "paper_fastlog_apfd": PAPER_FASTLOG_APFD.get(project),
        "sim_time_s": round(t_sim, 3), "rank_time_s": round(t_rank, 3),
        "n_gain_evals": res.n_gain_evals, "min_sim": float(sim.min()),
    }
    row["delta_vs_paper"] = (
        round(row["apfd"] - row["paper_falcon_apfd"], 4) if row["paper_falcon_apfd"] else None
    )

    art_order_file = emb_dir / "falcon_artifact_order.npy"
    if art_order_file.exists():
        art = np.load(art_order_file)
        row["artifact_apfd"] = round(apfd_fault_matrix(art, faults), 4)
        row.update({f"agree_{k}": v for k, v in order_agreement(res.order, art).items()})
    return row, res.order


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--projects", nargs="+", default=PROJECTS)
    ap.add_argument("--falcon-root", type=Path, default=ROOT / "external" / "falcon-icst-2026")
    ap.add_argument("--emb-root", type=Path, default=ROOT / "data" / "embeddings" / "d4j")
    ap.add_argument("--model", default="unixcoder")
    ap.add_argument("--metric", choices=["cosine", "euclidean"], default="cosine")
    ap.add_argument("--transform", choices=["none", "clip", "shift"], default="none",
                    help="'none' = raw cosine as in the FALCON artifact; 'clip' = HC-FALCON setting")
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "d4j")
    args = ap.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    rows = []
    for project in args.projects:
        row, order = run_project(project, args.falcon_root, args.emb_root, args.model,
                                 args.metric, args.transform)
        tag = f"{args.model}-{args.metric}-{args.transform}"
        np.save(args.out / f"{project}-{tag}-order.npy", order)
        rows.append(row)
        print(json.dumps(row))

    out_csv = args.out / f"falcon_repro-{args.model}-{args.metric}-{args.transform}.csv"
    keys = sorted({k for r in rows for k in r}, key=lambda k: (k != "project", k))
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)
    apfds = [r["apfd"] for r in rows]
    print(f"\nmedian APFD = {np.median(apfds):.3f} (paper FALCON median 0.731) -> {out_csv}")


if __name__ == "__main__":
    main()
