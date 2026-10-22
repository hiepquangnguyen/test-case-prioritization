#!/usr/bin/env python3
"""Smoke script to verify editable package installation in an isolated temporary venv.

Creates a fresh temporary virtual environment, installs the current repository
in editable mode without network or build isolation, imports core packages from
outside the repository, verifies module paths resolve to the repository root,
and cleans up all temporary directories in a guaranteed finally block.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify_editable_install() -> int:
    temp_dir = Path(tempfile.mkdtemp(prefix="tcp_smoke_venv_"))
    print(f"[*] Creating isolated temporary venv in: {temp_dir}")

    try:
        # 1. Create temporary venv using current interpreter
        subprocess.run([sys.executable, "-m", "venv", str(temp_dir)], check=True)

        py_exe = temp_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if not py_exe.exists():
            print(f"[!] Error: python executable not found in temp venv: {py_exe}", file=sys.stderr)
            return 1

        # 2. Seed setuptools & packaging from active venv to avoid network download in --no-build-isolation
        active_sp = Path(sys.prefix) / ("Lib/site-packages" if os.name == "nt" else f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages")
        target_sp = temp_dir / ("Lib/site-packages" if os.name == "nt" else f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages")

        if active_sp.exists():
            for pattern in ["setuptools*", "packaging*", "_distutils_hack*", "distutils-precedence.pth"]:
                for item in active_sp.glob(pattern):
                    dest = target_sp / item.name
                    if not dest.exists():
                        if item.is_dir():
                            shutil.copytree(item, dest)
                        else:
                            shutil.copy2(item, dest)

        # 3. Run pip install -e <repo-root> --no-deps --no-build-isolation
        print(f"[*] Installing {ROOT} in editable mode into temp venv...")
        install_cmd = [
            str(py_exe),
            "-m",
            "pip",
            "install",
            "-e",
            str(ROOT),
            "--no-deps",
            "--no-build-isolation",
        ]
        proc = subprocess.run(install_cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"[!] Editable install failed (exit {proc.returncode}):\n{proc.stderr}", file=sys.stderr)
            return proc.returncode

        # 4. Verify pip show in temp venv
        show_proc = subprocess.run(
            [str(py_exe), "-m", "pip", "show", "test-case-prioritization"],
            capture_output=True,
            text=True,
        )
        if show_proc.returncode != 0:
            print(f"[!] pip show failed:\n{show_proc.stderr}", file=sys.stderr)
            return show_proc.returncode

        # 5. Import packages from outside repository cwd
        outside_cwd = Path(tempfile.gettempdir()).resolve()
        print(f"[*] Verifying import from outside directory: {outside_cwd}")
        import_cmd = [
            str(py_exe),
            "-c",
            "import tcp, hc_falcon; print('tcp:', tcp.__file__); print('hc_falcon:', hc_falcon.__file__)",
        ]
        import_proc = subprocess.run(import_cmd, cwd=str(outside_cwd), capture_output=True, text=True)
        if import_proc.returncode != 0:
            print(f"[!] Import test failed from {outside_cwd}:\n{import_proc.stderr}", file=sys.stderr)
            return import_proc.returncode

        lines = import_proc.stdout.strip().splitlines()
        print(f"[*] Imported modules:\n  " + "\n  ".join(lines))

        # Check paths point to current repository
        root_str = str(ROOT).lower()
        for line in lines:
            if ":" in line:
                mod_path = line.split(":", 1)[1].strip().lower()
                if not mod_path.startswith(root_str):
                    print(f"[!] Module path {mod_path} does not resolve to repository root {ROOT}", file=sys.stderr)
                    return 1

        print("[+] Editable install and external import smoke test PASSED successfully!")
        return 0

    finally:
        # 6. Guaranteed cleanup
        print(f"[*] Cleaning up temporary venv: {temp_dir}")
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(verify_editable_install())
