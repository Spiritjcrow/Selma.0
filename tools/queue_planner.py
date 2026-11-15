#!/usr/bin/env python3
"""Offline, read-only queue planner. Does not schedule, claim, mutate or execute tasks."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

PRIORITIES = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
STATES = {"DISCOVERED", "QUEUED", "IN_REVIEW", "BLOCKED", "RESERVED_SOL_RED", "COMPLETE"}
READY = {"DISCOVERED", "QUEUED", "IN_REVIEW"}
ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")
MAX_STEPS = 7


def validate(data: dict) -> list[dict]:
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    items = data.get("items")
    if not isinstance(items, list):
        raise ValueError("items must be an array")
    seen = set()
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"item {i} must be an object")
        task_id = item.get("task_id")
        if not isinstance(task_id, str) or not ID_RE.fullmatch(task_id) or task_id in seen:
            raise ValueError(f"invalid/duplicate task_id at index {i}")
        seen.add(task_id)
        if item.get("priority") not in PRIORITIES:
            raise ValueError(f"invalid priority for {task_id}")
        if item.get("planning_state") not in STATES:
            raise ValueError(f"invalid state for {task_id}")
        if item.get("operation") != "READ_ONLY_TRIAGE":
            raise ValueError(f"unsafe operation for {task_id}")
        if item.get("approval_to_mutate") is not False:
            raise ValueError(f"mutation approval must be false for {task_id}")
        if not isinstance(item.get("source_url"), str) or not item["source_url"].startswith("https://"):
            raise ValueError(f"missing HTTPS source for {task_id}")
        for field in ("conflict_group", "lane", "next_action"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError(f"missing {field} for {task_id}")
    return items


def plan(data: dict, batch: int = 0, limit: int = 7) -> dict:
    items = validate(data)
    if not isinstance(batch, int) or batch < 0:
        raise ValueError("batch must be a nonnegative integer")
    if not isinstance(limit, int) or not 1 <= limit <= MAX_STEPS:
        raise ValueError("limit must be between 1 and 7")
    candidates = [
        item for item in items
        if item["planning_state"] in READY
    ]
    # Stable priority ordering; preserve seed order within each priority.
    candidates.sort(key=lambda item: PRIORITIES[item["priority"]])
    # One source conflict group per page. Competing tasks are deferred, not claimed.
    groups: set[str] = set()
    selected = []
    skipped_conflict = []
    for item in candidates[batch * limit:]:
        group = item["conflict_group"]
        if group in groups:
            skipped_conflict.append(item["task_id"])
            continue
        if len(selected) >= limit:
            break
        groups.add(group)
        selected.append({
            "task_id": item["task_id"],
            "source_url": item["source_url"],
            "priority": item["priority"],
            "lane": item["lane"],
            "operation": item["operation"],
            "next_action": item["next_action"],
            "source_updated_at": item.get("source_updated_at"),
        })
    digest = hashlib.sha256(json.dumps(selected, sort_keys=True).encode("utf-8")).hexdigest()
    return {
        "mode": "READ_ONLY_DRY_RUN",
        "actually_executed": 0,
        "tasks_discovered": len(items),
        "eligible_for_readonly_triage": len(candidates),
        "blocked_or_reserved": len(items) - len(candidates),
        "batch_index": batch,
        "limit": limit,
        "selected": selected,
        "deferred_same_conflict_group": skipped_conflict,
        "selection_sha256": digest,
        "warning": "A selection is not an assigned owner, completed work, live worker, permission or test PASS."
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan up to seven non-mutating queue triage steps offline")
    parser.add_argument("manifest", type=Path, help="JSON manifest (local file)")
    parser.add_argument("--batch", type=int, default=0, help="zero-based planning page")
    parser.add_argument("--limit", type=int, default=7, help="1..7 operations")
    args = parser.parse_args()
    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
        result = plan(data, batch=args.batch, limit=args.limit)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
