# Formal Amendment: Clean Clone Reproducibility & Packaging

- **Version**: `clean-clone-amendment-v3`
- **Supersedes**: `clean-clone-amendment-v2`
- **Scope**: `documentation_and_packaging_only`
- **Scientific Results Changed**: `false`
- **Reserved Opened**: `false`

## Context & Rationale

Independent validation from a fresh Windows clone exposed a line-ending mismatch in the first amendment. Historical evidence manifests were created from working-tree bytes: source and configuration files were frozen with LF, while 107 legacy report and documentation files were frozen with CRLF. A global `eol=lf` rule therefore changed those evidence bytes during clean checkout and caused valid SHA-256 freezes to fail.

The checkout policy established by the second amendment remains in force. This
third amendment records a documentation-only restructuring and verifier state
transition:

1. The retired seven-file `topic1-reading-guide/` is replaced by exactly two
   foundation documents: one for understanding the problem and one for the
   algorithms, formulas, and theory.
2. The new documents are grounded in `topic1.md` and the two original FALCON
   and DANTE papers, and are kept separate from Stage 1–12 experimental results.
3. Stale and machine-local documentation links are replaced with portable
   relative links.
4. The verifier accepts both the preregistered Stage 12 Phase A state and the
   evaluated Phase B state, while recomputing the decision, checking frozen
   hashes, and requiring the Reserved Confirmation dataset to remain sealed.

The second amendment:
1. Retains LF as the repository default for source, configuration, and current documentation.
2. Assigns CRLF only to the legacy report and documentation paths whose existing freeze hashes require it.
3. Keeps binary evidence exempt from text conversion.
4. Preserves the LF exception for `reports/stage10/smoke-chart16.json`.
5. Adds regression coverage for both Git attributes and canonical byte hashes.

No historical freeze hash is rewritten. The rules make checkout bytes conform to the already-recorded manifests on every platform.

The packaging and bootstrap changes introduced by `clean-clone-amendment-v1` remain in force: editable installation uses `pyproject.toml`, and `scripts/bootstrap_falcon.py` validates the pinned archive size, SHA-256, extraction whitelist, and Zip Slip safety.

Because `README.md` was originally recorded under `reports/stage6/final-evidence-freeze.json`, this formal cryptographic amendment records the complete SHA-256 lineage of `README.md` without modifying historical freeze manifests.

## Cryptographic Lineage of `README.md`

| Milestone | Git / Source Reference | SHA-256 Checksum |
| :--- | :--- | :--- |
| **Stage 6 Frozen** | `reports/stage6/final-evidence-freeze.json` | `315ba017c2c51a06614fd45d3e6c881b4e68480907c0b8998557d34a8633d2fe` |
| **Pre-Clean-Clone** | `HEAD:README.md` | `4c05d7c6e2e0f3f8536b5d22e6e17326bbf4043544b0cf7e99c26ff934089262` |
| **Clean-Clone Amendment v2** | `README.md` | `0886eb8adfde2a9c9246fc12f57e6d4309813ec8fe7ccedcf7c1e339f4607a93` |
| **Current Working Tree (v3)** | `README.md` | `21373dbae8c4e1ea0391bc1776ff032215cefa983a0a043f4d0b783bf6925564` |

## Non-Impact Assertion

We formally assert that:
- All scientific evaluations, benchmarks, and APFDc metrics remain completely unaltered.
- The HC-FALCON Effect Gate outcome on LRTS remains `NO-GO 0/3`.
- The CNS-Greedy evaluation and diagnostic results are unchanged.
- The Reserved Confirmation dataset remains strictly unopened (`reserved_opened: false`).
- Historical freeze manifests (`reports/stage*/evidence-freeze.json`) are completely untouched.

## Line-Ending Policy

- Default text checkout: LF.
- Frozen legacy report data: CRLF where explicitly listed by `.gitattributes`.
- Six frozen legacy Markdown reports: CRLF.
- Python source, versioned configurations, README, and all other current text: LF.
- Binary formats such as GZip, PDF, ZIP, NumPy, images, and pickle: no text conversion.

## Scope of v3 File Modifications

The v3 changes are restricted to documentation structure, portable links,
Stage 12 verification state, regression tests, and amendment records:

- `README.md`
- `topic1.md`
- `topic1-reading-guide/` (removed intentionally)
- `docs/00-foundations/`
- `docs/04-design/related-work.md`
- `docs/BAO_CAO_TONG_HOP_DU_AN.md`
- `docs/release/clean-clone-amendment.md`
- `reports/release/clean-clone-amendment.json`
- `scripts/verify_all.py`
- `tests/test_verify_all.py`
