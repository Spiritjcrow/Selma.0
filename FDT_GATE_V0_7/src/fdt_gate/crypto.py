from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.exceptions import InvalidSignature


@dataclass(frozen=True)
class PublicKeyRef:
    key_id: str
    public_pem: str


def _key_id(public_key: Ed25519PublicKey) -> str:
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return "ed25519:" + hashlib.sha256(raw).hexdigest()[:32]


class Signer:
    def __init__(self, private_key: Ed25519PrivateKey):
        self._private = private_key
        self.public_key = private_key.public_key()
        self.key_id = _key_id(self.public_key)

    @classmethod
    def generate(cls) -> "Signer":
        return cls(Ed25519PrivateKey.generate())

    @classmethod
    def load(cls, path: str | Path) -> "Signer":
        data = Path(path).read_bytes()
        key = serialization.load_pem_private_key(data, password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise TypeError("expected Ed25519 private key")
        return cls(key)

    def save_private(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = self._private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        p.write_bytes(data)
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass

    def public_pem(self) -> str:
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")

    def sign(self, payload: bytes) -> str:
        return base64.urlsafe_b64encode(self._private.sign(payload)).decode("ascii")


class Keyring:
    def __init__(self) -> None:
        self._keys: dict[str, Ed25519PublicKey] = {}

    def add_pem(self, pem: str) -> str:
        key = serialization.load_pem_public_key(pem.encode("ascii"))
        if not isinstance(key, Ed25519PublicKey):
            raise TypeError("expected Ed25519 public key")
        kid = _key_id(key)
        self._keys[kid] = key
        return kid

    def add_signer(self, signer: Signer) -> str:
        self._keys[signer.key_id] = signer.public_key
        return signer.key_id

    def verify(self, key_id: str, payload: bytes, signature: str) -> bool:
        key = self._keys.get(key_id)
        if key is None:
            return False
        try:
            key.verify(base64.urlsafe_b64decode(signature.encode("ascii")), payload)
            return True
        except (InvalidSignature, ValueError):
            return False

    def contains(self, key_id: str) -> bool:
        return key_id in self._keys
