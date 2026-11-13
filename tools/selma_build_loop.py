#!/usr/bin/env python3
"""Bounded, fail-closed local build-on-commit loop for SelmaOS.

This orchestrates existing source tests and an optional debug APK build. It
never generates code, merges PRs, signs releases, publishes, or runs remotely.
"""
import argparse
import contextlib
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent


def git(root, *args):
    return subprocess.run(
        ["git", *args], cwd=root, check=True, text=True, capture_output=True,
        timeout=20,
    ).stdout.strip()


def git_control_file(root, name):
    return (root / git(root, "rev-parse", "--git-path", name)).resolve()


def clean_revision(root):
    if Path(git(root, "rev-parse", "--show-toplevel")).resolve() != root.resolve():
        raise RuntimeError("wrong Git checkout root")
    revision = git(root, "rev-parse", "--verify", "HEAD^{commit}").lower()
    if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise RuntimeError("invalid HEAD SHA")
    if git(root, "status", "--porcelain", "--untracked-files=all"):
        raise RuntimeError("checkout is dirty; commit/review changes before validation")
    return revision


def terminate(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        with contextlib.suppress(OSError, subprocess.TimeoutExpired):
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=10, check=False)
    else:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
        with contextlib.suppress(ProcessLookupError):
            process.kill()
        process.wait(timeout=3)


def validate(root, expected_sha, *, android, stop_file, deadline):
    command = [sys.executable, "tools/ci_free_local.py", "--expected-sha", expected_sha]
    if android:
        command.append("--android")
    print("Validation starting:", expected_sha, "debug-APK=" + str(android), flush=True)
    opts = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
            else {"start_new_session": True})
    process = subprocess.Popen(command, cwd=root, **opts)
    try:
        while process.poll() is None:
            if stop_file.exists():
                print("STOP requested; terminating validation", file=sys.stderr)
                return 130
            if time.monotonic() >= deadline:
                print("Validation deadline exceeded", file=sys.stderr)
                return 124
            time.sleep(0.5)
        result = process.returncode
    finally:
        terminate(process)
    if clean_revision(root) != expected_sha:
        raise RuntimeError("source changed during validation; result invalid")
    print(f"Local validation exit={result}; hosted CI/device acceptance NOT_VERIFIED", flush=True)
    return result


def loop(root, *, android=False, watch=False, max_runs=3, max_minutes=60,
         interval=20):
    if max_runs < 1 or max_runs > 100:
        raise ValueError("max_runs must be 1..100")
    if max_minutes < 1 or max_minutes > 240:
        raise ValueError("max_minutes must be 1..240")
    if interval < 1 or interval > 3600:
        raise ValueError("interval must be 1..3600 seconds")
    stop_file = git_control_file(root, "SELMA_BUILD_STOP")
    lock_file = git_control_file(root, "SELMA_BUILD_LOCK")
    if stop_file.exists():
        raise RuntimeError(f"kill switch set: {stop_file} (remove intentionally to resume)")
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RuntimeError("another loop lock exists; inspect the process before manual removal") from exc
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(f"pid={os.getpid()}\n")
        seen = None
        deadline = time.monotonic() + max_minutes * 60
        count = 0
        while count < (max_runs if watch else 1):
            if stop_file.exists():
                return 130
            if time.monotonic() >= deadline:
                return 124
            current = clean_revision(root)
            if current != seen:
                seen = current
                count += 1
                result = validate(root, current, android=android,
                                  stop_file=stop_file, deadline=deadline)
                if result != 0:
                    return result
            if not watch:
                break
            time.sleep(min(interval, max(0, deadline - time.monotonic())))
        return 0
    finally:
        lock_file.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--android", action="store_true", help="also lint, unit-test, build and hash a debug APK")
    parser.add_argument("--watch", action="store_true", help="re-run on new clean HEAD commits")
    parser.add_argument("--max-runs", type=int, default=3)
    parser.add_argument("--max-minutes", type=int, default=60)
    parser.add_argument("--interval", type=int, default=20)
    args = parser.parse_args()
    try:
        return loop(ROOT, android=args.android, watch=args.watch,
                    max_runs=args.max_runs, max_minutes=args.max_minutes,
                    interval=args.interval)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"FAIL CLOSED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
