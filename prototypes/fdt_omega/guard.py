"""FDT-Omega v0 provenance gate prototype: no network, mutation, or settlement IO.

Default posture: no trusted keys; only observational actions may pass once keys
are explicitly provisioned by the operator. This module DOES NOT run a mesh.
"""
from __future__ import annotations

import base64
from contextlib import closing
import binascii
import hashlib
import json
import math
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

PROTOCOL = "FDT-Omega"
ALIASES = frozenset((PROTOCOL, "FTD-Omega"))
VERSION = 1
ALLOWED_OBSERVATIONAL_ACTIONS = frozenset(
    ("HEALTH_REPORT", "TELEMETRY_REPORT", "VECTOR_SYNC_OFFER", "MUTATION_PROPOSAL")
)
# Human-approved, operation-specific systems can be added through separate integration.
# No peer envelope is sufficient to authorize node deployments, protocol mutations,
# wallet transfers, or payments.
PERMANENTLY_BLOCKED_ACTIONS = frozenset(
    ("EXECUTE", "DEPLOY", "PROTOCOL_MUTATION", "SETTLE", "TRANSFER", "PAY")
)
FIELDS = frozenset((
    "protocol", "version", "node_id", "key_id", "issued_at", "expires_at",
    "nonce", "action", "payload", "signature"
))


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    """Unambiguous UTF-8 JSON encoding. Reject NaN and infinity."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


@dataclass(frozen=True)
class Verdict:
    accepted: bool
    freeze_node: bool
    reason: str
    protocol: str = PROTOCOL


class ReplayStore:
    """Persistent nonce ledger. Local state must be placed on durable private storage."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        with closing(sqlite3.connect(self.path)) as connection:
            with connection:
                connection.execute("CREATE TABLE IF NOT EXISTS seen (node TEXT NOT NULL, nonce TEXT NOT NULL, expires REAL NOT NULL, PRIMARY KEY(node, nonce))")

    def record_once(self, node: str, nonce: str, expires_at: float, now: float) -> bool:
        # Write transaction serializes concurrent local verifier processes.
        with closing(sqlite3.connect(self.path, timeout=10.0)) as connection:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("DELETE FROM seen WHERE expires < ?", (now - 300.0,))
                try:
                    connection.execute("INSERT INTO seen(node, nonce, expires) VALUES(?,?,?)", (node, nonce, expires_at))
                except sqlite3.IntegrityError:
                    return False
        return True


class OmegaGate:
    def __init__(
        self,
        trusted_keys: Mapping[tuple[str, str], bytes],
        replay_store: ReplayStore,
        *,
        max_lifetime_s: int = 300,
        clock_skew_s: int = 30,
        max_envelope_bytes: int = 65536,
    ):
        # User must register keys through trusted key distribution, not remote payloads.
        self.trusted_keys = dict(trusted_keys)
        self.replay_store = replay_store
        self.max_lifetime_s = max_lifetime_s
        self.clock_skew_s = clock_skew_s
        self.max_envelope_bytes = max_envelope_bytes

    def verify(self, envelope: Mapping[str, Any], *, now: float | None = None) -> Verdict:
        now = time.time() if now is None else now

        def deny(reason: str, *, freeze: bool = True) -> Verdict:
            return Verdict(False, freeze, reason)

        if not isinstance(envelope, dict) or set(envelope) != FIELDS:
            return deny("invalid_envelope_schema")
        try:
            if len(canonical_bytes(envelope)) > self.max_envelope_bytes:
                return deny("oversized_envelope")
            protocol = envelope["protocol"]
            version = envelope["version"]
            node = envelope["node_id"]
            key_id = envelope["key_id"]
            action = envelope["action"]
            nonce = envelope["nonce"]
            issued = envelope["issued_at"]
            expires = envelope["expires_at"]
            signature = envelope["signature"]
            payload = envelope["payload"]
            if protocol not in ALIASES or type(version) is not int or version != VERSION:
                return deny("unrecognized_protocol_version")
            if not all(isinstance(v, str) and 1 <= len(v) <= 128 for v in (node, key_id, nonce, action)):
                return deny("invalid_identity_or_action")
            if not isinstance(signature, str) or not isinstance(payload, dict):
                return deny("invalid_signature_or_payload_type")
            if any(type(v) not in (int, float) or not math.isfinite(v) for v in (issued, expires)):
                return deny("invalid_timestamps")
            if expires <= issued or expires - issued > self.max_lifetime_s:
                return deny("invalid_lifetime")
            if issued > now + self.clock_skew_s or expires < now - self.clock_skew_s:
                return deny("expired_or_future_message", freeze=False)
            pub = self.trusted_keys.get((node, key_id))
            if pub is None:
                return deny("untrusted_node_key")
            if type(pub) is not bytes or len(pub) != 32:
                return deny("invalid_trust_store")
            try:
                signature_bytes = base64.b64decode(signature, validate=True)
                if len(signature_bytes) != 64:
                    return deny("invalid_signature_size")
                signed = {k: v for k, v in envelope.items() if k != "signature"}
                Ed25519PublicKey.from_public_bytes(pub).verify(signature_bytes, canonical_bytes(signed))
            except (ValueError, InvalidSignature, binascii.Error):
                return deny("signature_verification_failed")
            # Verify identity BEFORE authorization, and never run peer-supplied actions.
            if action not in ALLOWED_OBSERVATIONAL_ACTIONS:
                return deny("action_not_authorized")
            if not self.replay_store.record_once(node, nonce, float(expires), now):
                return deny("replay_detected")
            return Verdict(True, False, "verified_observation")
        except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError, sqlite3.Error):
            return deny("verification_error")