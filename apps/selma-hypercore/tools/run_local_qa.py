#!/usr/bin/env python3
"""One-command fail-closed local HyperCore tests. Does NOT build or sign Android APKs."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TIMEOUT_SECONDS = 120


def commands(python_only=False, node_only=False) -> list[tuple[str, list[str]]]:
    if python_only and node_only:
        raise ValueError("choose either --python-only or --node-only")
    plan = []
    if not node_only:
        plan.append(("python_unit", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"]))
    if not python_only:
        node = shutil.which("node")
        if not node:
            raise ValueError("Node.js not found; install it or select --python-only")
        plan.extend([
            ("javascript_syntax", [node, "--check", "assets/preflight.js"]),
            ("node_unit", [node, "--test", "tests/preflight.test.cjs"]),
        ])
    return plan


def execute(plan: list[tuple[str, list[str]]], root: Path = ROOT) -> dict:
    if not plan:
        raise ValueError("no tests selected")
    checks = []
    for name, argv in plan:
        try:
            p = subprocess.run(argv, cwd=root, text=True, capture_output=True, timeout=TIMEOUT_SECONDS, check=False)
            summary = "\n".join((p.stdout + "\n" + p.stderr).splitlines()[-20:]) if p.returncode else ""
            checks.append({"name": name, "status": "PASS" if p.returncode == 0 else "FAIL", "exit_code": p.returncode, "error_tail": summary})
        except (OSError, subprocess.TimeoutExpired) as exc:
            checks.append({"name": name, "status": "BLOCKED", "exit_code": None, "error_tail": str(exc)[:600]})
        if checks[-1]["status"] != "PASS":
            break  # Stop before subsequent steps. Never publish a green overall result.
    return {"type": "selma-hypercore-local-qa", "source": "LOCAL_EXECUTION_ONLY",
            "status": "PASS" if len(checks) == len(plan) and all(x["status"] == "PASS" for x in checks) else "FAIL",
            "checks": checks, "hosted_ci_verified": False, "android_apk_tested": False}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run bounded HyperCore Python/Node source tests")
    opts = parser.add_mutually_exclusive_group()
    opts.add_argument("--python-only", action="store_true")
    opts.add_argument("--node-only", action="store_true")
    args = parser.parse_args()
    try:
        result = execute(commands(args.python_only, args.node_only))
    except ValueError as exc:
        print(json.dumps({"status":"ERROR","reason":str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
