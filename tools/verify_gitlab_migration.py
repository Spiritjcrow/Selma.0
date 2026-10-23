#!/usr/bin/env python3
"""Evidence utilities for moving Selma.0 from GitHub to GitLab.

This tool never invents a destination.  The compare command requires an
actual GitLab repository URL and fails closed when either side cannot be read.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

SOURCE_REPOSITORY = "https://github.com/Spiritjcrow/Selma.0.git"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _run(*args: str) -> str:
    p = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(args)}\n{p.stderr.strip()}")
    return p.stdout


def _remote_refs(url: str) -> dict[str, str]:
    out = _run("git", "ls-remote", "--heads", "--tags", url)
    refs: dict[str, str] = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        sha, ref = line.split("\t", 1)
        if ref.endswith("^{}"):
            continue
        refs[ref] = sha
    return refs


def compare_refs(destination: str, source: str = SOURCE_REPOSITORY) -> int:
    src = _remote_refs(source)
    dst = _remote_refs(destination)
    missing = sorted(set(src) - set(dst))
    extra = sorted(set(dst) - set(src))
    mismatched = sorted(ref for ref in set(src) & set(dst) if src[ref] != dst[ref])

    result = {
        "source": source,
        "destination": destination,
        "source_ref_count": len(src),
        "destination_ref_count": len(dst),
        "missing_refs": missing,
        "extra_refs": extra,
        "mismatched_refs": [
            {"ref": ref, "source": src[ref], "destination": dst[ref]}
            for ref in mismatched
        ],
        "verified": not missing and not mismatched,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["verified"] else 1


def ci_evidence(output: Path) -> int:
    sha = os.environ.get("CI_COMMIT_SHA", "")
    if not SHA_RE.fullmatch(sha):
        raise RuntimeError("CI_COMMIT_SHA is missing or is not a 40-character commit SHA")

    root = Path.cwd()
    excluded_roots = {".git", "build", "__pycache__", ".pytest_cache", ".mypy_cache"}
    files = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root)
        if rel.parts and rel.parts[0] in excluded_roots:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files.append({"path": rel.as_posix(), "bytes": path.stat().st_size, "sha256": digest})

    record = {
        "schema": "selma.gitlab.migration.evidence.v1",
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "project_path": os.environ.get("CI_PROJECT_PATH"),
        "commit_sha": sha,
        "commit_ref_name": os.environ.get("CI_COMMIT_REF_NAME"),
        "pipeline_id": os.environ.get("CI_PIPELINE_ID"),
        "job_id": os.environ.get("CI_JOB_ID"),
        "file_count": len(files),
        "files": files,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    compare = sub.add_parser("compare-refs", help="Compare Git heads/tags between GitHub and the real GitLab destination")
    compare.add_argument("--destination", required=True, help="Actual GitLab clone URL")
    compare.add_argument("--source", default=SOURCE_REPOSITORY)

    evidence = sub.add_parser("ci-evidence", help="Write immutable CI workspace evidence")
    evidence.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    try:
        if args.command == "compare-refs":
            return compare_refs(args.destination, args.source)
        if args.command == "ci-evidence":
            return ci_evidence(args.output)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
