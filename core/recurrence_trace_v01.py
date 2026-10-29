"""Offline classical recurrence/provenance research fixture for SelmaOS issue #52.

Hash links detect accidental changes to a supplied trace; they do NOT prove
actor identity, independent test execution, authenticity, or action authority.
Never use this research module to approve a device, repository, or account action.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

FIELDS = frozenset({
    "task_id", "event_id", "owner_role", "state", "artifact_sha256",
    "evidence_sha256", "previous_hash",
})
ROLES = frozenset({"Black", "White", "UltraViolet"})
STATES = frozenset({"QUEUED", "CLAIMED", "BLOCKED", "REVIEW", "COMPLETE"})
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,95}\Z", re.ASCII)
SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


def _validate(record: Any) -> dict[str, Any]:
    if type(record) is not dict or set(record) != FIELDS:
        raise ValueError("checkpoint must have exact allowlisted fields")
    for field in ("task_id", "event_id"):
        if type(record[field]) is not str or not ID.fullmatch(record[field]):
            raise ValueError(f"invalid {field}")
    if type(record["owner_role"]) is not str or record["owner_role"] not in ROLES:
        raise ValueError("invalid owner_role")
    if type(record["state"]) is not str or record["state"] not in STATES:
        raise ValueError("invalid state")
    for field in ("artifact_sha256", "evidence_sha256"):
        if type(record[field]) is not str or not SHA.fullmatch(record[field]):
            raise ValueError(f"invalid {field}")
    prev = record["previous_hash"]
    if prev is not None and (type(prev) is not str or not SHA.fullmatch(prev)):
        raise ValueError("invalid previous_hash")
    return record


def checkpoint_hash(record: dict[str, Any]) -> str:
    """Deterministic SHA-256 of strictly validated metadata, not an HMAC."""
    valid = _validate(record)
    payload = json.dumps(valid, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def review_trace(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Report duplicate/revisit signals without changing authority or state."""
    if type(records) is not list or len(records) > 128:
        raise ValueError("trace must be an array of at most 128 checkpoints")
    event_ids: set[str] = set()
    snapshots: set[tuple[str, str, str, str]] = set()
    prior_hash = None
    duplicate_ids: list[int] = []
    unchanged_revisits: list[int] = []
    chain_breaks: list[int] = []
    changed_evidence_revisits: list[int] = []
    last_evidence_by_task: dict[str, str] = {}
    for index, record in enumerate(records):
        digest = checkpoint_hash(record)
        if record["previous_hash"] != prior_hash:
            chain_breaks.append(index)
        if record["event_id"] in event_ids:
            duplicate_ids.append(index)
        event_ids.add(record["event_id"])
        snapshot = (record["task_id"], record["state"],
                    record["artifact_sha256"], record["evidence_sha256"])
        if snapshot in snapshots:
            unchanged_revisits.append(index)
        snapshots.add(snapshot)
        task = record["task_id"]
        if task in last_evidence_by_task and last_evidence_by_task[task] != record["evidence_sha256"]:
            changed_evidence_revisits.append(index)
        last_evidence_by_task[task] = record["evidence_sha256"]
        prior_hash = digest
    return {
        "count": len(records),
        "duplicate_event_indices": duplicate_ids,
        "unchanged_revisit_indices": unchanged_revisits,
        "changed_evidence_revisit_indices": changed_evidence_revisits,
        "chain_break_indices": chain_breaks,
        "last_hash": prior_hash,
        "authority": "none_data_only",
    }

