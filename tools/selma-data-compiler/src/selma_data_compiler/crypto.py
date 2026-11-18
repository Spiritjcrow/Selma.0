from __future__ import annotations
from dataclasses import dataclass, asdict
import base64, hashlib, hmac, os
from pathlib import Path

@dataclass(slots=True)
class IntegrityRecord:
    algorithm: str
    sha256: str
    size: int
    def to_dict(self) -> dict: return asdict(self)

def integrity_record(path: Path) -> IntegrityRecord:
    h = hashlib.sha256(); size = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            size += len(chunk); h.update(chunk)
    return IntegrityRecord("sha256", h.hexdigest(), size)

def sign_bytes(data: bytes, key: bytes) -> str:
    return hmac.new(key, data, hashlib.sha256).hexdigest()

def generate_key_b64() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")

def encrypt_bytes(data: bytes, key_b64: str, associated_data: bytes = b"selma") -> dict:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:
        raise RuntimeError("AES-GCM requires optional dependency: pip install 'selma-data-compiler[crypto]'") from exc
    key = base64.urlsafe_b64decode(key_b64.encode("ascii"))
    if len(key) != 32: raise ValueError("Expected a 32-byte AES-256 key.")
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, data, associated_data)
    return {"algorithm":"AES-256-GCM","nonce_b64":base64.urlsafe_b64encode(nonce).decode("ascii"),"ciphertext_b64":base64.urlsafe_b64encode(ciphertext).decode("ascii"),"associated_data_b64":base64.urlsafe_b64encode(associated_data).decode("ascii")}

def decrypt_bytes(envelope: dict, key_b64: str) -> bytes:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:
        raise RuntimeError("AES-GCM requires optional dependency: pip install 'selma-data-compiler[crypto]'") from exc
    key = base64.urlsafe_b64decode(key_b64.encode("ascii"))
    nonce = base64.urlsafe_b64decode(envelope["nonce_b64"])
    ciphertext = base64.urlsafe_b64decode(envelope["ciphertext_b64"])
    aad = base64.urlsafe_b64decode(envelope["associated_data_b64"])
    return AESGCM(key).decrypt(nonce, ciphertext, aad)
