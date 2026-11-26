import numpy as np
import pandas as pd
import pytest

from hcfalcon.lrts.filters import _split_flaky, compute_labels, freqfail_outliers, label_run
from hcfalcon.lrts.loader import ARTIFACT, DATA


def test_split_flaky():
    assert _split_flaky("FooTest#testBar") == ["FooTest", "testBar"]
    assert _split_flaky("testBar[1]") == [None, "testBar[1]"]
    assert _split_flaky("FooTest") == ["FooTest", None]


def test_freqfail_outliers_rule():
    counts = {f"T{i}": 1 for i in range(30)} | {"HOT": 40}
    assert freqfail_outliers(counts) == {"HOT"}
    assert freqfail_outliers({"ONLY": 9}) == set()  # std undefined -> no outlier, as in LRTS
    assert freqfail_outliers({}) == set()


def test_label_run_semantics():
    names = np.array(["x.FooTest", "x.BarTest", "x.BazTest", "x.QuxTest"])
    outcome = np.array([1, 1, 0, 0])
    last = np.array([0, 1, 1, 0])
    lab = label_run(names, outcome, last, jira=["FooTest"], common=["x.BarTest"], prev_common=[],
                    frequent=["BazTest", "QuxTest"])
    assert lab["jira"].tolist() == [1, 0, 0, 0]        # suffix match, failed
    assert lab["freqfail"].tolist() == [0, 0, 1, 0]    # Baz transitioned; Qux neither failed nor changed
    assert lab["stageunique"].tolist() == [1, 0, 0, 0]  # Bar failed in every stage


def _write(root, project, pr, build, stage, rows):
    d = root / "processed_test_result" / project / f"{pr}_build{build}" / f"stage_{stage}"
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=["testclass", "duration", "outcome", "last_outcome"]).to_csv(
        d / "test_class.csv.zip", index=False)


def test_compute_labels_end_to_end(tmp_path):
    # build 1 (t=100): stages s1, s2; A fails in both, B only in s1.  build 2 (t=200): A fails again in s1.
    _write(tmp_path, "p", "PR-1", 1, "s1", [["p.A", 1, 1, 0], ["p.B", 1, 1, 0], ["p.C", 1, 0, 0]])
    _write(tmp_path, "p", "PR-1", 1, "s2", [["p.A", 1, 1, 0], ["p.B", 1, 0, 0]])
    _write(tmp_path, "p", "PR-1", 2, "s1", [["p.A", 1, 1, 1], ["p.B", 1, 0, 1], ["p.C", 1, 0, 0]])
    index = pd.DataFrame({"project": "p", "pr_name": "PR-1", "build_id": [1, 1, 2], "stage_id": ["s1", "s2", "s1"],
                          "build_timestamp": [100.0, 100.0, 200.0]})
    flaky = tmp_path / "flaky.csv"
    pd.DataFrame({"project": ["p"], "flaky_test": ["B"], "url": ["u"], "fix_date": ["d"],
                  "fix_timestamp": [150.0], "inspection_source": ["title"]}).to_csv(flaky, index=False)

    lab = compute_labels(index, data_root=tmp_path, flaky_csv=flaky)
    b1s1, b1s2, b2s1 = ("PR-1", 1, "s1"), ("PR-1", 1, "s2"), ("PR-1", 2, "s1")
    assert lab.by_filter[b1s1]["stageunique"] == {"p.B"}      # B failed in s1 only
    assert lab.by_filter[b1s1]["jira"] == {"p.B"}             # fixed at 150 > 100
    assert lab.by_filter[b2s1]["jira"] == frozenset()         # B transitioned, but fixed before t=200
    assert lab.by_filter[b1s1]["first"] == frozenset()        # first failures of A and B in s1
    assert lab.by_filter[b2s1]["first"] == {"p.A"}            # A already failed in s1
    assert lab.by_filter[b1s2]["first"] == frozenset()        # stages are tracked separately
    assert lab.exclusion(*b1s1, "deconf") == {"p.B"}
    assert lab.scored(*b1s1, "deconf") and not lab.scored(*b2s1, "firstfail")
    assert lab.scored(*b2s1, "all")


@pytest.mark.external
def test_labels_match_lrts_metadata_on_activemq():
    if not (DATA / "processed_test_result" / "activemq").exists() or not ARTIFACT.exists():
        pytest.skip("processed LRTS or LRTS artifact not available")
    from hcfalcon.lrts.filters import validate_against_artifact
    from hcfalcon.lrts.loader import load_filter_index, load_index

    lab = compute_labels(load_index("artifact", "activemq"))
    v = validate_against_artifact("activemq", lab, load_filter_index())
    assert v["n_tsr"].iloc[0] == 207 and (v["match"] == 1.0).all()
    assert sum(lab.scored(*k, "deconf") for k in lab.failed) == 96
    assert sum(lab.scored(*k, "firstfail") for k in lab.failed) == 43
