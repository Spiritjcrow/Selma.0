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
import tempfile
import time

TEST_FILES = (
    "tests/test_duo_handoff.py",
    "tests/test_duo_mapping_keys.py",
    "tests/test_duo_cli_regression.py",
    "tests/test_duo_boundary_matrix.py",
)
# Python imports package initializers before their child modules.  The
# duo tests also import core.protocols indirectly through core/__init__.py.
# These executable dependencies must be pinned just like the test modules.
SOURCE_FILES = (
    "core/duo_handoff.py",
    "tools/selma_duo_validate.py",
    "core/__init__.py",
    "core/protocols.py",
    "tests/__init__.py",
)
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
        # edits from status. Compare all pinned executable inputs against
        # the exact commit tree before parsing or executing any of them.
        for path in SOURCE_FILES + TEST_FILES:
            source = root / path
            if not source.is_file() or source.is_symlink():
                raise ValueError(f"required source missing or symlink: {path}")
            committed_blob = git(root, "rev-parse", f"HEAD:{path}")
            actual_blob = git(root, "hash-object", "--", path)
            if actual_blob != committed_blob:
                raise ValueError(f"on-disk Git blob differs from pinned HEAD: {path}")
        # Python import resolution prefers a package directory with
        # __init__.py over a same-named .py module. An ignored directory
        # can therefore replace pinned source at import time while Git
        # status and hash-object still validate the untouched .py file.
        # This is a conservative import-shadow guard, not a sandbox.
        for path in SOURCE_FILES + TEST_FILES:
            package_dir = root / path.removesuffix(".py")
            if package_dir.is_dir() or package_dir.is_symlink():
                raise ValueError(f"package directory shadows pinned module: {path}")
        # unittest discovers matching tests recursively through Python packages.
        # A top-level glob misses nested tracked or Git-ignored tests, which
        # could execute despite the pinned top-level test-file allowlist.
        discovered = {path.relative_to(root).as_posix()
                      for path in (root / "tests").rglob("test_duo*.py")}
        if discovered != set(TEST_FILES):
            raise ValueError("discovered test files differ from pinned allowlist")
        declared_methods = 0
        for path in SOURCE_FILES + TEST_FILES:
            source = root / path
            if not source.is_file() or source.is_symlink():
                raise ValueError(f"required source missing or symlink: {path}")
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=path)
            # ast.parse alone accepts context-invalid constructs (for example,
            # a module-level return). Compile every pinned input without
            # executing it before any unittest import can report a false PASS.
            compile(tree, path, "exec", dont_inherit=True)
            if path in TEST_FILES:
                # unittest's module-level load_tests hook can replace the
                # discovered suite while preserving the reported test count
                # (e.g. repeat one passing method and omit a failing method).
                # The pinned v0.1 modules do not require custom discovery;
                # refuse these hooks before executing any test code.
                # unittest also honors load_tests bound through assignments
                # (including lambdas) or imported aliases, not just defs.
                # This is a bounded consistency check, not a sandbox for
                # arbitrary untrusted Python in a checkout.
                if any(
                    (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and node.name == "load_tests")
                    or (isinstance(node, ast.Name)
                        and isinstance(node.ctx, ast.Store)
                        and node.id == "load_tests")
                    or (isinstance(node, (ast.Import, ast.ImportFrom))
                        and any((alias.asname or alias.name.split(".")[0])
                                == "load_tests" for alias in node.names))
                    for node in ast.walk(tree)
                ):
                    raise ValueError(f"pinned test module defines load_tests: {path}")
                # PEP 562 module __getattr__ can synthesize a load_tests hook
                # at unittest discovery time without a static load_tests name.
                # This pinned suite needs no dynamic module attribute hooks.
                # __dir__ can hide a failing TestCase class from unittest
                # discovery and duplicate a passing class via an alias while
                # keeping the declared/reported method counts equal.
                for hook_name in ("__getattr__", "__dir__"):
                    if any(
                        (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                         and node.name == hook_name)
                        or (isinstance(node, ast.Name)
                            and isinstance(node.ctx, ast.Store)
                            and node.id == hook_name)
                        or (isinstance(node, (ast.Import, ast.ImportFrom))
                            and any((alias.asname or alias.name.split(".")[0])
                                    == hook_name for alias in node.names))
                        for node in ast.walk(tree)
                    ):
                        raise ValueError(f"pinned test module defines {hook_name}: {path}")
                # A pinned test module that silently loses all test methods
                # must not let the remaining modules yield a false PASS.
                # Count only directly declared methods of unittest.TestCase
                # subclasses in the pinned suite. A non-TestCase helper can
                # contain a test_-named method that unittest never discovers;
                # aliasing a passing TestCase under a second module name could
                # otherwise make the reported count equal the inflated AST
                # count while a hidden method remains unexecuted.
                # Inherited/dynamic test definitions are deliberately outside
                # this bounded, fail-closed suite contract (not a sandbox).
                # A top-level TestCase declaration may disappear from the
                # module namespace before discovery (del or rebinding), while
                # an alias repeats a passing class. The executed test count
                # can then match the AST count even though a failing class
                # was never loaded. Fail closed on direct module-level
                # binding changes and aliases in this fixed test suite.
                testcase_classes = [
                    cls for cls in tree.body
                    if isinstance(cls, ast.ClassDef)
                    and any(
                        isinstance(base, ast.Attribute)
                        and isinstance(base.value, ast.Name)
                        and base.value.id == "unittest"
                        and base.attr == "TestCase"
                        for base in cls.bases
                    )
                ]
                testcase_names = {cls.name for cls in testcase_classes}
                if len(testcase_names) != len(testcase_classes):
                    raise ValueError(f"pinned TestCase class name reused: {path}")
                # A module-level if/try/with/loop can delete or rebind a
                # TestCase class before unittest discovers it. Looking only
                # at direct tree.body assignment targets misses these paths,
                # allowing a passing-class alias to mask the lost test.
                # Inspect module-level executable statements recursively;
                # skip function/class bodies, which have their own scopes.
                for statement in tree.body:
                    if isinstance(statement, ast.ClassDef):
                        if (statement.name in testcase_names
                                and statement not in testcase_classes):
                            raise ValueError(f"pinned TestCase binding changed: {path}")
                        continue
                    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if statement.name in testcase_names:
                            raise ValueError(f"pinned TestCase binding changed: {path}")
                        continue
                    if any(
                        (isinstance(node, ast.Name)
                         and isinstance(node.ctx, (ast.Store, ast.Del))
                         and node.id in testcase_names)
                        # Function/class definitions bind their names without
                        # producing an ast.Name(Store). Catch definitions in
                        # module-level if/try/with/loop blocks too.
                        or (isinstance(node, (ast.FunctionDef,
                                              ast.AsyncFunctionDef,
                                              ast.ClassDef))
                            and node.name in testcase_names)
                        for node in ast.walk(statement)
                    ):
                        raise ValueError(f"pinned TestCase binding changed: {path}")
                methods = sum(
                    1
                    # unittest discovers module-level TestCase classes; a
                    # nested class is not loaded unless separately exposed.
                    # Counting nested methods can falsely match an aliased
                    # passing top-level class and conceal omitted coverage.
                    for cls in tree.body
                    if isinstance(cls, ast.ClassDef)
                    and any(
                        isinstance(base, ast.Attribute)
                        and isinstance(base.value, ast.Name)
                        and base.value.id == "unittest"
                        and base.attr == "TestCase"
                        for base in cls.bases
                    )
                    for node in cls.body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name.startswith("test_")
                )
                if not methods:
                    raise ValueError(f"pinned test module declares no test methods: {path}")
                declared_methods += methods
        result["test_methods_declared"] = declared_methods
        result["syntax"] = "PASS"
        # Do not inherit PYTHONPATH/PYTHONHOME or other Python interpreter
        # environment overrides: they can replace stdlib unittest and fake QA.
        # Nested CLI subprocesses inherit this sanitized environment too.
        env = {key: value for key, value in os.environ.items()
               if not key.upper().startswith("PYTHON")}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        # -B prevents writes, not reads: Python may otherwise execute an
        # ignored, timestamp-valid __pycache__ payload instead of pinned source.
        # A fresh isolated cache prefix also propagates to nested CLI Python.
        with tempfile.TemporaryDirectory(prefix="selma-duo-pycache-") as cache_dir:
            env["PYTHONPYCACHEPREFIX"] = cache_dir
            start = time.monotonic()
            process = subprocess.run(
                [sys.executable, "-I", "-B", "-X", f"pycache_prefix={cache_dir}",
                 "-c", "import sys, unittest; sys.path.insert(0, '.'); "
                 "unittest.main(module=None, argv=['unittest', 'discover', "
                 "'-s', 'tests', '-p', 'test_duo*.py', '-v'])"],
                cwd=root, env=env, text=True, encoding="utf-8", errors="replace",
                capture_output=True, timeout=timeout, check=False,
            )
        combined = process.stdout + "\n" + process.stderr
        result["elapsed_ms"] = round((time.monotonic() - start) * 1000)
        result["unittest_output_sha256"] = hashlib.sha256(combined.encode()).hexdigest()
        # unittest returns zero for a suite where every method was skipped.
        # Such a run is incomplete, not passing verification evidence.
        # Test modules may write arbitrary stderr, including a forged
        # "Ran 999 tests" header before unittest prints its real summary.
        # Ambiguous summaries cannot establish trustworthy coverage.
        summary_matches = re.findall(
            r"^Ran (\d+) tests? in ", process.stderr, re.MULTILINE,
        )
        count = int(summary_matches[0]) if len(summary_matches) == 1 else 0
        skipped_match = re.search(
            r"^OK\s*\([^)]*\bskipped=(\d+)", process.stderr, re.MULTILINE,
        )
        skipped = int(skipped_match.group(1)) if skipped_match else 0
        # @unittest.expectedFailure yields exit 0 even if no assertions pass.
        # Treat any such result as incomplete rather than promoting it to PASS.
        expected_failure_match = re.search(
            r"^OK\s*\([^)]*\bexpected failures=(\d+)",
            process.stderr, re.MULTILINE,
        )
        expected_failures = (int(expected_failure_match.group(1))
                             if expected_failure_match else 0)
        result["test_methods_reported"] = count
        result["unittest_summary_count"] = len(summary_matches)
        result["test_methods_skipped"] = skipped
        result["test_methods_expected_failures"] = expected_failures
        result["test_exit_code"] = process.returncode
        if process.returncode == 0 and (
            len(summary_matches) != 1 or count != declared_methods
            or skipped or expected_failures
        ):
            result["tests"] = "INCOMPLETE"
            result["blocker"] = (
                "unittest summary ambiguous, executed count differs from declared, "
                "skips, or expected failures"
            )
            return result, 2
        result["tests"] = "PASS" if process.returncode == 0 else "FAIL"
        result["state"] = "REVIEW" if process.returncode == 0 else "BLOCKED"
        # No acceptance state is emitted: even PASS is only local checkout QA.
        return result, 0 if process.returncode == 0 else 2
    except SyntaxError:
        result["syntax"] = "FAIL"
        result["blocker"] = "pinned Python input failed compilation"
        return result, 2
    except (OSError, UnicodeError, ValueError, subprocess.TimeoutExpired) as exc:
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
