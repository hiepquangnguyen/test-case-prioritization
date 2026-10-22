"""Unit tests for FALCON bootstrap extraction and security controls."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import bootstrap_falcon
from bootstrap_falcon import (
    BootstrapIntegrityError,
    BootstrapSecurityError,
    compute_sha256,
    extract_falcon,
)


class TestBootstrapFalcon(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.archive_path = self.temp_dir / "test_falcon.zip"
        self.target_dir = self.temp_dir / "work" / "artifacts" / "falcon"

        # Define synthetic members for fast testing
        self.mandatory = [
            "falcon/py/submodtcp.py",
            "falcon/py/embedding_generator.py",
            "falcon/py/metric.py",
            "falcon/input/Chart/Chart-bbox.txt",
            "falcon/input/Chart/test_method_mapping.json",
            "falcon/input/Chart/fault_matrix.pickle",
            "falcon/LICENSE",
        ]
        self.whitelist = [
            "falcon/py/",
            "falcon/input/Chart/",
            "falcon/LICENSE",
            "falcon/README.md",
            "falcon/requirements.txt",
        ]

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_zip(self, members: dict[str, bytes]) -> tuple[int, str]:
        """Helper to create a test zip with given member paths and contents."""
        with zipfile.ZipFile(self.archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name, data in members.items():
                zf.writestr(name, data)
        size = self.archive_path.stat().st_size
        sha256 = compute_sha256(self.archive_path)
        return size, sha256

    def _valid_members(self) -> dict[str, bytes]:
        return {
            "falcon/py/submodtcp.py": b"# submodtcp code",
            "falcon/py/embedding_generator.py": b"# generator code",
            "falcon/py/metric.py": b"# metric code",
            "falcon/input/Chart/Chart-bbox.txt": b"testMethod()",
            "falcon/input/Chart/test_method_mapping.json": b"{}",
            "falcon/input/Chart/fault_matrix.pickle": b"pickle_data",
            "falcon/LICENSE": b"MIT License",
            "falcon/README.md": b"# FALCON",
            "falcon/other_ignored.txt": b"should not be extracted",
        }

    def test_1_valid_zip_extracts_cleanly(self):
        members = self._valid_members()
        size, sha256 = self._create_zip(members)
        res = extract_falcon(
            archive_path=self.archive_path,
            target_dir=self.target_dir,
            expected_size=size,
            expected_sha256=sha256,
            mandatory_members=self.mandatory,
            whitelist_prefixes=self.whitelist,
        )
        self.assertEqual(res["created"], 8)
        self.assertEqual(res["skipped_identical"], 0)
        self.assertTrue((self.target_dir / "py" / "submodtcp.py").exists())
        self.assertTrue((self.target_dir / "LICENSE").exists())
        self.assertFalse((self.target_dir / "other_ignored.txt").exists())

    def test_2_wrong_hash_fails(self):
        members = self._valid_members()
        size, sha256 = self._create_zip(members)
        with self.assertRaises(BootstrapIntegrityError) as ctx:
            extract_falcon(
                archive_path=self.archive_path,
                target_dir=self.target_dir,
                expected_size=size,
                expected_sha256="0" * 64,
                mandatory_members=self.mandatory,
                whitelist_prefixes=self.whitelist,
            )
        self.assertIn("Archive SHA-256 mismatch", str(ctx.exception))

    def test_3_wrong_size_fails(self):
        members = self._valid_members()
        size, sha256 = self._create_zip(members)
        with self.assertRaises(BootstrapIntegrityError) as ctx:
            extract_falcon(
                archive_path=self.archive_path,
                target_dir=self.target_dir,
                expected_size=size + 100,
                expected_sha256=sha256,
                mandatory_members=self.mandatory,
                whitelist_prefixes=self.whitelist,
            )
        self.assertIn("Archive size mismatch", str(ctx.exception))

    def test_4_corrupt_zip_fails(self):
        self.archive_path.write_bytes(b"This is not a zip file content")
        size = self.archive_path.stat().st_size
        sha256 = compute_sha256(self.archive_path)
        with self.assertRaises(BootstrapIntegrityError) as ctx:
            extract_falcon(
                archive_path=self.archive_path,
                target_dir=self.target_dir,
                expected_size=size,
                expected_sha256=sha256,
                mandatory_members=self.mandatory,
                whitelist_prefixes=self.whitelist,
            )
        self.assertIn("Invalid or corrupted ZIP archive", str(ctx.exception))

    def test_5_missing_mandatory_member_fails(self):
        members = self._valid_members()
        del members["falcon/py/submodtcp.py"]
        size, sha256 = self._create_zip(members)
        with self.assertRaises(BootstrapIntegrityError) as ctx:
            extract_falcon(
                archive_path=self.archive_path,
                target_dir=self.target_dir,
                expected_size=size,
                expected_sha256=sha256,
                mandatory_members=self.mandatory,
                whitelist_prefixes=self.whitelist,
            )
        self.assertIn("missing mandatory members", str(ctx.exception))
        self.assertIn("falcon/py/submodtcp.py", str(ctx.exception))

    def test_6_zip_slip_dotdot_fails(self):
        members = self._valid_members()
        members["falcon/py/../../escape.py"] = b"# malicious code"
        size, sha256 = self._create_zip(members)
        with self.assertRaises(BootstrapSecurityError) as ctx:
            extract_falcon(
                archive_path=self.archive_path,
                target_dir=self.target_dir,
                expected_size=size,
                expected_sha256=sha256,
                mandatory_members=self.mandatory,
                whitelist_prefixes=self.whitelist,
            )
        self.assertIn("traversal '..'", str(ctx.exception))

    def test_7_zip_slip_absolute_path_fails(self):
        members = self._valid_members()
        members["/etc/passwd"] = b"root:x:0:0"
        size, sha256 = self._create_zip(members)
        with self.assertRaises(BootstrapSecurityError) as ctx:
            extract_falcon(
                archive_path=self.archive_path,
                target_dir=self.target_dir,
                expected_size=size,
                expected_sha256=sha256,
                mandatory_members=self.mandatory,
                whitelist_prefixes=self.whitelist,
            )
        self.assertIn("absolute path", str(ctx.exception))

    def test_8_zip_slip_windows_drive_letter_fails(self):
        members = self._valid_members()
        members["C:Windows\\System32\\calc.exe"] = b"MZ..."
        size, sha256 = self._create_zip(members)
        with self.assertRaises(BootstrapSecurityError) as ctx:
            extract_falcon(
                archive_path=self.archive_path,
                target_dir=self.target_dir,
                expected_size=size,
                expected_sha256=sha256,
                mandatory_members=self.mandatory,
                whitelist_prefixes=self.whitelist,
            )
        self.assertIn("drive letter", str(ctx.exception))

    def test_9_only_whitelisted_extracted(self):
        members = self._valid_members()
        members["falcon/models/big_model.bin"] = b"model_weights"
        members["falcon/output/results.csv"] = b"1,2,3"
        size, sha256 = self._create_zip(members)
        extract_falcon(
            archive_path=self.archive_path,
            target_dir=self.target_dir,
            expected_size=size,
            expected_sha256=sha256,
            mandatory_members=self.mandatory,
            whitelist_prefixes=self.whitelist,
        )
        self.assertFalse((self.target_dir / "models").exists())
        self.assertFalse((self.target_dir / "output").exists())

    def test_10_idempotent_pass_on_identical_destination(self):
        members = self._valid_members()
        size, sha256 = self._create_zip(members)
        # First extraction: 8 created
        res1 = extract_falcon(
            archive_path=self.archive_path,
            target_dir=self.target_dir,
            expected_size=size,
            expected_sha256=sha256,
            mandatory_members=self.mandatory,
            whitelist_prefixes=self.whitelist,
        )
        self.assertEqual(res1["created"], 8)
        self.assertEqual(res1["skipped_identical"], 0)

        # Second extraction: 0 created, 8 skipped
        res2 = extract_falcon(
            archive_path=self.archive_path,
            target_dir=self.target_dir,
            expected_size=size,
            expected_sha256=sha256,
            mandatory_members=self.mandatory,
            whitelist_prefixes=self.whitelist,
        )
        self.assertEqual(res2["created"], 0)
        self.assertEqual(res2["skipped_identical"], 8)

    def test_11_conflicting_destination_content_fails(self):
        members = self._valid_members()
        size, sha256 = self._create_zip(members)
        extract_falcon(
            archive_path=self.archive_path,
            target_dir=self.target_dir,
            expected_size=size,
            expected_sha256=sha256,
            mandatory_members=self.mandatory,
            whitelist_prefixes=self.whitelist,
        )
        # Corrupt one extracted file on disk
        target_file = self.target_dir / "py" / "submodtcp.py"
        target_file.write_bytes(b"# TAMPERED DIFFERENT CONTENT")

        with self.assertRaises(BootstrapIntegrityError) as ctx:
            extract_falcon(
                archive_path=self.archive_path,
                target_dir=self.target_dir,
                expected_size=size,
                expected_sha256=sha256,
                mandatory_members=self.mandatory,
                whitelist_prefixes=self.whitelist,
            )
        self.assertIn("conflicting SHA-256", str(ctx.exception))

    def test_12_no_files_created_in_reports(self):
        reports_dir = self.temp_dir / "reports"
        reports_dir.mkdir()
        members = self._valid_members()
        size, sha256 = self._create_zip(members)
        extract_falcon(
            archive_path=self.archive_path,
            target_dir=self.target_dir,
            expected_size=size,
            expected_sha256=sha256,
            mandatory_members=self.mandatory,
            whitelist_prefixes=self.whitelist,
        )
        self.assertEqual(list(reports_dir.iterdir()), [])

    def test_13_no_files_created_in_configs(self):
        configs_dir = self.temp_dir / "configs"
        configs_dir.mkdir()
        members = self._valid_members()
        size, sha256 = self._create_zip(members)
        extract_falcon(
            archive_path=self.archive_path,
            target_dir=self.target_dir,
            expected_size=size,
            expected_sha256=sha256,
            mandatory_members=self.mandatory,
            whitelist_prefixes=self.whitelist,
        )
        self.assertEqual(list(configs_dir.iterdir()), [])

    def test_14_no_reserved_data_accessed_or_created(self):
        reserved_dir = self.temp_dir / "data" / "reserved"
        reserved_dir.mkdir(parents=True)
        members = self._valid_members()
        size, sha256 = self._create_zip(members)
        extract_falcon(
            archive_path=self.archive_path,
            target_dir=self.target_dir,
            expected_size=size,
            expected_sha256=sha256,
            mandatory_members=self.mandatory,
            whitelist_prefixes=self.whitelist,
        )
        self.assertEqual(list(reserved_dir.iterdir()), [])

    def test_15_cli_exit_codes(self):
        script = ROOT / "scripts" / "bootstrap_falcon.py"
        # 1. Missing archive argument -> exit code 1
        proc1 = subprocess.run(
            [sys.executable, str(script), "--archive", str(self.temp_dir / "nonexistent.zip")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc1.returncode, 2)
        self.assertIn("BOOTSTRAP FAILED", proc1.stderr)

    def test_16_double_run_exact_same_result(self):
        members = self._valid_members()
        size, sha256 = self._create_zip(members)
        res1 = extract_falcon(
            archive_path=self.archive_path,
            target_dir=self.target_dir,
            expected_size=size,
            expected_sha256=sha256,
            mandatory_members=self.mandatory,
            whitelist_prefixes=self.whitelist,
        )
        hashes_run1 = {p.relative_to(self.target_dir): compute_sha256(p) for p in self.target_dir.rglob("*") if p.is_file()}

        res2 = extract_falcon(
            archive_path=self.archive_path,
            target_dir=self.target_dir,
            expected_size=size,
            expected_sha256=sha256,
            mandatory_members=self.mandatory,
            whitelist_prefixes=self.whitelist,
        )
        hashes_run2 = {p.relative_to(self.target_dir): compute_sha256(p) for p in self.target_dir.rglob("*") if p.is_file()}

        self.assertEqual(hashes_run1, hashes_run2)
        self.assertEqual(res2["skipped_identical"], res1["created"])

    def test_17_whitelist_rejects_impostors_and_chartbackup(self):
        """Regression test: impostors and ChartBackup must be rejected; exact files and prefixes extracted."""
        members = self._valid_members()
        # Add impostors
        members["falcon/LICENSE.bak"] = b"backup license"
        members["falcon/LICENSE/child"] = b"child of license"
        members["falcon/README.md.exe"] = b"fake readme executable"
        members["falcon/requirements.txt.old"] = b"old requirements"
        members["falcon/input/ChartBackup/file.txt"] = b"chart backup file"
        members["falcon/requirements.txt"] = b"numpy>=1.20"

        size, sha256 = self._create_zip(members)
        res = extract_falcon(
            archive_path=self.archive_path,
            target_dir=self.target_dir,
            expected_size=size,
            expected_sha256=sha256,
            mandatory_members=self.mandatory,
            whitelist_directory_prefixes=["falcon/py/", "falcon/input/Chart/"],
            whitelist_exact_files={"falcon/LICENSE", "falcon/README.md", "falcon/requirements.txt"},
        )

        # 1. Impostors must NOT be extracted
        self.assertFalse((self.target_dir / "LICENSE.bak").exists(), "LICENSE.bak must not be extracted")
        self.assertFalse((self.target_dir / "LICENSE" / "child").exists(), "LICENSE/child must not be extracted")
        self.assertFalse((self.target_dir / "README.md.exe").exists(), "README.md.exe must not be extracted")
        self.assertFalse((self.target_dir / "requirements.txt.old").exists(), "requirements.txt.old must not be extracted")
        self.assertFalse((self.target_dir / "input" / "ChartBackup").exists(), "ChartBackup must not be extracted")

        # 2. Valid exact files and directory members MUST be extracted
        self.assertTrue((self.target_dir / "LICENSE").is_file(), "LICENSE must be extracted")
        self.assertTrue((self.target_dir / "README.md").is_file(), "README.md must be extracted")
        self.assertTrue((self.target_dir / "requirements.txt").is_file(), "requirements.txt must be extracted")
        self.assertTrue((self.target_dir / "py" / "submodtcp.py").is_file(), "py/submodtcp.py must be extracted")
        self.assertTrue((self.target_dir / "input" / "Chart" / "Chart-bbox.txt").is_file(), "Chart-bbox.txt must be extracted")

    def test_18_preflight_conflict_at_end_of_archive_prevents_partial_extraction(self):
        """Conflict at end of archive aborts in preflight before writing any earlier new files."""
        # Pre-seed a file that will conflict with member at the end of archive
        existing_license = self.target_dir / "LICENSE"
        existing_license.parent.mkdir(parents=True, exist_ok=True)
        existing_license.write_bytes(b"# EXISTING DIFFERENT CONTENT ON DISK")

        # Archive has a new file FIRST, and conflicting member LAST
        members = {
            "falcon/py/submodtcp.py": b"# new submodtcp content",
            "falcon/LICENSE": b"# archive license content",
        }
        size, sha256 = self._create_zip(members)

        with self.assertRaises(BootstrapIntegrityError) as ctx:
            extract_falcon(
                archive_path=self.archive_path,
                target_dir=self.target_dir,
                expected_size=size,
                expected_sha256=sha256,
                mandatory_members=["falcon/LICENSE"],
                whitelist_directory_prefixes=["falcon/py/"],
                whitelist_exact_files={"falcon/LICENSE"},
            )

        self.assertIn("conflicting SHA-256", str(ctx.exception))
        self.assertIn("Aborting without writing any files", str(ctx.exception))

        # Crucial verification: the new file that was first in the archive MUST NOT have been created
        new_file = self.target_dir / "py" / "submodtcp.py"
        self.assertFalse(new_file.exists(), "New file earlier in archive must not be created when a later member conflicts")

        # The existing file on disk must be completely untouched
        self.assertEqual(
            existing_license.read_bytes(),
            b"# EXISTING DIFFERENT CONTENT ON DISK",
            "Existing file content must remain unchanged after conflict abort",
        )

    def test_19_whitelist_directory_prefixes_validation(self):
        """Directory prefixes must end with '/' or ValueError is raised."""
        members = self._valid_members()
        size, sha256 = self._create_zip(members)
        with self.assertRaises(ValueError) as ctx:
            extract_falcon(
                archive_path=self.archive_path,
                target_dir=self.target_dir,
                expected_size=size,
                expected_sha256=sha256,
                mandatory_members=self.mandatory,
                whitelist_directory_prefixes=["falcon/py"],  # Missing trailing slash
            )
        self.assertIn("Directory prefix must end with '/'", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
