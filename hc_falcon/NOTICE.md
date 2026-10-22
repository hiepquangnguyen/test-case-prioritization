# Attribution

`fast.py` adapts FAST-pw and minhash/LSH code from the ICSE 2018 FAST artifact,
https://github.com/icse18-FAST/FAST, as preserved in
`work/artifacts/falcon/py/fast.py` and `lsh.py`. Those source headers specify
GNU GPL version 3 or later, irrespective of the outer FALCON artifact's MIT
license. The adaptation retains that GPL-3.0-or-later notice. License text:
https://www.gnu.org/licenses/gpl-3.0.txt.

Changes include class-source input, explicit unavailable tail, UTF-8 bytes for
xxhash, local per-build RNG, sorted candidate choice and signature memoization.
`scripts/stage5_fast_verify.py` records comparison against the pinned code.

Other modules implement the project's frozen stage-4 specification; references
and distinctions from original FALCON/DANTE are documented in `docs/04-design/`.
