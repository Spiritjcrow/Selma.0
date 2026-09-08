"""Ed25519 avatar-pack signature verification with a pinned local trust store."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
import re
from types import MappingProxyType
from typing import Mapping

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
except ImportError:  # pragma: no cover - exercised on minimal target packages
    InvalidSignature = Exception  # type: ignore[assignment,misc]
    Ed25519PublicKey = None  # type: ignore[assignment,misc]


TRUST_SCHEMA_VERSION = "1.0.0"
MAX_TRUST_STORE_BYTES = 256 * 1024
MAX_TRUSTED_KEYS = 128
_KEY_ID = re.compile(r"ed25519:[a-z0-9][a-z0-9._:-]*")


class TrustStoreError(ValueError):
    """The local key registry is malformed or unsafe to use."""


def _no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise TrustStoreError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


@dataclass(frozen=True, slots=True)
class TrustedKey:
    key_id: str
    public_key: bytes
    status: str


def load_trust_store(path: str | Path) -> Mapping[str, TrustedKey]:
    """Load a strict public-key-only registry; private key fields are rejected."""
    with Path(path).open("rb") as handle:
        raw = handle.read(MAX_TRUST_STORE_BYTES + 1)
    if len(raw) > MAX_TRUST_STORE_BYTES:
        raise TrustStoreError("trust store exceeds size limit")
    try:
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicates)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise TrustStoreError("trust store is not strict UTF-8 JSON") from exc
    if not isinstance(document, dict) or document.get("schema_version") != TRUST_SCHEMA_VERSION:
        raise TrustStoreError("unsupported trust-store schema")
    if set(document) != {"schema_version", "algorithm", "keys"}:
        raise TrustStoreError("trust store contains missing or unknown fields")
    if document.get("algorithm") != "Ed25519":
        raise TrustStoreError("trust store algorithm must be Ed25519")
    raw_keys = document.get("keys")
    if not isinstance(raw_keys, list) or len(raw_keys) > MAX_TRUSTED_KEYS:
        raise TrustStoreError("trust-store key list is invalid or exceeds limit")
    keys: dict[str, TrustedKey] = {}
    for record in raw_keys:
        if not isinstance(record, dict) or set(record) != {"key_id", "public_key_base64", "status"}:
            raise TrustStoreError("key record contains missing, unknown, or private fields")
        key_id, encoded, status = record.get("key_id"), record.get("public_key_base64"), record.get("status")
        if not isinstance(key_id, str) or _KEY_ID.fullmatch(key_id) is None:
            raise TrustStoreError("key_id is not canonical")
        if key_id in keys:
            raise TrustStoreError("duplicate key_id")
        if status not in {"trusted", "revoked"}:
            raise TrustStoreError("key status must be trusted or revoked")
        if not isinstance(encoded, str):
            raise TrustStoreError("public key must be base64 text")
        try:
            public_key = base64.b64decode(encoded, validate=True)
        except ValueError as exc:
            raise TrustStoreError("public key is not valid base64") from exc
        if len(public_key) != 32:
            raise TrustStoreError("Ed25519 public key must be 32 bytes")
        keys[key_id] = TrustedKey(key_id, public_key, status)
    return MappingProxyType(keys)


class Ed25519Verifier:
    """Production verifier used by ``AvatarPack.open``.

    If the vetted cryptography backend is unavailable, verification returns
    false. No fallback algorithm or shell command is attempted.
    """

    def __init__(self, keys: Mapping[str, TrustedKey]) -> None:
        self._keys = MappingProxyType(dict(keys))

    @classmethod
    def from_file(cls, path: str | Path) -> "Ed25519Verifier":
        return cls(load_trust_store(path))

    @property
    def backend_available(self) -> bool:
        return Ed25519PublicKey is not None

    def verify(self, algorithm: str, key_id: str, payload: bytes, signature: bytes) -> bool:
        if algorithm != "Ed25519" or Ed25519PublicKey is None or len(signature) != 64:
            return False
        record = self._keys.get(key_id)
        if record is None or record.status != "trusted":
            return False
        try:
            Ed25519PublicKey.from_public_bytes(record.public_key).verify(signature, payload)
        except (InvalidSignature, ValueError, TypeError):
            return False
        return True
