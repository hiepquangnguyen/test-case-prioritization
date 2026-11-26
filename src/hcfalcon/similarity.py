"""Turn test embeddings into a non-negative similarity matrix for facility location.

Facility location is monotone submodular with F(empty) = 0 only when every similarity is
non-negative, so raw cosine (which can be negative) must be transformed first:

* ``"clip"``  -> max(0, cos)         (default for HC-FALCON)
* ``"shift"`` -> (1 + cos) / 2       (sensitivity analysis)
* ``"none"``  -> raw cos             (only to reproduce the FALCON artifact, which does not clip;
                                      the (1 - 1/e) guarantee does not hold in that mode)
"""

from __future__ import annotations

import numpy as np

SIM_TRANSFORMS = ("clip", "shift", "none")


def l2_normalize(emb: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    """Row-wise L2 normalisation. All-zero rows stay all-zero."""
    emb = np.asarray(emb, dtype=np.float64)
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    return emb / np.maximum(norms, eps)


def cosine_matrix(emb: np.ndarray) -> np.ndarray:
    """Pairwise cosine similarity, shape (n, n), float64."""
    x = l2_normalize(emb)
    cos = x @ x.T
    return np.clip(cos, -1.0, 1.0)


def euclidean_similarity(emb: np.ndarray) -> np.ndarray:
    """FALCON's Euclidean variant: 1 / (1 + ||a - b||). Always in (0, 1]."""
    emb = np.asarray(emb, dtype=np.float64)
    sq = np.sum(emb * emb, axis=1)
    d2 = np.maximum(sq[:, None] + sq[None, :] - 2.0 * (emb @ emb.T), 0.0)
    return 1.0 / (1.0 + np.sqrt(d2))


def transform_cosine(cos: np.ndarray, transform: str = "clip") -> np.ndarray:
    if transform == "clip":
        return np.maximum(cos, 0.0)
    if transform == "shift":
        return (1.0 + cos) / 2.0
    if transform == "none":
        return cos
    raise ValueError(f"unknown sim transform {transform!r}; expected one of {SIM_TRANSFORMS}")


def isolate(sim: np.ndarray, missing: np.ndarray) -> np.ndarray:
    """Give tests without an embedding zero similarity to every other test, self-similarity 1.

    Such a test only "covers itself", so facility location neither favours nor penalises it
    beyond its own coverage of 1 (scaled by alpha / n).
    """
    missing = np.asarray(missing, dtype=bool)
    if not missing.any():
        return sim
    sim = sim.copy()
    sim[missing, :] = 0.0
    sim[:, missing] = 0.0
    idx = np.flatnonzero(missing)
    sim[idx, idx] = 1.0
    return sim


def similarity_from_embeddings(
    emb: np.ndarray,
    transform: str = "clip",
    missing: np.ndarray | None = None,
    dtype=np.float32,
) -> np.ndarray:
    """Embeddings (n, d) -> similarity matrix (n, n) ready for :mod:`hcfalcon.submodular`."""
    sim = transform_cosine(cosine_matrix(emb), transform)
    if missing is not None:
        sim = isolate(sim, missing)
    return np.ascontiguousarray(sim, dtype=dtype)
