#!/usr/bin/env python3
"""Run bounded, local PR #50 contract QA from an exact, clean Git checkout.

This tool does not authenticate a White Tester, run on Android, or prove CI.
It invokes checked-out Python tests: only use with source you trust to execute.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

TEST_FILES = (
    "tests/test_duo_handoff.py",
    "tests/test_duo_mapping_keys.py",
    "tests/test_duo_cli_regression.py",
    "tests/test_duo_boundary_matrix.py",
)
SOURCE_FILES = ("core/duo_handoff.py", "tools/selma_duo_validate.py")
SHA_PATTERN = re.compile(r"[0-9a-f]{40}\Z")


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], text=True, capture_output=True,
        timeout=15, check=False,
    )
    if result.returncode:
        raise ValueError(f"git {' '.join(args[:2])} failed (exit {result.returncode})")
    return result.stdout.strip()


def verify(root: Path, expected: str, timeout: int) -> tuple[dict, int]:
    result: dict = {
        "kind": "selma_duo_pr50_local_qa_v1",
        "expected_head_sha": expected,
        "actual_head_sha": None,
        "state": "BLOCKED",
        "tests": "NOT_RUN",
        "syntax": "NOT_RUN",
        "independent_tester": "NOT_VERIFIED",
        "android_device": "NOT_RUN",
        "github_actions": "NOT_CHECKED",
    }
    try:
        actual_root = Path(git(root, "rev-parse", "--show-toplevel")).resolve()
        if actual_root != root.resolve():
            raise ValueError("working directory is not the repository root")
        actual = git(root, "rev-parse", "HEAD")
        result["actual_head_sha"] = actual
        if actual != expected:
            raise ValueError("checkout SHA does not match expected PR head")
        if git(root, "status", "--porcelain", "--untracked-files=all"):
            raise ValueError("working tree or index contains modified or untracked files")
        # Git index flags (assume-unchanged / skip-worktree) can conceal local
        # edits from status. Compare the six pinned executable inputs against
        # the exact commit tree before parsing or executing any of them.
        for path in SOURCE_FILES + TEST_FILES:
            source = root / path
            if not source.is_file() or source.is_symlink():
                raise ValueError(f"required source missing or symlink: {path}")
            committed_blob = git(root, "rev-parse", f"HEAD:{path}")
            actual_blob = git(root, "hash-object", "--", path)
            if actual_blob != committed_blob:
                raise ValueError(f"on-disk Git blob differs from pinned HEAD: {path}")
        discovered = {path.relative_to(root).as_posix()
                      for path in (root / "tests").glob("test_duo*.py")}
        if discovered != set(TEST_FILES):
            raise ValueError("discovered test files differ from pinned allowlist")
        for path in SOURCE_FILES + TEST_FILES:
            source = root / path
            if not source.is_file() or source.is_symlink():
                raise ValueError(f"required source missing or symlink: {path}")
            ast.parse(source.read_text(encoding="utf-8"), filename=path)
        result["syntax"] = "PASS"
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        start = time.monotonic()
        process = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_duo*.py", "-v"],
            cwd=root, env=env, text=True, encoding="utf-8", errors="replace",
            capture_output=True, timeout=timeout, check=False,
        )
        combined = process.stdout + "\n" + process.stderr
        result["elapsed_ms"] = round((time.monotonic() - start) * 1000)
        result["unittest_output_sha256"] = hashlib.sha256(combined.encode()).hexdigest()
        # unittest returns zero for a suite where every method was skipped.
        # Such a run is incomplete, not passing verification evidence.
        match = re.search(r"^Ran (\d+) tests? in ", process.stderr, re.MULTILINE)
        count = int(match.group(1)) if match else 0
        skipped_match = re.search(
            r"^OK\s*\([^)]*\bskipped=(\d+)", process.stderr, re.MULTILINE,
        )
        skipped = int(skipped_match.group(1)) if skipped_match else 0
        result["test_methods_reported"] = count
        result["test_methods_skipped"] = skipped
        result["test_exit_code"] = process.returncode
        if process.returncode == 0 and (count == 0 or skipped):
            result["tests"] = "INCOMPLETE"
            result["blocker"] = "unittest reported no executed methods or skipped methods"
            return result, 2
        result["tests"] = "PASS" if process.returncode == 0 else "FAIL"
        result["state"] = "REVIEW" if process.returncode == 0 else "BLOCKED"
        # No acceptance state is emitted: even PASS is only local checkout QA.
        return result, 0 if process.returncode == 0 else 2
    except (OSError, UnicodeError, SyntaxError, ValueError, subprocess.TimeoutExpired) as exc:
        result["blocker"] = str(exc)[:200]
        return result, 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-head", required=True, help="40-character PR head SHA")
    parser.add_argument("--root", default=".", help="exact repository checkout root")
    parser.add_argument("--timeout", type=int, default=120, help="test timeout in seconds (1..300)")
    args = parser.parse_args(argv)
    if not SHA_PATTERN.fullmatch(args.expected_head) or not 1 <= args.timeout <= 300:
        parser.error("expected-head must be a lowercase 40-character SHA and timeout 1..300")
    report, code = verify(Path(args.root), args.expected_head, args.timeout)
    print(json.dumps(report, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
