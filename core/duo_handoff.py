"""Offline, data-only handoff contract for the SelmaOS two-phone pilot.

This module neither authenticates an agent nor sends messages. GitHub permissions
and Selma's existing control plane remain authoritative for external actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence
import unicodedata

SCHEMA_VERSION = 1
FIELDS = frozenset({
    "schema_version", "task_id", "repository", "ref", "actor_role",
    "status", "artifact", "evidence", "summary",
})
# Only structural identifiers are constrained. Human-readable evidence and
# summaries remain untrusted free text; this does not authenticate an actor.
STRUCTURAL_FIELDS = frozenset({
    "task_id", "repository", "ref", "actor_role", "status", "artifact",
})
UNSAFE_IDENTIFIER_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Zl", "Zp"})
ALLOWED_STATUSES = {
    "builder": frozenset({"submitted"}),
    "tester": frozenset({"pass", "fail", "blocked"}),
}


def _unsafe_identifier_character(char: str) -> bool:
    """Reject invisible Unicode modifiers even when NFC-stable.

    Variation selectors and CGJ are Mn, not Cf, and can silently change how
    an identifier appears without changing its exact code-point sequence.
    This is a display/spoofing guard, not identity authentication.
    """
    codepoint = ord(char)
    return (unicodedata.category(char) in UNSAFE_IDENTIFIER_CATEGORIES
            or 0xFDD0 <= codepoint <= 0xFDEF
            or (codepoint & 0xFFFF) in (0xFFFE, 0xFFFF)
            or codepoint == 0x034F
            or 0xFE00 <= codepoint <= 0xFE0F
            or 0xE0100 <= codepoint <= 0xE01EF)


def _required_text(value: Any, field: str) -> str:
    # JSON decoding yields exact str. A str subclass can override __len__,
    # __iter__, strip and equality to conceal unsafe text in direct Mapping
    # calls; accept only the built-in type rather than trusting those hooks.
    if type(value) is not str or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    if len(value) > 4096:
        raise ValueError(f"{field} is too long")
    # Newlines, NULs, bidi overrides, zero-width formatters and surrogates
    # can visually spoof the task/ref/artifact shown in a GitHub handoff.
    # Reject them before strip(), which would otherwise hide edge controls.
    if field in STRUCTURAL_FIELDS:
        # Never silently canonicalize a structural ID. Leading/trailing
        # whitespace can make distinct submitted refs look identical.
        if any(_unsafe_identifier_character(char)
               for char in value):
            raise ValueError(f"{field} contains unsafe identifier characters")
        if value != value.strip():
            raise ValueError(f"{field} contains surrounding whitespace")
        # Non-ASCII spacing characters can look like ordinary spaces while
        # identifying a different task/ref. Keep ordinary ASCII spaces valid.
        if any(unicodedata.category(char) == "Zs" and char != " "
               for char in value):
            raise ValueError(f"{field} contains unsafe identifier characters")
        # Distinct NFC/NFD spellings can display as the same identifier.
        # Reject noncanonical forms instead of silently rewriting task/ref IDs.
        if unicodedata.normalize("NFC", value) != value:
            raise ValueError(f"{field} contains non-NFC Unicode text")
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
        # Mapping implementations can enumerate the same key twice even
        # though ordinary dicts cannot. Reject ambiguous in-process records
        # just as the JSON CLI rejects duplicate object keys.
        if len(keys) != len(key_set):
            raise ValueError("duplicate message field names")
        if key_set != FIELDS:
            # Never echo attacker-controlled field names into CLI errors or
            # audit logs: an unknown key may itself contain sensitive text.
            raise ValueError(
                f"message fields mismatch: missing_count={len(FIELDS - key_set)}, "
                f"extra_count={len(key_set - FIELDS)}"
            )
        if type(raw["schema_version"]) is not int or raw["schema_version"] != SCHEMA_VERSION:
            raise ValueError("unsupported schema_version")
        actor_role = _required_text(raw["actor_role"], "actor_role")
        status = _required_text(raw["status"], "status")
        if actor_role not in ALLOWED_STATUSES or status not in ALLOWED_STATUSES[actor_role]:
            raise ValueError("role cannot report this status")
        evidence = raw["evidence"]
        # JSON decoding produces an exact built-in list. A list subclass can
        # spoof __len__ or __iter__, bypassing the ten-item bound in direct
        # in-process Mapping calls. Reject it rather than trusting its methods.
        if type(evidence) is not list or len(evidence) > 10:
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
        # A hidden modifier can turn a source/command/observed lookalike
        # into an ignored label. Downgrade before the allowlist check so a
        # second, clean label cannot conceal that conflicting provenance.
        if separator and any(
            _unsafe_identifier_character(char)
            or (unicodedata.category(char) == "Zs" and char != " ")
            for char in label
        ):
            return "ambiguous_unverified"
        normalized = label.strip().lower()
        if not separator or normalized not in required:
            continue
        # Repeated labels may give incompatible source, command or observations.
        # Never elevate ambiguous free text to a clean provenance label.
        if normalized in found:
            return "ambiguous_unverified"
        if not detail.strip():
            return "unattributed_unverified"
        # A multiline or invisible-control detail can smuggle a second
        # provenance label into one evidence item. Keep the raw evidence
        # (untrusted text), but downgrade its derived trace metadata.
        if any(_unsafe_identifier_character(char)
               for char in detail):
            return "ambiguous_unverified"
        found.add(normalized)
    return ("source_labeled_unverified" if found == required
            else "unattributed_unverified")


def validate_exchange(raw_messages: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """Check one builder submission and at most one independent tester report.

    Status is a statement about supplied records, not a verified phone/session
    identity, real device test, or authorization decision.
    """
    # Direct Python callers can pass list subclasses with spoofed __len__.
    # Require the exact JSON-decoder list type so a third record is never ignored.
    if type(raw_messages) is not list or not 1 <= len(raw_messages) <= 2:
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
