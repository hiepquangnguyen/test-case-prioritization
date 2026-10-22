#!/usr/bin/env python3
"""Stage 11 Evidence Freeze & Closeout Manager.

Verifies prior freezes (Stages 5-10), checks simulation results and forensic analysis,
and freezes the 10 canonical files of Stage 11 into reports/stage11/evidence-freeze.json.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main():
    now_utc = datetime.now(timezone.utc).isoformat()
    out_dir = ROOT / "reports/stage11"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Verify prior freezes
    prior_freezes = {
        "reports/stage5/implementation-freeze.json": 41,
        "reports/stage6/final-evidence-freeze.json": 636,
        "reports/stage7/evidence-freeze.json": 8,
        "reports/stage8/evidence-freeze.json": 613,
        "reports/stage9/evidence-freeze.json": 3,
        "reports/stage10/evidence-freeze.json": 41,
    }

    for fp, exp_count in prior_freezes.items():
        target = ROOT / fp
        assert target.exists(), f"Prior freeze missing: {fp}"
        with open(target, "r", encoding="utf-8-sig") as f:
            d = json.load(f)
        count = len(d.get("files_sha256", {}))
        assert count == exp_count, f"Prior freeze {fp} count mismatch: exp={exp_count}, got={count}"

    print("Prior freezes (Stages 5-10) verified successfully.")

    # 2. Check simulation results and forensic analysis
    sim_p = out_dir / "simulation-results.json"
    forensic_p = out_dir / "forensic-analysis.json"
    assert sim_p.exists(), f"Missing {sim_p}"
    assert forensic_p.exists(), f"Missing {forensic_p}"

    sim_doc = json.loads(sim_p.read_text(encoding="utf-8-sig"))
    assert "projects" in sim_doc, "simulation-results.json missing projects key"

    # 3. Canonical 10 files of Stage 11
    stage11_files = sorted([
        "docs/11-improvement/forensic-report.md",
        "docs/11-improvement/hypothesis-and-design.md",
        "docs/11-improvement/phase3-report.md",
        "hc_falcon/variants.py",
        "reports/stage11/forensic-analysis.json",
        "reports/stage11/simulation-results.json",
        "scripts/stage11_closeout.py",
        "scripts/stage11_evaluation.py",
        "scripts/stage11_forensic_analysis.py",
        "tests/test_variants.py",
    ])

    stage11_hashes = {}
    for rel in stage11_files:
        full_p = ROOT / rel
        assert full_p.exists(), f"Stage 11 canonical file missing: {rel}"
        stage11_hashes[rel] = sha256_file(full_p)

    evidence_freeze = {
        "created_at": now_utc,
        "stage": "stage11-improvement-evaluation",
        "files_count": len(stage11_hashes),
        "reserved_opened": False,
        "lrts_effect_gate_passed": False,
        "files_sha256": stage11_hashes
    }

    freeze_p = out_dir / "evidence-freeze.json"
    raw_json = json.dumps(evidence_freeze, indent=2)
    # Ensure CRLF line endings per .gitattributes
    crlf_json = raw_json.replace("\r\n", "\n").replace("\n", "\r\n")
    freeze_p.write_bytes(crlf_json.encode("utf-8"))
    print(f"Wrote {freeze_p} with {len(stage11_hashes)} frozen files.")

    # 4. Strict Self-Consistency Verification
    for rel, exp_hash in stage11_hashes.items():
        act_hash = sha256_file(ROOT / rel)
        assert act_hash == exp_hash, f"Hash mismatch for {rel}: actual={act_hash} != frozen={exp_hash}"

    print(f"Self-consistency verified: all {len(stage11_hashes)} files match frozen SHA-256 hashes perfectly!")


if __name__ == "__main__":
    main()
