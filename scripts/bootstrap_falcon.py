#!/usr/bin/env python3
"""Bootstrap FALCON artifact from pinned archive into work/artifacts/falcon.

Extracts only whitelisted files required for Defects4J reproduction and Chart Bridge,
verifying archive size, SHA-256 checksum, member presence, and Zip Slip defenses.
Operation is idempotent: existing files with matching hashes are preserved; conflicting
files cause a hard failure without silent overwrites.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import stat
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

# Pinned metadata for FALCON v1 artifact (Zenodo Record: 18897073)
PINNED_ARCHIVE_SIZE = 24089023
PINNED_SHA256 = "d60fa62edf1d1838185edf19e61146f5981895702f6a7afce0ab8c3f65ee36c8"
PINNED_MD5 = "a1cfd6c32eb5889c0e08f23872739aae"
PINNED_ZENODO_RECORD = 18897073
ZENODO_DOWNLOAD_URL = "https://zenodo.org/records/18897073/files/falcon.zip?download=1"

MANDATORY_MEMBERS = [
    "falcon/py/submodtcp.py",
    "falcon/py/embedding_generator.py",
    "falcon/py/metric.py",
    "falcon/input/Chart/Chart-bbox.txt",
    "falcon/input/Chart/test_method_mapping.json",
    "falcon/input/Chart/fault_matrix.pickle",
    "falcon/LICENSE",
]

WHITELIST_DIRECTORY_PREFIXES = [
    "falcon/py/",
    "falcon/input/Chart/",
]

WHITELIST_EXACT_FILES = {
    "falcon/LICENSE",
    "falcon/README.md",
    "falcon/requirements.txt",
}


class BootstrapSecurityError(Exception):
    """Raised when an archive member violates path traversal or security constraints."""
    pass


class BootstrapIntegrityError(Exception):
    """Raised when an archive fails hash, size, or member verification."""
    pass


def compute_sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file in 64 KiB chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_bytes_sha256(data: bytes) -> str:
    """Compute SHA-256 hex digest of a byte string."""
    return hashlib.sha256(data).hexdigest()


def validate_archive_file(
    archive_path: Path,
    expected_size: int | None = PINNED_ARCHIVE_SIZE,
    expected_sha256: str | None = PINNED_SHA256,
) -> None:
    """Validate that the archive exists, is a regular file, and matches size and SHA-256."""
    if not archive_path.exists():
        raise BootstrapIntegrityError(f"Archive file not found: {archive_path}")
    if not archive_path.is_file():
        raise BootstrapIntegrityError(f"Archive path is not a regular file: {archive_path}")

    actual_size = archive_path.stat().st_size
    if expected_size is not None and actual_size != expected_size:
        raise BootstrapIntegrityError(
            f"Archive size mismatch: expected {expected_size} bytes, found {actual_size} bytes."
        )

    if expected_sha256 is not None:
        actual_sha256 = compute_sha256(archive_path)
        if actual_sha256.lower() != expected_sha256.lower():
            raise BootstrapIntegrityError(
                f"Archive SHA-256 mismatch:\n"
                f"  Expected: {expected_sha256}\n"
                f"  Found:    {actual_sha256}"
            )


def validate_member_security(member_name: str, info: zipfile.ZipInfo | None = None) -> None:
    """Check archive member against Zip Slip vulnerabilities, drive paths, and special files."""
    # Normalize separators for consistent checking
    norm = member_name.replace("\\", "/")

    # Check for drive letters (e.g. C:, D:)
    if re.match(r"^[a-zA-Z]:", member_name) or re.match(r"^[a-zA-Z]:", norm):
        raise BootstrapSecurityError(f"Zip member contains drive letter: {member_name}")

    # Check for absolute paths
    if norm.startswith("/") or Path(norm).is_absolute() or member_name.startswith("\\"):
        raise BootstrapSecurityError(f"Zip member has absolute path: {member_name}")

    # Check for directory traversal components
    parts = Path(norm).parts
    if ".." in parts:
        raise BootstrapSecurityError(f"Zip member contains parent directory traversal '..': {member_name}")

    # Check file mode for symlinks or special devices if ZipInfo provided
    if info is not None:
        mode = info.external_attr >> 16
        if mode != 0:
            if stat.S_ISLNK(mode):
                raise BootstrapSecurityError(f"Zip member is a symlink: {member_name}")
            if stat.S_ISCHR(mode) or stat.S_ISBLK(mode) or stat.S_ISFIFO(mode):
                raise BootstrapSecurityError(f"Zip member is a special device file: {member_name}")


def extract_falcon(
    archive_path: Path,
    target_dir: Path,
    expected_size: int | None = PINNED_ARCHIVE_SIZE,
    expected_sha256: str | None = PINNED_SHA256,
    mandatory_members: list[str] | None = None,
    whitelist_directory_prefixes: list[str] | None = None,
    whitelist_exact_files: set[str] | list[str] | None = None,
    whitelist_prefixes: list[str] | None = None,
) -> dict[str, int]:
    """Extract whitelisted members from FALCON archive into target_dir with strict preflight verification.

    Returns:
        dict with counts of 'created', 'skipped_identical', 'total_whitelisted'.
    """
    if mandatory_members is None:
        mandatory_members = MANDATORY_MEMBERS

    dir_prefixes = list(whitelist_directory_prefixes) if whitelist_directory_prefixes is not None else list(WHITELIST_DIRECTORY_PREFIXES)
    exact_files = set(whitelist_exact_files) if whitelist_exact_files is not None else set(WHITELIST_EXACT_FILES)

    # Legacy support if caller passes single list of whitelist_prefixes
    if whitelist_prefixes is not None:
        for pfx in whitelist_prefixes:
            if pfx.endswith("/"):
                if pfx not in dir_prefixes:
                    dir_prefixes.append(pfx)
            else:
                exact_files.add(pfx)

    # Directory prefixes must strictly end with '/'
    for pfx in dir_prefixes:
        if not pfx.endswith("/"):
            raise ValueError(f"Directory prefix must end with '/': {pfx}")

    # --- Phase 1: Preflight & Conflict Detection (Zero writes) ---
    validate_archive_file(archive_path, expected_size=expected_size, expected_sha256=expected_sha256)

    try:
        zf = zipfile.ZipFile(archive_path, "r")
    except zipfile.BadZipFile as e:
        raise BootstrapIntegrityError(f"Invalid or corrupted ZIP archive: {e}") from e

    with zf:
        namelist = zf.namelist()
        name_set = set(namelist)

        # 1. Verify all mandatory members exist
        missing_mandatory = [m for m in mandatory_members if m not in name_set]
        if missing_mandatory:
            raise BootstrapIntegrityError(
                f"Archive is missing mandatory members:\n" + "\n".join(f"  - {m}" for m in missing_mandatory)
            )

        # 2. Verify security of all members in archive
        for info in zf.infolist():
            validate_member_security(info.filename, info)

        target_dir = target_dir.resolve()

        to_create: list[tuple[Path, bytes]] = []
        skipped_count = 0

        for info in zf.infolist():
            raw_name = info.filename
            if raw_name.endswith("/"):
                continue

            # Strict membership check: exact file OR inside directory prefix
            is_exact = raw_name in exact_files
            is_in_dir = any(raw_name.startswith(pfx) for pfx in dir_prefixes)
            if not (is_exact or is_in_dir):
                continue

            # Map falcon/... to target_dir/...
            if raw_name.startswith("falcon/"):
                rel_path = raw_name[len("falcon/"):]
            else:
                rel_path = raw_name

            dest_file = (target_dir / rel_path).resolve()

            # Defense-in-depth: verify destination is strictly inside target_dir
            try:
                dest_file.relative_to(target_dir)
            except ValueError as e:
                raise BootstrapSecurityError(
                    f"Resolved destination {dest_file} escapes target directory {target_dir}"
                ) from e

            # Read member content
            data = zf.read(raw_name)
            member_sha256 = compute_bytes_sha256(data)

            # Conflict detection before writing ANY file
            if dest_file.exists():
                disk_sha256 = compute_sha256(dest_file)
                if disk_sha256.lower() == member_sha256.lower():
                    skipped_count += 1
                else:
                    raise BootstrapIntegrityError(
                        f"Destination file already exists with conflicting SHA-256!\n"
                        f"  File:     {dest_file}\n"
                        f"  On disk:  {disk_sha256}\n"
                        f"  In ZIP:   {member_sha256}\n"
                        f"Aborting without writing any files to avoid partial state or silent overwrite."
                    )
            else:
                to_create.append((dest_file, data))

        # --- Phase 2: Write Execution (Only runs if zero conflicts found) ---
        target_dir.mkdir(parents=True, exist_ok=True)
        for dest_file, data in to_create:
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            dest_file.write_bytes(data)

    return {
        "created": len(to_create),
        "skipped_identical": skipped_count,
        "total_whitelisted": len(to_create) + skipped_count,
    }


def download_archive(url: str, output_path: Path) -> None:
    """Download archive to a specified path with basic progress."""
    print(f"Downloading FALCON archive from {url}...")
    req = urllib.request.Request(url, headers={"User-Agent": "HC-FALCON-Bootstrap/1.0"})
    with urllib.request.urlopen(req) as resp, open(output_path, "wb") as out:
        total_size = resp.headers.get("Content-Length")
        total = int(total_size) if total_size else None
        downloaded = 0
        while chunk := resp.read(65536):
            out.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = (downloaded / total) * 100
                print(f"\rDownloading: {downloaded:,} / {total:,} bytes ({pct:.1f}%)", end="", flush=True)
    print("\nDownload complete.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap FALCON artifact into work/artifacts/falcon from pinned archive."
    )
    parser.add_argument(
        "--archive",
        type=Path,
        default=None,
        help="Path to local falcon.zip archive.",
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=None,
        help="Target extraction directory (defaults to <repo_root>/work/artifacts/falcon).",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download FALCON archive directly from pinned Zenodo record 18897073.",
    )
    args = parser.parse_args(argv)

    root_dir = Path(__file__).resolve().parents[1]
    target_dir = args.target_dir or (root_dir / "work/artifacts/falcon")

    temp_dl_file = None
    archive_path = args.archive

    if args.download:
        if archive_path is not None:
            print("ERROR: Specify either --archive or --download, not both.", file=sys.stderr)
            return 1
        temp_dl = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        temp_dl.close()
        temp_dl_file = Path(temp_dl.name)
        try:
            download_archive(ZENODO_DOWNLOAD_URL, temp_dl_file)
            archive_path = temp_dl_file
        except Exception as e:
            if temp_dl_file.exists():
                temp_dl_file.unlink()
            print(f"ERROR: Failed to download FALCON archive: {e}", file=sys.stderr)
            return 1

    if archive_path is None:
        # Check standard default location
        default_local = root_dir / "references/artifacts/falcon/falcon.zip"
        if default_local.exists():
            print(f"No --archive provided; using local archive at {default_local}")
            archive_path = default_local
        else:
            print(
                "ERROR: FALCON archive not specified and default archive not found.\n"
                "Usage:\n"
                "  python scripts/bootstrap_falcon.py --archive <path-to-falcon.zip>\n"
                f"Zenodo record: https://zenodo.org/records/{PINNED_ZENODO_RECORD}",
                file=sys.stderr,
            )
            return 1

    try:
        print(f"Verifying archive: {archive_path}")
        stats = extract_falcon(archive_path=archive_path, target_dir=target_dir)
        print(
            f"FALCON bootstrap successful:\n"
            f"  Target:            {target_dir}\n"
            f"  Created files:     {stats['created']}\n"
            f"  Preserved files:   {stats['skipped_identical']}\n"
            f"  Total whitelisted: {stats['total_whitelisted']}"
        )
        return 0
    except (BootstrapIntegrityError, BootstrapSecurityError) as e:
        print(f"BOOTSTRAP FAILED: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"UNEXPECTED ERROR: {e}", file=sys.stderr)
        return 3
    finally:
        if temp_dl_file is not None and temp_dl_file.exists():
            try:
                temp_dl_file.unlink()
            except OSError:
                pass


if __name__ == "__main__":
    sys.exit(main())
