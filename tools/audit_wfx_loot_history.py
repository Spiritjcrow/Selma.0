#!/usr/bin/env python3
"""Read-only wfx-loot / GhostAction indicator scan of reachable local Git history.

Does not execute checked-in code, fetch network resources, or print file contents.
A clean result is NOT evidence that credentials were never accessed or that
force-pushed commits, deleted remote refs, or deleted GitHub Actions runs are safe.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

IOC_COMMIT_SUBJECTS = {
    "ci: refresh build cache", "ci: restore", "ci: cleanup",
    "chore: add ci helper", "chore: add dependency audit workflow",
}
IOC_CONTENT_MARKERS = (
    "WF_CALLBACK", "WF_SECRETS", "WF_CTOKEN", "WFX-BEGIN",
    "194.150.166.244", "18.143.168.96", "193.32.204.199",
)


def branch_indicator(ref: str) -> bool:
    return (ref.endswith("/wfx-docs") or ref == "wfx-docs" or
            bool(re.search(r"(?:^|/)ci-check-[0-9]{4}$", ref)) or
            bool(re.search(r"(?:^|/)chore/[a-z0-9]{8}$", ref)))


def file_indicator(path: str) -> bool:
    return (bool(re.search(r"(?:^|/)\.ci-[a-z0-9]{6}\.sh$", path)) or
            bool(re.search(r"(?:^|/)\.github/workflows/build-audit-[a-z0-9]+\.ya?ml$", path)) or
            path.endswith("public/fonts/fa-solid-400.woff2"))


def git(repo: Path, *arguments: str, ok_codes=(0,)) -> tuple[int, str]:
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    cmd = ["git", "-C", str(repo), "-c", "core.quotePath=false", *arguments]
    cp = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                        errors="replace", timeout=35, env=env, check=False)
    if cp.returncode not in ok_codes:
        raise RuntimeError(f"Git command failed (exit {cp.returncode}): " + " ".join(arguments[:3]))
    return cp.returncode, cp.stdout


def scan(repo: Path, since: str) -> dict:
    _, top = git(repo, "rev-parse", "--show-toplevel")
    root = Path(top.strip())
    _, refs_text = git(root, "for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/remotes")
    refs = [line for line in refs_text.splitlines() if line and not line.endswith("/HEAD")]
    findings: list[dict[str, str]] = []
    for ref in refs:
        if branch_indicator(ref):
            findings.append({"type": "suspicious_branch_name", "ref": ref})

    _, log = git(root, "log", "--all", f"--since={since}",
                 "--no-renames", "--pretty=format:%x1e%H%x1f%s", "--name-only")
    commits_scanned = 0
    seen_paths = set()
    current_sha = ""
    for raw in log.split("\n"):
        line = raw.strip(" \t\r\n")
        if not line:
            continue
        if line.startswith("\x1e"):
            fields = line[1:].split("\x1f", 1)
            if len(fields) != 2:
                raise RuntimeError("Unexpected git log commit framing")
            current_sha, subject = fields
            commits_scanned += 1
            if subject.strip().lower() in IOC_COMMIT_SUBJECTS:
                findings.append({"type": "suspicious_commit_subject", "sha": current_sha, "subject": subject})
        elif current_sha and file_indicator(line):
            key = (current_sha, line)
            if key not in seen_paths:
                seen_paths.add(key)
                findings.append({"type": "suspicious_historical_path", "sha": current_sha, "path": line})

    # Only names, not contents. Exclude this detector and its test fixtures so
    # recording the IOC strings in the detection rules cannot flag itself.
    grep_args = ["grep", "-Il"]
    for marker in IOC_CONTENT_MARKERS:
        grep_args.extend(("-e", marker))
    grep_args.extend(("HEAD", "--", ".", ":(exclude)tools/audit_wfx_loot_history.py",
                      ":(exclude)tests/test_audit_wfx_loot_history.py"))
    _, current_matches = git(root, *grep_args, ok_codes=(0, 1))
    for path in sorted(set(p.strip() for p in current_matches.splitlines() if p.strip())):
        findings.append({"type": "current_file_content_marker", "path": path.removeprefix("HEAD:")})

    return {
        "assessment": "IOC_MATCHES_REQUIRE_REVIEW" if findings else "NO_MATCHES_IN_SCANNED_REACHABLE_HISTORY",
        "repo": str(root), "since": since, "refs_scanned": len(refs),
        "reachable_commits_scanned": commits_scanned, "findings": findings,
        "limitations": [
            "Only local fetched refs and reachable commits are examined; fetch all authorized refs separately.",
            "Deleted refs/commits, rewritten history, deleted GitHub Actions runs, tokens and cloud IAM are not inspected.",
            "Current-file content detection scans HEAD tracked text only and reports file paths, never contents.",
            "No findings does not prove account, workflow or credential safety.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."), help="local repository to scan")
    parser.add_argument("--since", default="2026-11-10T00:00:00Z", help="Git --since date/time")
    args = parser.parse_args()
    try:
        data = scan(args.repo, args.since)
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
        print(json.dumps({"assessment": "SCAN_INCOMPLETE", "error": str(exc)}), file=sys.stdout)
        return 2
    print(json.dumps(data, indent=2, sort_keys=True))
    return 1 if data["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
