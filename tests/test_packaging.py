"""Tests for packaging configuration, build system, and line-ending attributes."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestPackagingConfiguration(unittest.TestCase):
    def setUp(self):
        self.pyproject_path = ROOT / "pyproject.toml"
        self.assertTrue(self.pyproject_path.exists(), "pyproject.toml must exist")
        with open(self.pyproject_path, "rb") as f:
            self.pyproject = tomllib.load(f)

    def test_build_backend_is_setuptools_build_meta(self):
        build_sys = self.pyproject.get("build-system", {})
        backend = build_sys.get("build-backend")
        self.assertEqual(
            backend,
            "setuptools.build_meta",
            f"Expected build-backend setuptools.build_meta, got {backend}",
        )
        requires = build_sys.get("requires", [])
        self.assertTrue(any("setuptools" in r for r in requires), "setuptools must be in build-system requires")

    def test_package_discovery_covers_tcp_and_hc_falcon(self):
        tools = self.pyproject.get("tool", {}).get("setuptools", {}).get("packages", {}).get("find", {})
        include_patterns = tools.get("include", [])
        self.assertTrue(any("tcp" in p for p in include_patterns), "tcp packages must be included")
        self.assertTrue(any("hc_falcon" in p for p in include_patterns), "hc_falcon packages must be included")

    def test_extras_all_and_dev_exist(self):
        extras = self.pyproject.get("project", {}).get("optional-dependencies", {})
        self.assertIn("all", extras, "Extra 'all' must exist")
        self.assertIn("dev", extras, "Extra 'dev' must exist")
        self.assertIn("falcon", extras, "Extra 'falcon' must exist")
        self.assertIn("dante", extras, "Extra 'dante' must exist")

    def test_no_self_referencing_dependencies(self):
        pkg_name = self.pyproject.get("project", {}).get("name", "test-case-prioritization")
        extras = self.pyproject.get("project", {}).get("optional-dependencies", {})
        for extra_name, deps in extras.items():
            for dep in deps:
                self.assertFalse(
                    dep.startswith(pkg_name),
                    f"Extra '{extra_name}' contains self-referencing dependency '{dep}' which causes resolver loops",
                )

    def test_public_release_metadata_is_complete(self):
        project = self.pyproject.get("project", {})
        self.assertEqual(project.get("version"), "0.1.1")
        self.assertEqual(project.get("license"), "GPL-3.0-or-later")
        self.assertEqual(
            project.get("authors"),
            [{"name": "Hiep Quang Nguyen", "email": "hiepquangnguyen.me@gmail.com"}],
        )
        self.assertIn("Repository", project.get("urls", {}))
        self.assertIn("LICENSE", project.get("license-files", []))
        self.assertIn("THIRD_PARTY_NOTICES.md", project.get("license-files", []))

        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("GNU GENERAL PUBLIC LICENSE", license_text)
        self.assertIn("Version 3, 29 June 2007", license_text)

        citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        self.assertIn("cff-version: 1.2.0", citation)
        self.assertIn("version: 0.1.1", citation)
        self.assertIn("license: GPL-3.0-or-later", citation)

        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        for component in ("FAST", "FALCON", "DANTE", "Apache"):
            self.assertIn(component, notices)

    def test_isolated_import_from_outside_repo_cwd(self):
        """Ensures tcp and hc_falcon resolve to repository root even when invoked from outside cwd."""
        import tempfile
        outside_cwd = tempfile.gettempdir()
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import tcp, hc_falcon; print('tcp:', tcp.__file__); print('hc_falcon:', hc_falcon.__file__)",
            ],
            cwd=str(outside_cwd),
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, f"Import from outside cwd failed: {proc.stderr}")
        root_str = str(ROOT).lower()
        for line in proc.stdout.strip().splitlines():
            if ":" in line:
                mod_path = line.split(":", 1)[1].strip().lower()
                self.assertTrue(
                    mod_path.startswith(root_str),
                    f"Imported module {mod_path} does not resolve to repo root {ROOT}",
                )


class TestPackagingSideEffectsAndEnvironmentPurity(unittest.TestCase):
    """Ensures test suite and environment packaging operations leave zero pollution."""

    def test_editable_location_points_to_repo_root(self):
        """Main environment must point editable location strictly to ROOT, not temp simulations."""
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "show", "test-case-prioritization"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, f"pip show failed: {proc.stderr}")
        lines = [line.strip() for line in proc.stdout.splitlines() if line.startswith("Editable project location:")]
        self.assertTrue(len(lines) > 0, "pip show must report 'Editable project location:'")
        actual_loc = lines[0].split(":", 1)[1].strip()
        self.assertEqual(
            Path(actual_loc).resolve(),
            ROOT.resolve(),
            f"Editable project location must be {ROOT}, found: {actual_loc}",
        )

    def test_no_clean_clone_sim_directories_in_temp(self):
        """No leaked clean_clone_sim_* directories remain in temp folder."""
        import tempfile
        temp_dir = Path(tempfile.gettempdir())
        leaked = list(temp_dir.glob("clean_clone_sim_*"))
        self.assertEqual(
            leaked,
            [],
            f"Found leaked clean_clone_sim directories in {temp_dir}: {leaked}",
        )

    def test_no_temporary_direct_url_or_pth_references(self):
        """No .pth or direct_url.json in active site-packages points to temp or missing paths."""
        sp = Path(sys.prefix) / "Lib" / "site-packages"
        if not sp.exists():
            return

        for pth in sp.glob("*.pth"):
            content = pth.read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn("clean_clone_sim", content, f".pth file {pth} references clean_clone_sim")

        for durl in sp.glob("*/direct_url.json"):
            content = durl.read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn("clean_clone_sim", content, f"direct_url.json {durl} references clean_clone_sim")


class TestGitAttributesAndLineEndings(unittest.TestCase):
    def test_gitattributes_file_exists_and_sets_mixed_policy(self):
        gitattributes = ROOT / ".gitattributes"
        self.assertTrue(gitattributes.exists(), ".gitattributes must exist at root")
        content = gitattributes.read_text(encoding="utf-8")
        self.assertIn("text=auto eol=lf", content)
        self.assertIn("reports/stage[4-9]/**/*.json text eol=crlf", content)
        self.assertIn("reports/stage6/**/*.txt text eol=crlf", content)
        self.assertIn("reports/stage10/**/*.json text eol=crlf", content)
        self.assertIn("reports/stage10/smoke-chart16.json text eol=lf", content)
        self.assertIn("docs/07-diagnosis/diagnosis-and-proposal.md text eol=crlf", content)
        self.assertIn("*.pdf binary", content)
        self.assertIn("*.zip binary", content)
        self.assertIn("*.pickle binary", content)

    def test_git_resolves_expected_eol_for_representative_paths(self):
        paths = {
            "configs/implementation-v1.json": "lf",
            "scripts/stage7_diagnosis.py": "lf",
            "reports/stage9/fidelity-audit.json": "crlf",
            "reports/stage10/Chart/complete.json": "crlf",
            "reports/stage10/smoke-chart16.json": "lf",
            "docs/07-diagnosis/diagnosis-and-proposal.md": "crlf",
        }
        for rel_path, expected_eol in paths.items():
            proc = subprocess.run(
                ["git", "check-attr", "eol", "--", rel_path],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(
                proc.stdout.strip(),
                f"{rel_path}: eol: {expected_eol}",
                f"Unexpected checkout EOL policy for {rel_path}",
            )

    def test_canonical_line_endings_match_frozen_hashes(self):
        """Both LF source files and legacy CRLF evidence reproduce their frozen hashes."""
        probes = [
            ("configs/implementation-v1.json", "lf", "60091eb490"),
            ("scripts/stage7_diagnosis.py", "lf", "6a83562d44"),
            ("reports/stage9/fidelity-audit.json", "crlf", "dd3704e921"),
            ("docs/07-diagnosis/diagnosis-and-proposal.md", "crlf", "e856b7cdd5"),
            ("reports/stage10/smoke-chart16.json", "lf", "d34d60abfb"),
        ]
        for rel_path, eol, expected_prefix in probes:
            target = ROOT / rel_path
            self.assertTrue(target.exists(), f"File {rel_path} must exist")
            raw_bytes = target.read_bytes()
            lf_normalized = raw_bytes.replace(b"\r\n", b"\n")
            canonical = lf_normalized if eol == "lf" else lf_normalized.replace(b"\n", b"\r\n")
            canonical_hash = hashlib.sha256(canonical).hexdigest()
            self.assertTrue(
                canonical_hash.startswith(expected_prefix),
                f"{rel_path} canonical {eol.upper()} hash {canonical_hash} did not start with "
                f"expected freeze prefix {expected_prefix}",
            )

    def test_all_frozen_files_match_their_checkout_policy(self):
        """Every strict freeze hash is reproducible from the declared checkout attributes."""
        manifests = [
            "reports/stage5/implementation-freeze.json",
            "reports/stage6/final-evidence-freeze.json",
            "reports/stage7/evidence-freeze.json",
            "reports/stage8/evidence-freeze.json",
            "reports/stage9/evidence-freeze.json",
            "reports/stage10/evidence-freeze.json",
            "reports/stage11/evidence-freeze.json",
        ]
        frozen: dict[str, str] = {}
        for manifest in manifests:
            document = json.loads((ROOT / manifest).read_text(encoding="utf-8-sig"))
            for rel_path, expected_hash in document["files_sha256"].items():
                if rel_path == "README.md":
                    continue  # README is verified through the formal lineage amendment.
                previous = frozen.setdefault(rel_path, expected_hash)
                self.assertEqual(previous, expected_hash, f"Conflicting freeze hashes for {rel_path}")

        text_paths = sorted(path for path in frozen if not path.endswith(".gz"))
        proc = subprocess.run(
            ["git", "check-attr", "eol", "--", *text_paths],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        eol_by_path = {}
        for line in proc.stdout.splitlines():
            rel_path, eol = line.rsplit(": eol: ", 1)
            eol_by_path[rel_path] = eol

        mismatches = []
        for rel_path, expected_hash in frozen.items():
            raw = (ROOT / rel_path).read_bytes()
            if rel_path.endswith(".gz"):
                canonical = raw
            else:
                lf_bytes = raw.replace(b"\r\n", b"\n")
                eol = eol_by_path.get(rel_path)
                self.assertIn(eol, {"lf", "crlf"}, f"Missing explicit EOL policy for {rel_path}: {eol}")
                canonical = lf_bytes if eol == "lf" else lf_bytes.replace(b"\n", b"\r\n")
            actual_hash = hashlib.sha256(canonical).hexdigest()
            if actual_hash != expected_hash:
                mismatches.append(f"{rel_path}: expected={expected_hash[:10]} actual={actual_hash[:10]}")

        self.assertEqual(mismatches, [], f"Checkout policy breaks frozen evidence: {mismatches[:10]}")


if __name__ == "__main__":
    unittest.main()
