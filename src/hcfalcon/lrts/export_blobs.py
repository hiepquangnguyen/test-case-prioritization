"""Map every (TSR, test class) of an LRTS project to source-file versions and export the texts to embed.

    python -m hcfalcon.lrts.export_blobs --project activemq [--index drive]

Outputs (all under ``data/``, gitignored):

- ``lrts/source/<project>/tsr_tests.csv.gz``: one row per (TSR, test class): where the class file was
  found (``head`` = PR head, ``trunk`` = target branch at build time, ``none``), that commit, and the
  blob(s) of the file (';'-separated when the class name exists in several modules);
- ``lrts/source/<project>/blobs.jsonl.gz``: per blob, its path, what was embedded (test / all / file),
  parse errors, and the ids of its method texts;
- ``lrts/corpus/<project>_methods.jsonl.gz``: unique method texts ``{"id", "text"}``. Upload this
  file to Colab (``notebooks/embed_colab.ipynb``, mode b);
- ``lrts/source/<project>/summary.json``: coverage and counts.

The Drive index (superset) is the default so the embeddings cover both TSR sets.
"""

from __future__ import annotations

import argparse
import gzip
import json
import time
from collections import Counter

import pandas as pd

from hcfalcon.lrts.java_parse import parse_java, select_methods, text_id
from hcfalcon.lrts.loader import DATA, ROOT, load_index, read_tsr
from hcfalcon.lrts.source import (class_of_test, ensure_commits, list_test_files, missing_commits, read_blobs,
                                  repo_path)

OUT = ROOT / "data" / "lrts"


def resolve_commits(repo, index: pd.DataFrame, fetch: bool = True) -> dict:
    """(pr_name, build_id) -> (head commit or None, trunk commit or None), only commits present in the clone.

    Jenkins tests the merge of the PR into the target branch, so a class may be missing at the PR head
    (added to trunk after the PR branched off). Lookup order per class: head, then trunk."""
    wanted = list(index["build_head_sha"].dropna().unique()) + list(index["trunk_sha"].dropna().unique())
    still = set(ensure_commits(repo, wanted) if fetch else missing_commits(repo, wanted))

    def ok(s):
        return s if isinstance(s, str) and s and s not in still else None

    return {(r.pr_name, int(r.build_id)): (ok(r.build_head_sha), ok(r.trunk_sha))
            for r in index.drop_duplicates(["pr_name", "build_id"]).itertuples()}


def export(project: str, index_source: str = "drive", fetch: bool = True, data_root=DATA,
           index: pd.DataFrame | None = None, repo=None, out=OUT) -> dict:
    t0 = time.time()
    repo = repo_path(project) if repo is None else repo
    if not repo.exists():
        raise FileNotFoundError(f"{repo} missing: clone it first (see hcfalcon.lrts.source docstring)")
    index = load_index(index_source, project) if index is None else index
    commits = resolve_commits(repo, index, fetch=fetch)

    trees = {}

    def tree(commit):
        if commit is None:
            return {}
        if commit not in trees:
            trees[commit] = list_test_files(repo, commit)
        return trees[commit]

    rows = []
    for r in index.itertuples():
        head, trunk = commits[(r.pr_name, int(r.build_id))]
        run = read_tsr(project, r.pr_name, int(r.build_id), str(r.stage_id), data_root)
        for t in run.names:
            cls = class_of_test(t)
            cands, commit, origin = tree(head).get(cls, []), head, "head"
            if not cands:
                cands, commit, origin = tree(trunk).get(cls, []), trunk, "trunk"
            if not cands:
                commit, origin = None, "none"
            rows.append((r.pr_name, int(r.build_id), str(r.stage_id), t, commit, origin,
                         ";".join(b for _, b in cands), len(cands)))
    tests = pd.DataFrame(rows, columns=["pr_name", "build_id", "stage_id", "testclass", "commit", "source",
                                        "blobs", "n_candidates"])

    blob_paths = {}
    for commit_files in trees.values():
        for cands in commit_files.values():
            for path, b in cands:
                blob_paths.setdefault(b, path)
    needed = sorted({b for s in tests["blobs"] if s for b in s.split(";")})
    contents = read_blobs(repo, needed)

    methods, blob_rows, kinds = {}, [], Counter()
    for b in needed:
        src = contents.get(b)
        if src is None:
            continue
        parsed = parse_java(src)
        kind, texts = select_methods(parsed, src)
        ids = []
        for txt in texts:
            i = text_id(txt)
            methods.setdefault(i, txt)
            ids.append(i)
        kinds[kind] += 1
        blob_rows.append({"blob": b, "path": blob_paths.get(b), "kind": kind, "has_error": parsed.has_error,
                          "n_methods": len(ids), "method_ids": ids})

    src_dir = out / "source" / project
    corpus_dir = out / "corpus"
    src_dir.mkdir(parents=True, exist_ok=True)
    corpus_dir.mkdir(parents=True, exist_ok=True)
    tests.to_csv(src_dir / "tsr_tests.csv.gz", index=False)
    with gzip.open(src_dir / "blobs.jsonl.gz", "wt", encoding="utf-8") as fh:
        for row in blob_rows:
            fh.write(json.dumps(row) + "\n")
    with gzip.open(corpus_dir / f"{project}_methods.jsonl.gz", "wt", encoding="utf-8") as fh:
        for i, txt in methods.items():
            fh.write(json.dumps({"id": i, "text": txt}) + "\n")

    per_tsr = tests.assign(found=tests["n_candidates"] > 0).groupby(["pr_name", "build_id", "stage_id"])["found"].mean()
    summary = {
        "project": project, "index": index_source, "n_tsr": int(len(index)), "n_builds": len(commits),
        "builds_without_head": int(sum(h is None for h, _ in commits.values())),
        "builds_without_any_commit": int(sum(h is None and t is None for h, t in commits.values())),
        "n_test_rows": int(len(tests)),
        "row_source": {k: round(float(v), 4) for k, v in tests["source"].value_counts(normalize=True).items()},
        "coverage_rows": round(float((tests["n_candidates"] > 0).mean()), 4),
        "coverage_tsr_min": round(float(per_tsr.min()), 4),
        "coverage_tsr_median": round(float(per_tsr.median()), 4),
        "tsr_below_95pct": int((per_tsr < 0.95).sum()),
        "ambiguous_rows": round(float((tests["n_candidates"] > 1).mean()), 4),
        "n_commits": len(trees), "n_blobs": len(blob_rows), "blob_kind": dict(kinds),
        "blobs_with_parse_error": int(sum(r["has_error"] for r in blob_rows)),
        "n_unique_methods": len(methods),
        "corpus_chars": int(sum(len(t) for t in methods.values())),
        "unmatched_examples": tests.loc[tests["n_candidates"] == 0, "testclass"].drop_duplicates().head(15).tolist(),
        "seconds": round(time.time() - t0, 1),
    }
    with open(src_dir / "summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--index", choices=["drive", "artifact"], default="drive")
    ap.add_argument("--no-fetch", action="store_true", help="do not fetch missing commits from GitHub")
    args = ap.parse_args(argv)
    print(json.dumps(export(args.project, args.index, fetch=not args.no_fetch), indent=2))


if __name__ == "__main__":
    main()
