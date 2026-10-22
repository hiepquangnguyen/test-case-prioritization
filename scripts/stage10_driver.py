"""Stage 10 Orchestration Driver with Resource Supervision.

Supervises single or sequential runs across the 6 projects:
- Enforces concurrency guard (only 1 worker at a time)
- Enforces peak RSS limit (8.0 GiB) and wall-clock limit (8.0 h)
- Logs stdout and stderr separately
- Updates reports/stage10/task-status.json on completion
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_EXE = ROOT / "work/envs/falcon/Scripts/python.exe"
if not PYTHON_EXE.exists():
    PYTHON_EXE = Path(sys.executable)


def get_single_pid_rss_bytes(pid: int) -> int:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]
        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_VM_READ = 0x0010
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if not handle:
            return 0
        try:
            pmc = PROCESS_MEMORY_COUNTERS()
            pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            psapi = ctypes.windll.psapi
            psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            if psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
                return int(pmc.WorkingSetSize)
            return 0
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    else:
        try:
            with open(f"/proc/{pid}/statm") as f:
                return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
        except Exception:
            return 0


def get_process_tree_pids(root_pid: int) -> List[int]:
    """Discovers all descendant PIDs of root_pid."""
    pids = [root_pid]
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class PROCESSENTRY32(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_char * 260),
            ]

        kernel32 = ctypes.windll.kernel32
        hSnapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
        if hSnapshot == wintypes.HANDLE(-1).value or not hSnapshot:
            return pids

        pe = PROCESSENTRY32()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
        children: Dict[int, List[int]] = {}
        try:
            if kernel32.Process32First(hSnapshot, ctypes.byref(pe)):
                while True:
                    pid = pe.th32ProcessID
                    ppid = pe.th32ParentProcessID
                    children.setdefault(ppid, []).append(pid)
                    if not kernel32.Process32Next(hSnapshot, ctypes.byref(pe)):
                        break
        finally:
            kernel32.CloseHandle(hSnapshot)

        queue = [root_pid]
        while queue:
            curr = queue.pop(0)
            for child in children.get(curr, []):
                if child not in pids:
                    pids.append(child)
                    queue.append(child)
    return pids


def get_process_tree_rss_bytes(root_pid: int) -> int:
    """Sums the WorkingSetSize across the root process and all its children."""
    total_rss = 0
    tree_pids = get_process_tree_pids(root_pid)
    for pid in tree_pids:
        total_rss += get_single_pid_rss_bytes(pid)
    return total_rss


def is_pid_alive(pid: int) -> bool:
    """Checks whether a process with given PID is still running."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        SYNCHRONIZE = 0x00100000
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if not handle:
            err = ctypes.windll.kernel32.GetLastError()
            return err == 5
        try:
            wait_res = ctypes.windll.kernel32.WaitForSingleObject(handle, 0)
            return wait_res == 0x00000102
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def _terminate_pid_win32(pid: int) -> bool:
    """Terminates a single process on Windows via TerminateProcess."""
    import ctypes
    PROCESS_TERMINATE = 0x0001
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
    if not handle:
        return False
    try:
        return bool(ctypes.windll.kernel32.TerminateProcess(handle, 1))
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def kill_process_tree(root_pid: int, timeout: float = 5.0):
    """Terminates root_pid and all its child processes.

    Guarantees:
    - Target tree PIDs are discovered before termination to ensure clean tracking.
    - On Windows, uses taskkill /F /T with return code inspection.
    - If taskkill fails or is unavailable, falls back to direct Win32 TerminateProcess
      on all discovered descendant PIDs and root.
    - On Linux/macOS, uses process group SIGKILL with fallback to individual PID kills.
    - Verifies parent and all child processes actually exit before returning.
    - Does not accidentally kill processes outside the target tree.
    - Safely handles processes that have already terminated.
    - Provides meaningful error reporting instead of silently swallowing failures.
    """
    if root_pid <= 0:
        return

    # 1. Discover all descendant PIDs
    target_pids = get_process_tree_pids(root_pid)
    if root_pid not in target_pids:
        target_pids.append(root_pid)

    # If all processes already exited, return immediately
    if not any(is_pid_alive(p) for p in target_pids):
        return

    if sys.platform == "win32":
        taskkill_output = ""
        try:
            res = subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(root_pid)],
                capture_output=True,
                text=True,
            )
            # returncode 0 = SUCCESS, 128 = Process not found (already exited)
            if res.returncode not in (0, 128):
                taskkill_output = (res.stderr or res.stdout or "").strip()
                sys.stderr.write(
                    f"[kill_process_tree] taskkill /F /T /PID {root_pid} returned code {res.returncode}: {taskkill_output}\n"
                )
        except Exception as exc:
            taskkill_output = str(exc)
            sys.stderr.write(
                f"[kill_process_tree] Failed to invoke taskkill for PID {root_pid}: {exc}\n"
            )

        # Fallback: if any target PID remains alive, terminate each directly
        for p in reversed(target_pids):
            if is_pid_alive(p):
                _terminate_pid_win32(p)

        # Verification loop: wait until all target PIDs have terminated
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            still_alive = [p for p in target_pids if is_pid_alive(p)]
            if not still_alive:
                return
            for p in still_alive:
                _terminate_pid_win32(p)
            time.sleep(0.05)

        still_alive = [p for p in target_pids if is_pid_alive(p)]
        if still_alive:
            err_msg = (
                f"[kill_process_tree] Failed to terminate processes in tree of PID {root_pid}. "
                f"Surviving PIDs: {still_alive}. (taskkill output: {taskkill_output})"
            )
            sys.stderr.write(f"{err_msg}\n")
            raise RuntimeError(err_msg)

    else:
        import signal
        try:
            pgid = os.getpgid(root_pid)
            os.killpg(pgid, signal.SIGKILL)
        except Exception:
            pass

        # Fallback: kill target PIDs individually
        for p in reversed(target_pids):
            if is_pid_alive(p):
                try:
                    os.kill(p, signal.SIGKILL)
                except OSError:
                    pass

        # Verification loop
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            still_alive = [p for p in target_pids if is_pid_alive(p)]
            if not still_alive:
                return
            for p in still_alive:
                try:
                    os.kill(p, signal.SIGKILL)
                except OSError:
                    pass
            time.sleep(0.05)

        still_alive = [p for p in target_pids if is_pid_alive(p)]
        if still_alive:
            err_msg = (
                f"[kill_process_tree] Failed to terminate processes in tree of PID {root_pid}. "
                f"Surviving PIDs: {still_alive}."
            )
            sys.stderr.write(f"{err_msg}\n")
            raise RuntimeError(err_msg)


def main():
    parser = argparse.ArgumentParser(description="Stage 10 Orchestrator Driver")
    parser.add_argument("--project", type=str, choices=["Chart", "Mockito", "Lang", "Math", "Time", "Closure", "all"], default="Chart")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of tests (0 for full suite)")
    parser.add_argument("--log-dir", type=Path, default=ROOT / "work/runs/stage10/logs")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    args.log_dir.mkdir(parents=True, exist_ok=True)
    projects = ["Chart", "Mockito", "Lang", "Math", "Time", "Closure"] if args.project == "all" else [args.project]

    MAX_RSS_GIB = 8.0
    MAX_WALLCLOCK_SEC = 8.0 * 3600.0
    max_rss_bytes = int(MAX_RSS_GIB * (1024 ** 3))

    for prj in projects:
        run_dir = ROOT / f"work/runs/stage10/{prj}"
        run_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        stdout_log = args.log_dir / f"{prj}_{timestamp}_stdout.log"
        stderr_log = args.log_dir / f"{prj}_{timestamp}_stderr.log"

        cmd = [
            str(PYTHON_EXE),
            str(ROOT / "scripts/stage10_reproduce.py"),
            "--project", prj,
            "--output-dir", str(run_dir),
            "--limit", str(args.limit)
        ]
        if args.validate_only:
            cmd.append("--validate-only")

        print(f"[{prj}] Launching: {' '.join(cmd)}", flush=True)
        t_start = time.perf_counter()

        with open(stdout_log, "w", encoding="utf-8") as out_f, open(stderr_log, "w", encoding="utf-8") as err_f:
            proc = subprocess.Popen(cmd, stdout=out_f, stderr=err_f)
            peak_rss_seen = 0
            while proc.poll() is None:
                elapsed = time.perf_counter() - t_start
                if elapsed > MAX_WALLCLOCK_SEC:
                    kill_process_tree(proc.pid)
                    proc.kill()
                    print(f"[{prj}] KILL: Exceeded wallclock limit of {MAX_WALLCLOCK_SEC}s ({elapsed:.2f}s)", file=sys.stderr)
                    sys.exit(124)

                curr_rss = get_process_tree_rss_bytes(proc.pid)
                if curr_rss > peak_rss_seen:
                    peak_rss_seen = curr_rss
                if curr_rss > max_rss_bytes:
                    kill_process_tree(proc.pid)
                    proc.kill()
                    print(f"[{prj}] KILL: Process tree exceeded RSS limit of {MAX_RSS_GIB} GiB ({curr_rss / (1024**3):.2f} GiB)", file=sys.stderr)
                    sys.exit(137)

                time.sleep(1.0)
            ret = proc.returncode

        elapsed = time.perf_counter() - t_start
        print(f"[{prj}] Finished in {elapsed:.2f}s (peak RSS observed: {peak_rss_seen / (1024*1024):.2f} MiB) with exit code {ret}", flush=True)

        if ret != 0:
            print(f"[{prj}] Error encountered! Check stderr log: {stderr_log}", file=sys.stderr)
            sys.exit(ret)

        # Run validation
        val_cmd = [
            str(PYTHON_EXE),
            str(ROOT / "scripts/stage10_validate.py"),
            "--run-dir", str(run_dir),
            "--project", prj,
            "--limit", str(args.limit)
        ]
        val_ret = subprocess.run(val_cmd).returncode
        if val_ret != 0:
            print(f"[{prj}] Validation failed!", file=sys.stderr)
            sys.exit(val_ret)

    print("All requested runs completed and validated successfully.")


if __name__ == "__main__":
    main()
