import numpy as np
import pandas as pd
import pytest

from hcfalcon.stats import cliffs_delta, delta_magnitude, holm, paired


def test_cliffs_delta_and_labels():
    assert cliffs_delta([3, 4, 5], [1, 2]) == 1.0
    assert cliffs_delta([1, 2], [3, 4, 5]) == -1.0
    assert cliffs_delta([1, 2, 3], [1, 2, 3]) == 0.0
    assert cliffs_delta([1, 3], [2]) == 0.0
    assert [delta_magnitude(x) for x in (0.1, -0.2, 0.4, 0.9)] == ["negligible", "small", "medium", "large"]


def test_holm_matches_definition():
    p = [0.01, 0.04, 0.03, 0.2]
    # sorted: .01*4=.04, .03*3=.09, .04*2=.08 -> max(.09,.08)=.09, .2*1=.2
    assert holm(p) == pytest.approx([0.04, 0.09, 0.09, 0.2])
    assert holm([0.5, 0.9]).max() <= 1.0


def test_paired_comparison():
    rng = np.random.default_rng(0)
    rows = []
    for i in range(40):
        base = rng.uniform(0.5, 0.8)
        for m, v in (("A", base + 0.05), ("B", base), ("C", base + rng.normal(0, 0.001))):
            rows.append({"project": "p", "stage": "s", "pr_name": f"P{i}", "build_id": 1, "dataset": "deconf",
                         "split": "eval", "method": m, "apfdc_u": v})
    res = paired(pd.DataFrame(rows), "A", ["B", "C"]).set_index("baseline")
    assert res.loc["B", "wins"] == 40 and res.loc["B", "significant"]
    assert res.loc["B", "median_paired_diff"] == pytest.approx(0.05)
    assert res.loc["B", "p_holm"] >= res.loc["B", "p"]
