"""Paired comparisons of prioritizers over the same TSRs (protocol §4).

- Wilcoxon signed-rank test on per-TSR metric values, two-sided, zero differences dropped (``wilcox``);
- Holm-Bonferroni correction over a family of comparisons;
- Cliff's delta between the two samples of per-TSR values, with the usual magnitude labels
  (|d| < 0.147 negligible, < 0.33 small, < 0.474 medium, else large; Romano et al. 2006);
- the median of paired differences and the relative change of the medians (the pilot threshold of
  ``topic1.md`` is a 3-5% median improvement).

Stochastic methods are averaged over seeds per TSR before testing (``rolling`` already does this).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

KEY = ["project", "stage", "pr_name", "build_id"]


def cliffs_delta(a, b) -> float:
    """P(a > b) - P(a < b) over all pairs."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) == 0 or len(b) == 0:
        return float("nan")
    diff = a[:, None] - b[None, :]
    return float((np.sign(diff)).mean())


def delta_magnitude(d: float) -> str:
    d = abs(d)
    if np.isnan(d):
        return "n/a"
    return "negligible" if d < 0.147 else "small" if d < 0.33 else "medium" if d < 0.474 else "large"


def holm(pvalues) -> np.ndarray:
    """Holm-adjusted p-values (monotone, capped at 1)."""
    p = np.asarray(pvalues, float)
    m = len(p)
    order = np.argsort(p)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * p[i])
        adj[i] = min(1.0, running)
    return adj


def paired(raw: pd.DataFrame, method: str, baselines, metric: str = "apfdc_u", dataset: str = "deconf",
           split: str | None = "eval") -> pd.DataFrame:
    """``method`` vs each baseline on the TSRs where both were scored; Holm over the baselines."""
    df = raw[raw["dataset"] == dataset]
    if split is not None:
        df = df[df["split"] == split]
    wide = df.pivot_table(index=KEY, columns="method", values=metric, aggfunc="mean")
    rows = []
    for b in baselines:
        sub = wide[[method, b]].dropna()
        x, y = sub[method].to_numpy(), sub[b].to_numpy()
        d = x - y
        if len(d) == 0 or np.allclose(d, 0):
            p = 1.0
        else:
            p = float(wilcoxon(x, y, zero_method="wilcox", alternative="two-sided").pvalue)
        cd = cliffs_delta(x, y)
        med_x, med_y = float(np.median(x)), float(np.median(y))
        rows.append({
            "method": method, "baseline": b, "n_tsr": len(d), f"mean_{metric}": float(x.mean()),
            f"baseline_mean_{metric}": float(y.mean()), "median": med_x, "baseline_median": med_y,
            "median_rel_change": med_x / med_y - 1 if med_y > 0 else float("nan"),
            "median_paired_diff": float(np.median(d)), "wins": int((d > 0).sum()), "losses": int((d < 0).sum()),
            "p": p, "cliffs_delta": cd, "magnitude": delta_magnitude(cd),
        })
    out = pd.DataFrame(rows)
    if len(out):
        out["p_holm"] = holm(out["p"])
        out["significant"] = out["p_holm"] < 0.05
    return out
