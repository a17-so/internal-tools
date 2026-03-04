from __future__ import annotations

import argparse
import json
import os
import signal
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Stop an active run_once process")
    parser.add_argument("--force", action="store_true", help="Escalate to SIGTERM if SIGINT does not stop")
    parser.add_argument("--timeout-seconds", type=float, default=8.0)
    args = parser.parse_args()

    pid_file = _pid_file_path()
    if not pid_file.exists():
        print("No active run PID file found.")
        return 1

    payload = json.loads(pid_file.read_text(encoding="utf-8"))
    pid = int(payload.get("pid", 0))
    if pid <= 0:
        print("Invalid PID file.")
        return 1

    if not _is_alive(pid):
        print(f"Process {pid} is not running. Removing stale PID file.")
        pid_file.unlink(missing_ok=True)
        return 0

    os.kill(pid, signal.SIGINT)
    print(f"Sent SIGINT to run_once pid={pid}")
    if _wait_for_exit(pid, timeout_seconds=args.timeout_seconds):
        print("run_once stopped cleanly.")
        return 0

    if args.force:
        os.kill(pid, signal.SIGTERM)
        print(f"Sent SIGTERM to run_once pid={pid}")
        if _wait_for_exit(pid, timeout_seconds=max(2.0, args.timeout_seconds)):
            print("run_once stopped after SIGTERM.")
            return 0
        print("run_once did not stop after SIGTERM.")
        return 2

    print("run_once is still running. Re-run with --force to escalate.")
    return 2


def _pid_file_path() -> Path:
    project_root = Path(__file__).resolve().parents[2]
    return project_root / ".runtime" / "run_once.pid"


def _is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _wait_for_exit(pid: int, *, timeout_seconds: float) -> bool:
    deadline = time.time() + max(0.0, timeout_seconds)
    while time.time() < deadline:
        if not _is_alive(pid):
            return True
        time.sleep(0.2)
    return not _is_alive(pid)


if __name__ == "__main__":
    raise SystemExit(main())
