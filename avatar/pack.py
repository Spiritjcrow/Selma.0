"""Fail-closed Avatar Pack v1 verifier and bounded lazy chunk reader."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from types import MappingProxyType
from typing import Any, Mapping, Protocol
import zlib

from core.protocols import AvatarState

PACK_SCHEMA_VERSION = "1.0.0"
PACK_CONTRACT = "selma.avatar-pack.v1"
MAX_MANIFEST_BYTES = 256 * 1024
MAX_CHUNKS = 4096


class AvatarPackError(ValueError):
    """A pack is corrupt, incompatible, unauthenticated, or over budget."""


class SignatureVerifier(Protocol):
    """Platform crypto boundary. Production must provide an Ed25519 verifier."""

    def verify(self, algorithm: str, key_id: str, payload: bytes, signature: bytes) -> bool: ...


class RejectAllSignatures:
    """Safe default: unsigned/unverifiable packs never activate."""

    def verify(self, algorithm: str, key_id: str, payload: bytes, signature: bytes) -> bool:
        return False


def _object_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AvatarPackError(f"duplicate manifest key: {key}")
        result[key] = value
    return result


def _canonical_unsigned(manifest: Mapping[str, Any]) -> bytes:
    unsigned = dict(manifest)
    unsigned.pop("signature", None)
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _required(mapping: Mapping[str, Any], key: str, expected: type) -> Any:
    value = mapping.get(key)
    if not isinstance(value, expected):
        raise AvatarPackError(f"{key} must be {expected.__name__}")
    return value


def _safe_chunk_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in ("", ".", "..") for part in path.parts):
        raise AvatarPackError("chunk path must be a normalized relative POSIX path")
    return path


@dataclass(frozen=True, slots=True)
class ChunkRecord:
    chunk_id: str
    path: PurePosixPath
    encoding: str
    encoded_size: int
    decoded_size: int
    sha256: str


class AvatarPack:
    """A verified local pack with a byte-bounded decoded LRU cache."""

    def __init__(
        self,
        root: Path,
        manifest: Mapping[str, Any],
        chunks: Mapping[str, ChunkRecord],
        *,
        cache_limit_bytes: int,
        chunk_limit_bytes: int,
    ) -> None:
        self.root = root.resolve()
        self.manifest = MappingProxyType(dict(manifest))
        self.chunks = MappingProxyType(dict(chunks))
        self.cache_limit_bytes = cache_limit_bytes
        self.chunk_limit_bytes = chunk_limit_bytes
        self._cache: OrderedDict[str, bytes] = OrderedDict()
        self._cache_bytes = 0

    @classmethod
    def open(
        cls,
        root: str | Path,
        *,
        signature_verifier: SignatureVerifier | None = None,
        cache_limit_bytes: int = 8 * 1024 * 1024,
        chunk_limit_bytes: int = 4 * 1024 * 1024,
    ) -> "AvatarPack":
        if cache_limit_bytes < 0 or chunk_limit_bytes <= 0:
            raise AvatarPackError("cache and chunk limits must be bounded positive values")
        root_path = Path(root).resolve()
        manifest_path = root_path / "manifest.json"
        raw = manifest_path.read_bytes()
        if len(raw) > MAX_MANIFEST_BYTES:
            raise AvatarPackError("manifest exceeds size limit")
        try:
            manifest = json.loads(raw, object_pairs_hook=_object_no_duplicates)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise AvatarPackError("manifest is not strict UTF-8 JSON") from exc
        if not isinstance(manifest, dict):
            raise AvatarPackError("manifest root must be an object")
        cls._validate_identity(manifest)
        signature = _required(manifest, "signature", dict)
        algorithm = _required(signature, "algorithm", str)
        key_id = _required(signature, "key_id", str)
        encoded_signature = _required(signature, "value_base64", str)
        try:
            signature_bytes = base64.b64decode(encoded_signature, validate=True)
        except ValueError as exc:
            raise AvatarPackError("signature is not valid base64") from exc
        verifier = signature_verifier or RejectAllSignatures()
        if not verifier.verify(algorithm, key_id, _canonical_unsigned(manifest), signature_bytes):
            raise AvatarPackError("manifest signature verification failed")
        chunks = cls._validate_chunks(manifest, chunk_limit_bytes)
        return cls(root_path, manifest, chunks, cache_limit_bytes=cache_limit_bytes, chunk_limit_bytes=chunk_limit_bytes)

    @staticmethod
    def _validate_identity(manifest: Mapping[str, Any]) -> None:
        if manifest.get("schema_version") != PACK_SCHEMA_VERSION:
            raise AvatarPackError("unsupported schema_version")
        if manifest.get("contract") != PACK_CONTRACT:
            raise AvatarPackError("unsupported pack contract")
        pack_id = _required(manifest, "pack_id", str)
        if re.fullmatch(r"avatar-pack:[a-z0-9][a-z0-9._-]*", pack_id) is None:
            raise AvatarPackError("pack_id is not stable/canonical")
        if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", _required(manifest, "pack_version", str)) is None:
            raise AvatarPackError("pack_version must be semantic major.minor.patch")
        personification_id = _required(manifest, "personification_id", str)
        if re.fullmatch(r"personification:[a-z0-9][a-z0-9._-]*", personification_id) is None:
            raise AvatarPackError("personification_id is not stable/canonical")
        states = _required(manifest, "states", list)
        expected = {state.value for state in AvatarState}
        if set(states) != expected or len(states) != len(expected):
            raise AvatarPackError("states must exactly match the Gate 1 AvatarState contract")

    @staticmethod
    def _validate_chunks(manifest: Mapping[str, Any], chunk_limit: int) -> dict[str, ChunkRecord]:
        raw_chunks = _required(manifest, "chunks", list)
        if not raw_chunks or len(raw_chunks) > MAX_CHUNKS:
            raise AvatarPackError("chunk count is empty or exceeds limit")
        chunks: dict[str, ChunkRecord] = {}
        paths: set[PurePosixPath] = set()
        for item in raw_chunks:
            if not isinstance(item, dict):
                raise AvatarPackError("chunk record must be an object")
            chunk_id = _required(item, "chunk_id", str)
            path = _safe_chunk_path(_required(item, "path", str))
            encoding = _required(item, "encoding", str)
            encoded_size = _required(item, "encoded_size", int)
            decoded_size = _required(item, "decoded_size", int)
            digest = _required(item, "sha256", str)
            if chunk_id in chunks or path in paths:
                raise AvatarPackError("duplicate chunk id or path")
            if encoding not in {"stored", "zlib"}:
                raise AvatarPackError("unsupported chunk encoding")
            if isinstance(encoded_size, bool) or isinstance(decoded_size, bool):
                raise AvatarPackError("chunk sizes must be integers")
            if encoded_size < 0 or decoded_size < 0 or encoded_size > chunk_limit or decoded_size > chunk_limit:
                raise AvatarPackError("chunk exceeds configured size limit")
            if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise AvatarPackError("chunk sha256 must be lowercase hexadecimal")
            chunks[chunk_id] = ChunkRecord(chunk_id, path, encoding, encoded_size, decoded_size, digest)
            paths.add(path)
        return chunks

    def read_chunk(self, chunk_id: str) -> bytes:
        if chunk_id in self._cache:
            self._cache.move_to_end(chunk_id)
            return self._cache[chunk_id]
        try:
            record = self.chunks[chunk_id]
        except KeyError as exc:
            raise AvatarPackError("unknown chunk id") from exc
        candidate = (self.root / Path(*record.path.parts)).resolve()
        if self.root not in candidate.parents:
            raise AvatarPackError("chunk path escaped pack root")
        if candidate.stat().st_size != record.encoded_size or candidate.stat().st_size > self.chunk_limit_bytes:
            raise AvatarPackError("encoded chunk size mismatch")
        raw = candidate.read_bytes()
        if len(raw) != record.encoded_size or len(raw) > self.chunk_limit_bytes:
            raise AvatarPackError("encoded chunk size mismatch")
        if hashlib.sha256(raw).hexdigest() != record.sha256:
            raise AvatarPackError("chunk digest mismatch")
        if record.encoding == "stored":
            decoded = raw
        else:
            decoder = zlib.decompressobj()
            try:
                decoded = decoder.decompress(raw, self.chunk_limit_bytes + 1)
                if decoder.unconsumed_tail or len(decoded) > self.chunk_limit_bytes:
                    raise AvatarPackError("decoded chunk size mismatch or limit exceeded")
                decoded += decoder.flush(max(1, self.chunk_limit_bytes + 1 - len(decoded)))
            except zlib.error as exc:
                raise AvatarPackError("invalid compressed chunk") from exc
            if decoder.unused_data or decoder.unconsumed_tail or not decoder.eof:
                raise AvatarPackError("compressed chunk has trailing or oversized data")
        if len(decoded) != record.decoded_size or len(decoded) > self.chunk_limit_bytes:
            raise AvatarPackError("decoded chunk size mismatch or limit exceeded")
        if len(decoded) <= self.cache_limit_bytes:
            while self._cache and self._cache_bytes + len(decoded) > self.cache_limit_bytes:
                _, evicted = self._cache.popitem(last=False); self._cache_bytes -= len(evicted)
            self._cache[chunk_id] = decoded; self._cache_bytes += len(decoded)
        return decoded

    @property
    def cache_bytes(self) -> int:
        return self._cache_bytes

    def close(self) -> None:
        self._cache.clear(); self._cache_bytes = 0
