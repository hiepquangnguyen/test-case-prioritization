import numpy as np
import pytest

from hcfalcon.d4j.falcon_repro import apfd_fault_matrix, order_agreement


def test_apfd_fault_matrix_matches_hand_computation():
    # 5 methods; bug 1 found by m3 and m0, bug 2 by m4 -> order [3, 1, 4, 0, 2]
    faults = {0: [1], 3: [1], 4: [2]}
    order = [3, 1, 4, 0, 2]
    # bug1 first at pos 1, bug2 at pos 3: 1 - 4/(5*2) + 1/10
    assert apfd_fault_matrix(order, faults) == pytest.approx(0.7)


def test_apfd_fault_matrix_no_fault():
    assert apfd_fault_matrix([0, 1, 2], {}) == 0.0


def test_run_project_end_to_end_on_fake_artifact(tmp_path):
    import pickle

    from hcfalcon.d4j.falcon_repro import run_project

    falcon_root, emb_root = tmp_path / "falcon", tmp_path / "emb"
    inp = falcon_root / "input" / "Toy"
    (inp).mkdir(parents=True)
    (emb_root / "Toy").mkdir(parents=True)
    (inp / "Toy-bbox.txt").write_text("\n".join(f"void test{i}() {{}}" for i in range(6)) + "\n")
    with open(inp / "fault_matrix.pickle", "wb") as fh:
        pickle.dump({0: [1], 5: [2]}, fh)
    rng = np.random.default_rng(0)
    np.save(emb_root / "Toy" / "unixcoder_test_embeddings.npy", rng.normal(size=(6, 8)))
    np.save(emb_root / "Toy" / "falcon_artifact_order.npy", np.arange(6))

    row, order = run_project("Toy", falcon_root, emb_root, "unixcoder", "cosine", "clip")
    assert sorted(order.tolist()) == list(range(6))
    assert 0.0 < row["apfd"] <= 1.0 and row["n_bugs"] == 2 and row["min_sim"] >= 0
    assert "artifact_apfd" in row and "agree_identical" in row


def test_order_agreement():
    same = order_agreement([2, 0, 1], [2, 0, 1])
    assert same["identical"] and same["same_prefix"] == 3 and same["norm_footrule"] == 0.0
    diff = order_agreement(np.array([0, 1, 2, 3]), np.array([0, 2, 1, 3]))
    assert not diff["identical"] and diff["same_prefix"] == 1 and diff["norm_footrule"] > 0
