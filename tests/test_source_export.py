import gzip
import json
import subprocess

import numpy as np
import pandas as pd
import pytest

from hcfalcon.lrts.source import class_of_test, list_test_files, missing_commits, path_to_class, read_blobs


def test_path_to_class():
    assert path_to_class("activemq-broker/src/test/java/org/a/FooTest.java") == "org.a.FooTest"
    assert path_to_class("src/test/java/org/a/FooTest.java") == "org.a.FooTest"
    assert path_to_class("legacy/src/test/org/a/FooTest.java") == "org.a.FooTest"
    assert path_to_class("mod/src/main/java/org/a/Foo.java") is None
    assert path_to_class("mod/src/test/resources/a.xml") is None
    assert class_of_test("org.a.FooTest$Inner") == "org.a.FooTest"


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


FOO_V1 = "package a; public class FooTest { @Test public void testA() { int x = 1; } }"
FOO_V2 = "package a; public class FooTest { @Test public void testA() { int x = 1; } @Test public void testB() {} }"
BAR = "package a; public class BarTest extends Base { void helper() {} }"


@pytest.fixture
def toy_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")

    def commit(files, msg):
        for path, text in files.items():
            p = repo / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", msg)
        return git(repo, "rev-parse", "HEAD")

    c1 = commit({"m1/src/test/java/a/FooTest.java": FOO_V1, "m1/src/main/java/a/Foo.java": "class Foo {}"}, "c1")
    c2 = commit({"m1/src/test/java/a/FooTest.java": FOO_V2, "m2/src/test/java/a/BarTest.java": BAR}, "c2")
    return repo, c1, c2


def test_ls_tree_and_cat_file(toy_repo):
    repo, c1, c2 = toy_repo
    f1, f2 = list_test_files(repo, c1), list_test_files(repo, c2)
    assert set(f1) == {"a.FooTest"} and set(f2) == {"a.FooTest", "a.BarTest"}
    (_, b1), = f1["a.FooTest"]
    (_, b2), = f2["a.FooTest"]
    assert b1 != b2
    assert read_blobs(repo, [b1, b2]) == {b1: FOO_V1.encode(), b2: FOO_V2.encode()}
    assert missing_commits(repo, [c1, "0" * 40]) == ["0" * 40]


def _write_tsr(root, project, pr, build, stage, names):
    d = root / "processed_test_result" / project / f"{pr}_build{build}" / f"stage_{stage}"
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"testclass": names, "duration": 1.0, "outcome": 0, "last_outcome": 0}).to_csv(
        d / "test_class.csv.zip", index=False)


def test_export_and_tsr_vectors_end_to_end(toy_repo, tmp_path):
    from hcfalcon.lrts.embeddings import TSRVectors
    from hcfalcon.lrts.export_blobs import export

    repo, c1, c2 = toy_repo
    data = tmp_path / "lrts"
    # PR-1 head = c1, but BarTest (added on trunk later) must come from trunk = c2; PR-2 head = c2
    _write_tsr(data, "p", "PR-1", 1, "s", ["a.FooTest", "a.BarTest$Inner", "ext.JarTest"])
    _write_tsr(data, "p", "PR-2", 1, "s", ["a.FooTest", "a.BarTest"])
    index = pd.DataFrame({"project": "p", "pr_name": ["PR-1", "PR-2"], "build_id": [1, 1], "stage_id": ["s", "s"],
                          "build_timestamp": [1.0, 2.0], "build_head_sha": [c1, c2], "trunk_sha": [c2, c2]})
    out = tmp_path / "out"
    s = export("p", fetch=False, data_root=data, index=index, repo=repo, out=out)
    assert s["coverage_rows"] == pytest.approx(4 / 5) and s["n_blobs"] == 3
    assert s["blob_kind"] == {"test": 2, "all": 1}
    assert s["n_unique_methods"] == 3  # testA is identical in both FooTest versions

    tests = pd.read_csv(out / "source" / "p" / "tsr_tests.csv.gz", keep_default_na=False)
    src = dict(zip(zip(tests.pr_name, tests.testclass), tests.source))
    assert src[("PR-1", "a.FooTest")] == "head" and src[("PR-1", "a.BarTest$Inner")] == "trunk"
    assert src[("PR-1", "ext.JarTest")] == "none"

    with gzip.open(out / "corpus" / "p_methods.jsonl.gz", "rt") as fh:
        ids = [json.loads(line)["id"] for line in fh]
    emb_root = tmp_path / "emb"
    (emb_root / "p").mkdir(parents=True)
    vecs = np.eye(len(ids), 4, dtype=np.float16)
    np.savez(emb_root / "p" / "unixcoder_methods.npz", ids=np.array(ids), vectors=vecs)

    tv = TSRVectors("p", source_root=out / "source", emb_root=emb_root)
    emb, found = tv.get("PR-1", 1, "s", ["a.FooTest", "a.BarTest$Inner", "ext.JarTest", "not.InTSR"])
    assert found.tolist() == [True, True, False, False]
    assert np.allclose(emb[2:], 0) and np.linalg.norm(emb[0]) > 0
    emb2, _ = tv.get("PR-2", 1, "s", ["a.FooTest"])
    assert not np.allclose(emb[0], emb2[0])  # FooTest v1 (1 method) vs v2 (2 methods)
    cov = tv.coverage().set_index("pr_name").emb_coverage
    assert cov["PR-1"] == pytest.approx(2 / 3) and cov["PR-2"] == 1.0
