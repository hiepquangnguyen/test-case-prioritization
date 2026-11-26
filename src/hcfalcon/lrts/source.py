"""Test-class source code at the exact commit of each LRTS build, read from a bare git clone.

No working tree is checked out:
- ``git ls-tree -r <commit>`` gives (path, blob SHA) of every test file;
- the blob SHA identifies one version of a file, so each version is parsed and embedded once across the
  whole history;
- ``git cat-file --batch`` reads blob contents.

The commit is ``build_head_sha`` (the PR head Jenkins built). PR heads that were later force-pushed are
no longer on ``refs/pull/*/head``, but GitHub still serves them by SHA (``ensure_commits``). Only if that
fails does a build fall back to ``trunk_sha``; the share is reported. Testing the PR head instead of the
merge commit Jenkins actually ran is an approximation (threats to validity).

Clone once (ask before downloading)::

    git clone --bare https://github.com/apache/<repo>.git data/repos/<project>.git
    git -C data/repos/<project>.git fetch origin "+refs/pull/*/head:refs/pull/*/head"
"""

from __future__ import annotations

import subprocess
from collections import defaultdict
from pathlib import Path

from hcfalcon.lrts.loader import ROOT

REPOS = ROOT / "data" / "repos"
GITHUB = {
    "activemq": "apache/activemq",
    "jackrabbit-oak": "apache/jackrabbit-oak",
    "hbase": "apache/hbase",
    "hadoop": "apache/hadoop",
    "karaf": "apache/karaf",
}
TEST_ROOTS = ("src/test/java/", "src/test/")


def repo_path(project: str) -> Path:
    return REPOS / f"{project}.git"


def git(repo: Path, *args: str, input: bytes | None = None) -> bytes:
    p = subprocess.run(["git", "-C", str(repo), *args], input=input, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:3])} failed: {p.stderr.decode('utf-8', 'replace').strip()}")
    return p.stdout


def missing_commits(repo: Path, shas) -> list[str]:
    shas = [s for s in dict.fromkeys(shas) if isinstance(s, str) and s]
    if not shas:
        return []
    out = git(repo, "cat-file", "--batch-check", input="\n".join(f"{s}^{{commit}}" for s in shas).encode())
    return [s for s, line in zip(shas, out.splitlines()) if line.endswith(b" missing")]


def ensure_commits(repo: Path, shas, remote: str = "origin", batch: int = 40) -> list[str]:
    """Fetch commits that are not in the clone by SHA. Returns those still missing."""
    todo = missing_commits(repo, shas)
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        p = subprocess.run(["git", "-C", str(repo), "fetch", "--quiet", remote, *chunk], capture_output=True)
        if p.returncode != 0:  # one unknown SHA fails the whole batch: retry one by one
            for s in chunk:
                subprocess.run(["git", "-C", str(repo), "fetch", "--quiet", remote, s], capture_output=True)
    return missing_commits(repo, todo)


def path_to_class(path: str) -> str | None:
    """'mod/src/test/java/a/b/FooTest.java' -> 'a.b.FooTest' (None if not a Java test source)."""
    if not path.endswith(".java"):
        return None
    p = "/" + path
    for root in TEST_ROOTS:
        k = p.rfind("/" + root)
        if k >= 0:
            return p[k + len(root) + 1:-len(".java")].replace("/", ".")
    return None


def list_test_files(repo: Path, commit: str) -> dict[str, list[tuple[str, str]]]:
    """Fully qualified class name -> [(path, blob sha), ...] for every test source file at ``commit``.
    The same class name can exist in several modules, hence a list."""
    out = git(repo, "ls-tree", "-r", "-z", "--full-tree", commit)
    files = defaultdict(list)
    for entry in out.split(b"\0"):
        if not entry:
            continue
        meta, path = entry.split(b"\t", 1)
        _, kind, blob = meta.split()
        if kind != b"blob":
            continue
        path = path.decode("utf-8", "replace")
        cls = path_to_class(path)
        if cls is not None:
            files[cls].append((path, blob.decode()))
    for v in files.values():
        v.sort()
    return dict(files)


def class_of_test(testclass: str) -> str:
    """LRTS test name -> top-level class whose file holds it ('a.B$Inner' -> 'a.B')."""
    return testclass.split("$", 1)[0]


def read_blobs(repo: Path, blobs) -> dict[str, bytes]:
    """Contents of the given blob SHAs via one ``git cat-file --batch`` call."""
    blobs = list(dict.fromkeys(blobs))
    if not blobs:
        return {}
    out = git(repo, "cat-file", "--batch", input=("\n".join(blobs) + "\n").encode())
    res, pos = {}, 0
    for b in blobs:
        nl = out.index(b"\n", pos)
        header = out[pos:nl].split()
        if header[-1] == b"missing":
            pos = nl + 1
            continue
        size = int(header[2])
        res[b] = out[nl + 1:nl + 1 + size]
        pos = nl + 1 + size + 1  # content is followed by a newline
    return res
