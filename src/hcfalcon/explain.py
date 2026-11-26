"""Why each test got its position: the HC-FALCON explanation output required by ``topic1.md``.

For every selected test: position, total marginal gain, its semantic part ``alpha/n * dFL`` and its
history/cost part ``(1 - alpha) * q``, the estimates behind q (p, conf, cost), and the tests it newly
covered most (largest increase of their best similarity). Built from ``HCFalconPrioritizer.last``,
which needs ``explain_top > 0`` for the coverage lists.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def explanation_table(last: dict, k: int | None = None, outcome=None) -> pd.DataFrame:
    """One row per selected test (first ``k``). ``outcome`` (optional, aligned with ``last['names']``) adds
    the real result, which is known only after the run: for reading, never used for ranking."""
    res, names, est, q = last["result"], last["names"], last["est"], last["q"]
    alpha, n = last["alpha"], last["n"]
    k = len(res.order) if k is None else min(k, len(res.order))
    rows = []
    for pos in range(k):
        t = int(res.order[pos])
        sem = alpha / n * float(res.fl_gain[pos])
        covers = res.top_covered[pos] if pos < len(res.top_covered) else []
        rows.append({
            "position": pos + 1, "test": names[t], "gain": float(res.gain[pos]),
            "semantic_part": sem, "history_cost_part": float(res.gain[pos]) - sem,
            "p": float(est["p"][t]), "conf": float(est["conf"][t]), "cost_s": float(est["cost"][t]),
            "q": float(q[t]), "has_embedding": bool(last["found"][t]),
            "covers": "; ".join(f"{names[u].rsplit('.', 1)[-1]} (+{imp:.2f})" for u, imp in covers if u != t),
            **({"failed": int(outcome[t])} if outcome is not None else {}),
        })
    return pd.DataFrame(rows)


def describe(row) -> str:
    """One readable line per test."""
    short = row["test"].rsplit(".", 1)[-1]
    parts = [f"#{row['position']} {short}: gain {row['gain']:.4f} = semantic {row['semantic_part']:.4f}"
             f" + history/cost {row['history_cost_part']:.4f}",
             f"p={row['p']:.3f}, conf={row['conf']:.2f}, cost {row['cost_s']:.1f} s"]
    if not row["has_embedding"]:
        parts.append("no source (isolated)")
    if row.get("covers"):
        parts.append(f"newly covers {row['covers']}")
    if "failed" in row and not pd.isna(row["failed"]):
        parts.append("FAILED in this run" if row["failed"] else "passed")
    return " | ".join(parts)


def render(table: pd.DataFrame, header: str = "") -> str:
    lines = [header] if header else []
    lines += [describe(r) for r in table.to_dict("records")]
    return "\n".join(lines)


def share_semantic(last: dict, k: int = 10) -> float:
    """Fraction of the first ``k`` gains that came from the semantic part (diagnostic)."""
    t = explanation_table(last, k)
    tot = t["gain"].sum()
    return float(t["semantic_part"].sum() / tot) if tot > 0 else float("nan")
