"""Offline, data-only handoff contract for the SelmaOS two-phone pilot.

This module neither authenticates an agent nor sends messages. GitHub permissions
and Selma's existing control plane remain authoritative for external actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = 1
FIELDS = frozenset({
    "schema_version", "task_id", "repository", "ref", "actor_role",
    "status", "artifact", "evidence", "summary",
})
ALLOWED_STATUSES = {
    "builder": frozenset({"submitted"}),
    "tester": frozenset({"pass", "fail", "blocked"}),
}


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    if len(value) > 4096:
        raise ValueError(f"{field} is too long")
    return value.strip()


@dataclass(frozen=True, slots=True)
class HandoffMessage:
    schema_version: int
    task_id: str
    repository: str
    ref: str
    actor_role: str
    status: str
    artifact: str
    evidence: tuple[str, ...]
    summary: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "HandoffMessage":
        if not isinstance(raw, Mapping):
            raise ValueError("message must be a JSON object")
        keys = tuple(raw)
        if any(type(key) is not str for key in keys):
            raise ValueError("message field names must be strings")
        key_set = set(keys)
        if key_set != FIELDS:
            raise ValueError(
                f"message fields mismatch: missing={sorted(FIELDS - key_set)}, "
                f"extra={sorted(key_set - FIELDS)}"
            )
        if type(raw["schema_version"]) is not int or raw["schema_version"] != SCHEMA_VERSION:
            raise ValueError("unsupported schema_version")
        actor_role = _required_text(raw["actor_role"], "actor_role")
        status = _required_text(raw["status"], "status")
        if actor_role not in ALLOWED_STATUSES or status not in ALLOWED_STATUSES[actor_role]:
            raise ValueError("role cannot report this status")
        evidence = raw["evidence"]
        if not isinstance(evidence, list) or len(evidence) > 10:
            raise ValueError("evidence must be a JSON array of at most 10 strings")
        validated_evidence = tuple(
            _required_text(item, "evidence item") for item in evidence
        )
        if actor_role == "tester" and not validated_evidence:
            raise ValueError("tester reports require reproducible evidence")
        return cls(
            schema_version=SCHEMA_VERSION,
            task_id=_required_text(raw["task_id"], "task_id"),
            repository=_required_text(raw["repository"], "repository"),
            ref=_required_text(raw["ref"], "ref"),
            actor_role=actor_role,
            status=status,
            artifact=_required_text(raw["artifact"], "artifact"),
            evidence=validated_evidence,
            summary=_required_text(raw["summary"], "summary"),
        )


def _evidence_trace(items: tuple[str, ...]) -> str:
    """Describe source labeling only; labels never authenticate a test or actor.

    v0.1 evidence remains free text for compatibility. This metadata helps a
    coordinator distinguish unattributed reports from source-labeled reports
    without upgrading either to independently verified acceptance.
    """
    required = {"source", "command", "observed"}
    found = set()
    for item in items:
        label, separator, detail = item.partition(":")
        normalized = label.strip().lower()
        if not separator or normalized not in required:
            continue
        # Repeated labels may give incompatible source, command or observations.
        # Never elevate ambiguous free text to a clean provenance label.
        if normalized in found:
            return "ambiguous_unverified"
        if not detail.strip():
            return "unattributed_unverified"
        found.add(normalized)
    return ("source_labeled_unverified" if found == required
            else "unattributed_unverified")


def validate_exchange(raw_messages: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """Check one builder submission and at most one independent tester report.

    Status is a statement about supplied records, not a verified phone/session
    identity, real device test, or authorization decision.
    """
    if not isinstance(raw_messages, list) or not 1 <= len(raw_messages) <= 2:
        raise ValueError("exchange must be a JSON array of 1 or 2 messages")
    messages = [HandoffMessage.from_mapping(item) for item in raw_messages]
    builder = messages[0]
    if builder.actor_role != "builder":
        raise ValueError("exchange must begin with a builder submission")
    if len(messages) == 1:
        return {"state": "awaiting_tester", "task_id": builder.task_id}
    tester = messages[1]
    if tester.actor_role != "tester":
        raise ValueError("second exchange message must be from tester")
    for field in ("task_id", "repository", "ref", "artifact"):
        if getattr(builder, field) != getattr(tester, field):
            raise ValueError(f"tester {field} does not match builder submission")
    return {
        "state": f"tester_reported_{tester.status}",
        "task_id": builder.task_id,
        "evidence_trace": _evidence_trace(tester.evidence),
    }
