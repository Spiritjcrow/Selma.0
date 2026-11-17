#!/usr/bin/env python3
"""Offline, bounded classification of owner-supplied Gradle logs. No build authentication."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

MAX_BYTES = 2 * 1024 * 1024
TASKS = (":app:lintDebug", ":app:testDebugUnitTest", ":app:assembleDebug")
TASK_LINE = re.compile(r"^\s*> Task (:[A-Za-z0-9:_-]+)(?:\s+(FAILED|SKIPPED|NO-SOURCE|UP-TO-DATE|FROM-CACHE))?\s*$")
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


class LogError(ValueError):
    """No usable bounded Gradle log available."""


def classify(text: str) -> dict:
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_BYTES:
        raise LogError("log text is invalid or too large")
    observed = {task: "NOT_OBSERVED" for task in TASKS}
    summary = "INCOMPLETE_OR_UNKNOWN"
    for raw in text.splitlines():
        line = ANSI.sub("", raw).strip()
        match = TASK_LINE.fullmatch(line)
        if match and match.group(1) in observed:
            task, outcome = match.groups()
            observed[task] = {
                "FAILED": "REPORTED_FAILED",
                "SKIPPED": "REPORTED_SKIPPED",
                "NO-SOURCE": "REPORTED_NO_SOURCE",
                "UP-TO-DATE": "REPORTED_REUSED",
                "FROM-CACHE": "REPORTED_REUSED",
                None: "REPORTED_EXECUTED_NO_RESULT",
            }[outcome]
        # Last explicit overall marker wins: no inference from missing lines.
        if line.startswith("BUILD FAILED") or line.startswith("FAILURE: Build failed"):
            summary = "REPORTED_FAILED"
        elif line.startswith("BUILD SUCCESSFUL"):
            summary = "REPORTED_SUCCESSFUL"
    if summary == "REPORTED_SUCCESSFUL":
        for task, state in list(observed.items()):
            if state == "REPORTED_EXECUTED_NO_RESULT":
                observed[task] = "REPORTED_EXECUTED_IN_SUCCESSFUL_BUILD"
    if summary == "REPORTED_FAILED":
        # Earlier task lines cannot prove that their outputs were accepted after a failed build.
        for task, state in list(observed.items()):
            if state == "REPORTED_EXECUTED_NO_RESULT":
                observed[task] = "REPORTED_EXECUTED_BUILD_FAILED"
    return {
        "type": "selma-hypercore-gradle-log-summary",
        "source": "OWNER_SUPPLIED_UNAUTHENTICATED_TEXT",
        "overall": summary,
        "tasks": observed,
        "authenticated_runner": False,
        "apk_tested_on_device": False,
    }


def from_file(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise LogError("log unavailable, symbolic link, or exceeds 2 MiB")
    try:
        return classify(path.read_text(encoding="utf-8"))
    except UnicodeError as exc:
        raise LogError("log must be UTF-8") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Gradle report, never proof of CI success")
    parser.add_argument("log", type=Path)
    args = parser.parse_args()
    try:
        result = from_file(args.log)
    except (OSError, LogError) as exc:
        print(json.dumps({"overall": "ERROR", "error": str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["overall"] == "REPORTED_SUCCESSFUL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
