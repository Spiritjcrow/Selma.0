"""Offline-only, data-only Selma agent handoff boundary (proposal; not wired to runtime).

Only a trusted coordinator may seal envelopes. Compacted model output is always
untrusted data: this format carries a small status vocabulary, never instructions,
free text, hidden reasoning, approvals, secrets, or tool-execution authority.

HMAC authenticates origin/integrity/audience but DOES NOT encrypt content.
Coordinator keys and caller authentication must be supplied by a separate trusted
control plane; do not expose the signing key to model workers.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time
from dataclasses import dataclass
from typing import Any

VERSION = 1
MAX_TTL_SECONDS = 300
MAX_WIRE_BYTES = 2048
MAX_FUTURE_SKEW_SECONDS = 5
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}\Z")
_NONCE = re.compile(r"[0-9a-f]{32}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_STATUSES = frozenset({"queued", "running", "blocked", "completed"})
_REASONS = frozenset({"none", "validation_failed", "dependency_blocked", "needs_review", "unavailable"})
_ENVELOPE_FIELDS = frozenset({
    "version", "issuer", "recipient", "session", "issued_at",
    "expires_at", "nonce", "payload", "signature",
})
_PAYLOAD_FIELDS = frozenset({"task_id", "status", "reason_code", "artifact_sha256"})


class HandoffRejected(ValueError):
    """The envelope was malformed, untrusted, unauthorized, or replayed."""


@dataclass(frozen=True, slots=True)
class VerifiedHandoff:
    issuer: str
    recipient: str
    session: str
    task_id: str
    status: str
    reason_code: str
    artifact_sha256: str | None
    issued_at: int
    expires_at: int


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _integer(value: Any) -> bool:
    return type(value) is int


def _valid_key(key: bytes) -> None:
    if not isinstance(key, bytes) or len(key) < 32:
        raise ValueError("coordinator key must be at least 32 bytes")


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def _validate_payload(payload: Any) -> None:
    if not isinstance(payload, dict) or set(payload) != _PAYLOAD_FIELDS:
        raise HandoffRejected("unexpected or missing payload fields")
    if not _identifier(payload["task_id"]):
        raise HandoffRejected("invalid task identity")
    if type(payload["status"]) is not str or payload["status"] not in _STATUSES:
        raise HandoffRejected("unsupported status")
    if type(payload["reason_code"]) is not str or payload["reason_code"] not in _REASONS:
        raise HandoffRejected("unsupported reason code")
    artifact = payload["artifact_sha256"]
    if artifact is not None and (
        type(artifact) is not str or _DIGEST.fullmatch(artifact) is None
    ):
        raise HandoffRejected("invalid artifact hash")


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            raise HandoffRejected("duplicate JSON field")
        result[name] = value
    return result


def _now_seconds(value: int | None) -> int:
    if value is None:
        return int(time.time())
    if not _integer(value) or value < 0:
        raise ValueError("now must be a non-negative integer second")
    return value


def seal_handoff(
    *,
    coordinator_key: bytes,
    issuer: str,
    recipient: str,
    session: str,
    task_id: str,
    status: str,
    reason_code: str = "none",
    artifact_sha256: str | None = None,
    ttl_seconds: int = 60,
    now: int | None = None,
) -> str:
    """Trusted-coordinator ONLY; no model content is accepted as free text."""
    _valid_key(coordinator_key)
    if not all(_identifier(x) for x in (issuer, recipient, session)):
        raise HandoffRejected("invalid scope identity")
    if not _integer(ttl_seconds) or not 1 <= ttl_seconds <= MAX_TTL_SECONDS:
        raise HandoffRejected("invalid TTL")
    payload = {
        "task_id": task_id, "status": status,
        "reason_code": reason_code, "artifact_sha256": artifact_sha256,
    }
    _validate_payload(payload)
    issued = _now_seconds(now)
    unsigned = {
        "version": VERSION,
        "issuer": issuer,
        "recipient": recipient,
        "session": session,
        "issued_at": issued,
        "expires_at": issued + ttl_seconds,
        "nonce": secrets.token_hex(16),
        "payload": payload,
    }
    signature = hmac.new(coordinator_key, _canonical(unsigned), hashlib.sha256).hexdigest()
    return _canonical({**unsigned, "signature": signature}).decode("ascii")


class HandoffVerifier:
    """Recipient+session scoped gate with in-memory bounded replay detection.

    This is a data validation primitive, NOT user approval or an executor.
    Give each intended recipient/session a separate verifier; key ownership and
    authenticated transport belong to the existing coordinator/control plane.
    """

    def __init__(
        self, *, coordinator_key: bytes, expected_issuer: str,
        recipient: str, session: str, replay_capacity: int = 4096,
    ) -> None:
        _valid_key(coordinator_key)
        if not all(_identifier(x) for x in (expected_issuer, recipient, session)):
            raise ValueError("invalid expected scope")
        if not _integer(replay_capacity) or replay_capacity < 1:
            raise ValueError("invalid replay capacity")
        self._key = coordinator_key
        self._issuer = expected_issuer
        self._recipient = recipient
        self._session = session
        self._capacity = replay_capacity
        self._seen: dict[str, int] = {}

    def verify(self, wire: str, *, now: int | None = None) -> VerifiedHandoff:
        current = _now_seconds(now)
        if not isinstance(wire, str) or len(wire.encode("utf-8")) > MAX_WIRE_BYTES:
            raise HandoffRejected("invalid handoff wire size/type")
        try:
            envelope = json.loads(wire, object_pairs_hook=_reject_duplicates)
        except (ValueError, TypeError, UnicodeError) as exc:
            raise HandoffRejected("invalid handoff JSON") from exc
        if not isinstance(envelope, dict) or set(envelope) != _ENVELOPE_FIELDS:
            raise HandoffRejected("unexpected or missing envelope fields")
        if type(envelope["version"]) is not int or envelope["version"] != VERSION:
            raise HandoffRejected("unsupported handoff version")
        for field in ("issuer", "recipient", "session"):
            if not _identifier(envelope[field]):
                raise HandoffRejected("malformed scope")
        if (envelope["issuer"], envelope["recipient"], envelope["session"]) != (
            self._issuer, self._recipient, self._session
        ):
            raise HandoffRejected("agent/session scope mismatch")
        issued, expires = envelope["issued_at"], envelope["expires_at"]
        if not _integer(issued) or not _integer(expires):
            raise HandoffRejected("malformed timestamp")
        if not 1 <= expires - issued <= MAX_TTL_SECONDS:
            raise HandoffRejected("unbounded TTL")
        if issued > current + MAX_FUTURE_SKEW_SECONDS or expires <= current:
            raise HandoffRejected("future or expired handoff")
        nonce, signature = envelope["nonce"], envelope["signature"]
        if (type(nonce) is not str or _NONCE.fullmatch(nonce) is None or
            type(signature) is not str or _DIGEST.fullmatch(signature) is None):
            raise HandoffRejected("invalid nonce/signature")
        _validate_payload(envelope["payload"])
        unsigned = {key: value for key, value in envelope.items() if key != "signature"}
        expected = hmac.new(self._key, _canonical(unsigned), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise HandoffRejected("handoff integrity verification failed")
        # Expired entries can be safely evicted. Live entries are never evicted
        # just to accept another message: capacity exhaustion fails closed.
        self._seen = {k: expiry for k, expiry in self._seen.items() if expiry > current}
        if nonce in self._seen:
            raise HandoffRejected("handoff replay")
        if len(self._seen) >= self._capacity:
            raise HandoffRejected("replay cache capacity exhausted")
        self._seen[nonce] = expires
        payload = envelope["payload"]
        return VerifiedHandoff(
            issuer=envelope["issuer"], recipient=envelope["recipient"],
            session=envelope["session"], task_id=payload["task_id"],
            status=payload["status"], reason_code=payload["reason_code"],
            artifact_sha256=payload["artifact_sha256"],
            issued_at=issued, expires_at=expires,
        )
