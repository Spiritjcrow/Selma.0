#!/usr/bin/env python3
"""Compare an offline destination ref snapshot with the pinned source inventory."""

import argparse
import json
from pathlib import Path
import sys


def compare_refs(source, destination):
    expected_branches = source["source_branch_refs"]
    expected_tags = source["source_tag_refs"]
    actual_branches = destination.get("branches", {})
    actual_tags = destination.get("tags", {})

    def differences(expected, actual):
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        changed = sorted(
            name
            for name in set(expected) & set(actual)
            if expected[name] != actual[name]
        )
        return missing, extra, changed

    missing_branches, extra_branches, changed_branches = differences(
        expected_branches, actual_branches
    )
    missing_tags, extra_tags, changed_tags = differences(
        expected_tags, actual_tags
    )
    visibility = destination.get("visibility")
    matches = not any(
        (
            missing_branches,
            extra_branches,
            changed_branches,
            missing_tags,
            extra_tags,
            changed_tags,
        )
    ) and visibility == "private"

    return {
        "repository": source["name"],
        "status": "MATCH" if matches else "MISMATCH",
        "visibility": visibility,
        "expected_source_refs_sha256": source["source_refs_sha256"],
        "missing_branches": missing_branches,
        "extra_branches": extra_branches,
        "changed_branches": changed_branches,
        "missing_tags": missing_tags,
        "extra_tags": extra_tags,
        "changed_tags": changed_tags,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("inventory", type=Path)
    parser.add_argument("repository")
    parser.add_argument("destination_snapshot", type=Path)
    args = parser.parse_args(argv)

    try:
        inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
        destination = json.loads(
            args.destination_snapshot.read_text(encoding="utf-8")
        )
        source = next(
            item
            for item in inventory["source_repositories"]
            if item["name"] == args.repository
        )
        report = compare_refs(source, destination)
    except (KeyError, StopIteration, OSError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, sort_keys=True))
        return 2

    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "MATCH" else 1


if __name__ == "__main__":
    sys.exit(main())
