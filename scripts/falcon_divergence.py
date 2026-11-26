"""Why our lazy-greedy order differs from the FALCON artifact's, and how much it matters.

1. Divergence: at the first position where the two orders differ, compute (in float64) the exact
   marginal gain of both picks given the common prefix. A gap far below 1e-4 means a near-tie that
   the artifact's float32 GPU sums and its ``exact >= max - 1e-6`` acceptance rule break differently.
2. Objective: FL value of both prefixes at several lengths (ours should never be lower by more than
   float noise; greedy is exact here).
3. Sensitivity: rerun our greedy on sim + symmetric N(0, sigma^2) noise (sigma = 1e-6, the artifact's
   tolerance) for 10 seeds and report the APFD spread. If the spread is as wide as the gap between
   our APFD and the artifact's, that gap is tie-breaking noise, not an implementation error.

    python scripts/falcon_divergence.py  ->  results/d4j/falcon_divergence.csv
"""

from pathlib import Path

import numpy as np
import pandas as pd

from hcfalcon.d4j.falcon_repro import PROJECTS, apfd_fault_matrix, load_fault_matrix
from hcfalcon.similarity import cosine_matrix, l2_normalize
from hcfalcon.submodular import fl_value, lazy_greedy

ROOT = Path(__file__).resolve().parents[1]
EMB = ROOT / "data" / "embeddings" / "d4j"
FALCON = ROOT / "external" / "falcon-icst-2026" / "input"
OURS = ROOT / "results" / "d4j"
SIGMA, SEEDS = 1e-6, 10


def gain(sim, cur, t):
    col = sim[:, t]
    return col.sum() if cur is None else np.maximum(col - cur, 0).sum()


def main():
    rows = []
    for p in PROJECTS:
        emb = np.load(EMB / p / "unixcoder_test_embeddings.npy").astype(np.float64)
        sim = cosine_matrix(l2_normalize(emb))
        faults = load_fault_matrix(FALCON / p / "fault_matrix.pickle")
        art = np.load(EMB / p / "falcon_artifact_order.npy")
        ours = np.load(OURS / f"{p}-unixcoder-cosine-none-order.npy")

        k = int(np.argmax(art != ours)) if (art != ours).any() else len(art)
        cur = sim[:, art[:k]].max(axis=1) if k else None
        g_ours, g_art = gain(sim, cur, ours[k]), gain(sim, cur, art[k])
        g_top = max(gain(sim, cur, t) for t in set(range(len(art))) - set(art[:k].tolist()))

        lens = [100, 500, 1000, len(art) // 2]
        fl_gap = {f"fl_gap@{m}": fl_value(sim, ours[:m]) - fl_value(sim, art[:m]) for m in lens}

        noisy = []
        for s in range(SEEDS):
            rng = np.random.default_rng(s)
            e = rng.normal(scale=SIGMA, size=sim.shape)
            noisy.append(apfd_fault_matrix(lazy_greedy((sim + (e + e.T) / 2).astype(np.float32)).order, faults))

        row = {
            "project": p, "first_diff_pos": k,
            "gain_ours": g_ours, "gain_artifact": g_art, "gain_best": g_top,
            "gap_artifact_vs_best": g_top - g_art,
            "apfd_ours": apfd_fault_matrix(ours, faults), "apfd_artifact": apfd_fault_matrix(art, faults),
            "apfd_noise_min": min(noisy), "apfd_noise_median": float(np.median(noisy)),
            "apfd_noise_max": max(noisy), **fl_gap,
        }
        rows.append(row)
        print({key: (round(v, 7) if isinstance(v, float) else v) for key, v in row.items()})

    df = pd.DataFrame(rows)
    out = OURS / "falcon_divergence.csv"
    df.to_csv(out, index=False)
    print(f"median APFD  ours {df.apfd_ours.median():.4f}  artifact {df.apfd_artifact.median():.4f}  "
          f"noise-median {df.apfd_noise_median.median():.4f}  -> {out}")


if __name__ == "__main__":
    main()
