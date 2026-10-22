#!/usr/bin/env python3
"""Cryptographic Manifest Manager for Stage 12: HC-FALCON v2.

Supports two explicit execution modes:
1. --pre-evaluation:
   Hashes all preregistration documentation, configuration, algorithm implementation,
   tests, and evaluation code.
   Outputs: reports/stage12/pre-evaluation-manifest.json
   Flags: reserved_opened=false, development_evaluated=false.
   Refuses to run if any post-observation evaluation evidence already exists.

2. --post-evaluation:
   Readiness and integrity check verifying that the pre-evaluation manifest is valid,
   complete, and strictly matches disk SHA-256 hashes.
   (In Phase A, this mode performs verification only and does not generate post-evaluation freeze).
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Tuple, Union

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "reports" / "stage12"
PRE_EVAL_MANIFEST_PATH = OUT_DIR / "pre-evaluation-manifest.json"

PREREGISTRATION_FILES = [
    "configs/hc-falcon-v2-preregistered.json",
    "docs/12-hc-falcon-v2/problem-statement.md",
    "docs/12-hc-falcon-v2/specification.md",
    "docs/12-hc-falcon-v2/evaluation-protocol.md",
    "hc_falcon/v2.py",
    "scripts/stage12_evaluate.py",
    "scripts/stage12_freeze.py",
    "tests/test_hc_falcon_v2.py",
]

POST_EVALUATION_EVIDENCE_FILES = [
    OUT_DIR / "development-screen.json",
    OUT_DIR / "evidence-freeze.json",
    OUT_DIR / "post-evaluation-manifest.json",
]

HEX_64_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def sha256_file(path: Path) -> str:
    """Computes SHA-256 hash of a file on disk."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def validate_pre_evaluation_manifest(
    manifest_data_or_path: Union[Path, str, Dict[str, Any]],
    root_dir: Path = ROOT,
    raise_on_error: bool = False,
) -> Tuple[bool, List[str]]:
    """Strict fail-closed validator for the Stage 12 pre-evaluation manifest.

    Verifies:
    - manifest is non-empty dictionary
    - stage == "12"
    - scope == "stage12_pre_evaluation_freeze"
    - parent_release == "v0.1.1"
    - primary_method == "hc_ugcs_v2"
    - reserved_opened is False (strictly boolean)
    - development_evaluated is False (strictly boolean)
    - files_count == 8
    - files_sha256 is an object matching EXACTLY the 8 preregistration files (no missing, no extra)
    - each path is non-absolute and does not traverse outside root via '..'
    - each hash is a 64-char lowercase hex string
    - each file exists on disk at root_dir / path
    - disk SHA-256 matches manifest hash
    """
    errors: List[str] = []

    # 1. Load manifest data
    if isinstance(manifest_data_or_path, (Path, str)):
        manifest_path = Path(manifest_data_or_path)
        if not manifest_path.exists():
            errors.append(f"Manifest file not found: {manifest_path}")
            if raise_on_error:
                raise RuntimeError("; ".join(errors))
            return False, errors
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception as e:
            errors.append(f"Failed to parse manifest JSON: {e}")
            if raise_on_error:
                raise RuntimeError("; ".join(errors))
            return False, errors
    elif isinstance(manifest_data_or_path, dict):
        manifest = manifest_data_or_path
    else:
        errors.append(f"Invalid manifest data type: {type(manifest_data_or_path).__name__}")
        if raise_on_error:
            raise RuntimeError("; ".join(errors))
        return False, errors

    # 2. Check non-empty dict
    if not manifest or not isinstance(manifest, dict):
        errors.append("Manifest must be a non-empty dictionary")
        if raise_on_error:
            raise RuntimeError("; ".join(errors))
        return False, errors

    # 3. Fixed fields validation
    if manifest.get("stage") != "12":
        errors.append(f"Invalid stage: expected '12', got {manifest.get('stage')!r}")

    if manifest.get("scope") != "stage12_pre_evaluation_freeze":
        errors.append(
            f"Invalid scope: expected 'stage12_pre_evaluation_freeze', got {manifest.get('scope')!r}"
        )

    if manifest.get("parent_release") != "v0.1.1":
        errors.append(
            f"Invalid parent_release: expected 'v0.1.1', got {manifest.get('parent_release')!r}"
        )

    if manifest.get("primary_method") != "hc_ugcs_v2":
        errors.append(
            f"Invalid primary_method: expected 'hc_ugcs_v2', got {manifest.get('primary_method')!r}"
        )

    if manifest.get("reserved_opened") is not False:
        errors.append(
            f"Invalid reserved_opened: must be boolean False, got {manifest.get('reserved_opened')!r}"
        )

    if manifest.get("development_evaluated") is not False:
        errors.append(
            f"Invalid development_evaluated: must be boolean False, got {manifest.get('development_evaluated')!r}"
        )

    # 4. Files count and files_sha256 structure
    expected_files_set = set(PREREGISTRATION_FILES)
    expected_count = len(expected_files_set)

    if manifest.get("files_count") != expected_count:
        errors.append(
            f"Invalid files_count: expected {expected_count}, got {manifest.get('files_count')!r}"
        )

    files_sha256 = manifest.get("files_sha256")
    if not isinstance(files_sha256, dict):
        errors.append(f"files_sha256 must be a dictionary, got {type(files_sha256).__name__}")
        if raise_on_error:
            raise RuntimeError("; ".join(errors))
        return False, errors

    if len(files_sha256) != expected_count:
        errors.append(
            f"files_sha256 length mismatch: expected {expected_count}, got {len(files_sha256)}"
        )

    actual_files_set = set(files_sha256.keys())
    missing_files = expected_files_set - actual_files_set
    extra_files = actual_files_set - expected_files_set

    if missing_files:
        errors.append(f"Missing required preregistration files: {sorted(missing_files)}")
    if extra_files:
        errors.append(f"Unexpected extra files in manifest: {sorted(extra_files)}")

    # 5. Path hygiene, hash format, disk existence, and SHA-256 match
    root_resolved = root_dir.resolve()
    for rel_path, declared_hash in files_sha256.items():
        # 1. Path type check
        if not isinstance(rel_path, str) or not rel_path.strip():
            errors.append(f"Invalid file path type: {type(rel_path).__name__}")
            continue

        # 2. Check for absolute path or Windows drive path
        p = Path(rel_path)
        if p.is_absolute() or rel_path.startswith(("/", "\\")) or (len(rel_path) > 1 and rel_path[1] == ":"):
            errors.append(f"Path must not be absolute: {rel_path}")
            continue

        # 3. Check for directory traversal
        if ".." in p.parts or ".." in rel_path.split("/") or ".." in rel_path.split("\\"):
            errors.append(f"Path must not contain '..': {rel_path}")
            continue

        # 4. Reject any file outside exact preregistration allowlist
        if rel_path not in expected_files_set:
            errors.append(f"File path not in preregistration allowlist: {rel_path}")
            continue

        # 5. Resolve candidate path and verify strictly contained inside root
        try:
            candidate_path = (root_dir / rel_path).resolve()
            try:
                candidate_path.relative_to(root_resolved)
            except ValueError:
                errors.append(f"Path escapes repository root: {rel_path}")
                continue
        except Exception as e:
            errors.append(f"Path resolution failed for {rel_path}: {e}")
            continue

        # 6. Check hash format
        if not isinstance(declared_hash, str) or not HEX_64_PATTERN.match(declared_hash):
            errors.append(
                f"Invalid SHA-256 format for {rel_path}: expected 64-character lowercase hex string, got {declared_hash!r}"
            )
            continue

        # Only check disk existence and hash if all safety checks pass
        if not candidate_path.exists():
            errors.append(f"Declared file does not exist on disk: {rel_path}")
        else:
            try:
                actual_hash = sha256_file(candidate_path)
                if actual_hash != declared_hash:
                    errors.append(
                        f"Hash mismatch for {rel_path}: manifest={declared_hash} disk={actual_hash}"
                    )
            except Exception as e:
                errors.append(f"Failed to compute hash for {rel_path}: {e}")

    is_valid = len(errors) == 0
    if raise_on_error and not is_valid:
        raise RuntimeError(f"Pre-evaluation manifest validation failed: {'; '.join(errors)}")

    return is_valid, errors


def run_pre_evaluation(
    root_dir: Path = ROOT,
    out_dir: Optional[Path] = None,
    manifest_path: Optional[Path] = None,
    preregistration_files: Optional[List[str]] = None,
    post_evaluation_evidence_files: Optional[List[Path]] = None,
) -> Path:
    """Generates pre-evaluation cryptographic manifest for preregistered assets.

    Supports dependency injection for isolated testing in temporary directories.
    """
    target_out_dir = out_dir or (root_dir / "reports" / "stage12")
    target_manifest_path = manifest_path or (target_out_dir / "pre-evaluation-manifest.json")
    files_to_freeze = preregistration_files or PREREGISTRATION_FILES
    evidence_files = (
        post_evaluation_evidence_files
        if post_evaluation_evidence_files is not None
        else [
            target_out_dir / "development-screen.json",
            target_out_dir / "evidence-freeze.json",
            target_out_dir / "post-evaluation-manifest.json",
        ]
    )

    is_default_run = (root_dir == ROOT)
    if is_default_run:
        print("=" * 70)
        print("Stage 12: Pre-Evaluation Cryptographic Freeze")
        print("=" * 70)

    # Guard against overwriting preregistration after post-observation results exist
    for evidence_path in evidence_files:
        if evidence_path.exists():
            raise RuntimeError(
                f"Pre-evaluation freeze refused: post-observation evidence already exists ({evidence_path.name}). "
                "Preregistration cannot be modified after observing evaluation results."
            )

    target_out_dir.mkdir(parents=True, exist_ok=True)
    files_sha256 = {}

    for rel_path in sorted(files_to_freeze):
        abs_path = root_dir / rel_path
        if not abs_path.exists():
            raise FileNotFoundError(f"Required preregistration file missing: {rel_path}")
        h = sha256_file(abs_path)
        files_sha256[rel_path] = h
        if is_default_run:
            print(f"  [HASH] {rel_path:45s} -> {h}")

    manifest = {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stage": "12",
        "scope": "stage12_pre_evaluation_freeze",
        "parent_release": "v0.1.1",
        "primary_method": "hc_ugcs_v2",
        "reserved_opened": False,
        "development_evaluated": False,
        "files_count": len(files_sha256),
        "files_sha256": files_sha256,
    }

    with open(target_manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    if is_default_run:
        print(f"\n[+] Pre-evaluation manifest written to: {target_manifest_path}")
        print("    reserved_opened: false")
        print("    development_evaluated: false")
        print("    parent_release: v0.1.1")
        print("    primary_method: hc_ugcs_v2")
        print(f"    files_count: {len(files_sha256)}")

    return target_manifest_path


def run_post_evaluation():
    print("=" * 70)
    print("Stage 12: Preregistration Integrity & Post-Evaluation Readiness Check")
    print("=" * 70)

    # Perform strict fail-closed validation of pre-evaluation manifest
    validate_pre_evaluation_manifest(PRE_EVAL_MANIFEST_PATH, ROOT, raise_on_error=True)
    print("[+] Pre-evaluation manifest and disk files verified cleanly.")

    dev_screen_path = OUT_DIR / "development-screen.json"
    if not dev_screen_path.exists():
        print(
            "[*] Notice: Development screen results not yet present (scripts/stage12_evaluate.py has not been run).\n"
            "    Phase A readiness check complete. Post-evaluation freeze will be generated only after evaluation."
        )
        return

    print("[+] Development screen results present. Ready for evidence freeze.")


def main():
    parser = argparse.ArgumentParser(description="Stage 12 Manifest and Freeze Automation")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--pre-evaluation",
        action="store_true",
        help="Generate pre-evaluation manifest for Stage 12 preregistered assets (refuses if results exist)",
    )
    group.add_argument(
        "--post-evaluation",
        action="store_true",
        help="Perform readiness and integrity check on Stage 12 preregistered assets (does not generate freeze in Phase A)",
    )

    args = parser.parse_args()

    if args.pre_evaluation:
        run_pre_evaluation()
    elif args.post_evaluation:
        run_post_evaluation()


if __name__ == "__main__":
    main()
