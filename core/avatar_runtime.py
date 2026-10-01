"""Portable offline avatar runtime primitives for SelmaOS Adult Mode.

No camera, microphone, network, or device actions are performed here. Real
platform effects remain behind SelmaOS permission, registry, and audit paths.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
from threading import RLock
from typing import Callable, Mapping, Protocol
import zlib

from core.protocols import AvatarState, CancellationToken

AVATAR_PACK_SCHEMA_VERSION = 1
AVATAR_RUNTIME_VERSION = "1.0.0"
_ALLOWED_COMPRESSION = frozenset({"none", "zlib"})


class AvatarPackError(ValueError):
    """Fail-closed avatar pack validation error."""


class AvatarPackSignatureError(AvatarPackError):
    pass


class AvatarChunkError(AvatarPackError):
    pass


def _version_tuple(value: str) -> tuple[int, int, int]:
    parts = value.split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise AvatarPackError("runtime versions must use numeric major.minor.patch format")
    return int(parts[0]), int(parts[1]), int(parts[2])


@dataclass(frozen=True, slots=True)
class AvatarChunkIndex:
    chunk_id: str
    path: str
    sha256_hex: str
    stored_size: int
    raw_size: int
    compression: str = "none"

    def __post_init__(self) -> None:
        if not self.chunk_id.strip():
            raise AvatarPackError("chunk_id must not be empty")
        path = PurePosixPath(self.path)
        if path.is_absolute() or ".." in path.parts or self.path in {"", "."}:
            raise AvatarPackError("chunk path must be a safe relative path")
        if len(self.sha256_hex) != 64 or any(c not in "0123456789abcdef" for c in self.sha256_hex):
            raise AvatarPackError("chunk sha256 must be lowercase hex")
        if self.stored_size < 0 or self.raw_size < 0:
            raise AvatarPackError("chunk sizes must be non-negative")
        if self.compression not in _ALLOWED_COMPRESSION:
            raise AvatarPackError(f"unsupported compression: {self.compression}")


@dataclass(frozen=True, slots=True)
class AvatarPackManifest:
    pack_id: str
    pack_version: str
    identity_id: str
    minimum_runtime_version: str
    capabilities: tuple[str, ...]
    chunks: tuple[AvatarChunkIndex, ...]
    schema_version: int = AVATAR_PACK_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name, value in (
            ("pack_id", self.pack_id),
            ("pack_version", self.pack_version),
            ("identity_id", self.identity_id),
            ("minimum_runtime_version", self.minimum_runtime_version),
        ):
            if not isinstance(value, str) or not value.strip():
                raise AvatarPackError(f"{name} must not be empty")
        if self.schema_version != AVATAR_PACK_SCHEMA_VERSION:
            raise AvatarPackError("unsupported avatar pack schema version")
        if _version_tuple(self.minimum_runtime_version) > _version_tuple(AVATAR_RUNTIME_VERSION):
            raise AvatarPackError("avatar pack requires a newer runtime")
        if not self.capabilities or any(not item.strip() for item in self.capabilities):
            raise AvatarPackError("capabilities must contain non-empty values")
        if len(self.capabilities) != len(set(self.capabilities)):
            raise AvatarPackError("capabilities must be unique")
        ids = [c.chunk_id for c in self.chunks]
        paths = [c.path for c in self.chunks]
        if len(ids) != len(set(ids)) or len(paths) != len(set(paths)):
            raise AvatarPackError("chunk ids and paths must be unique")

    def canonical_payload(self) -> bytes:
        body = {
            "schema_version": self.schema_version,
            "pack_id": self.pack_id,
            "pack_version": self.pack_version,
            "identity_id": self.identity_id,
            "minimum_runtime_version": self.minimum_runtime_version,
            "capabilities": list(self.capabilities),
            "chunks": [
                {
                    "chunk_id": c.chunk_id,
                    "path": c.path,
                    "sha256": c.sha256_hex,
                    "stored_size": c.stored_size,
                    "raw_size": c.raw_size,
                    "compression": c.compression,
                }
                for c in self.chunks
            ],
        }
        return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "AvatarPackManifest":
        try:
            raw_chunks = data["chunks"]
            if not isinstance(raw_chunks, list):
                raise TypeError("chunks must be a list")
            chunks: list[AvatarChunkIndex] = []
            for item in raw_chunks:
                if not isinstance(item, Mapping):
                    raise TypeError("every chunk must be an object")
                for key in ("chunk_id", "path", "sha256"):
                    if not isinstance(item.get(key), str):
                        raise TypeError(f"{key} must be a string")
                for key in ("stored_size", "raw_size"):
                    value = item.get(key)
                    if isinstance(value, bool) or not isinstance(value, int):
                        raise TypeError(f"{key} must be an integer")
                compression = item.get("compression", "none")
                if not isinstance(compression, str):
                    raise TypeError("compression must be a string")
                chunks.append(
                    AvatarChunkIndex(
                        chunk_id=item["chunk_id"],
                        path=item["path"],
                        sha256_hex=item["sha256"],
                        stored_size=item["stored_size"],
                        raw_size=item["raw_size"],
                        compression=compression,
                    )
                )
            caps = data.get("capabilities", [])
            if not isinstance(caps, list) or not all(isinstance(x, str) for x in caps):
                raise TypeError("capabilities must be a string list")
            for key in ("pack_id", "pack_version", "identity_id", "minimum_runtime_version"):
                if not isinstance(data.get(key), str):
                    raise TypeError(f"{key} must be a string")
            schema = data.get("schema_version", 0)
            if isinstance(schema, bool) or not isinstance(schema, int):
                raise TypeError("schema_version must be an integer")
            return cls(
                pack_id=data["pack_id"],
                pack_version=data["pack_version"],
                identity_id=data["identity_id"],
                minimum_runtime_version=data["minimum_runtime_version"],
                capabilities=tuple(caps),
                chunks=tuple(chunks),
                schema_version=schema,
            )
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, AvatarPackError):
                raise
            raise AvatarPackError(f"invalid avatar manifest: {exc}") from exc


SignatureVerifier = Callable[[bytes, bytes], bool]


def load_verified_manifest(
    manifest_path: Path,
    signature_path: Path,
    verifier: SignatureVerifier,
) -> AvatarPackManifest:
    """Load a manifest only after its detached signature verifies.

    The cryptographic provider is injected so platform packaging can use a
    vetted Ed25519 implementation rather than a home-grown primitive here.
    """

    raw = manifest_path.read_bytes()
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AvatarPackError("manifest is not valid UTF-8 JSON") from exc
    if not isinstance(data, Mapping):
        raise AvatarPackError("manifest root must be an object")
    manifest = AvatarPackManifest.from_mapping(data)
    signature = signature_path.read_bytes()
    try:
        verified = bool(signature) and verifier(manifest.canonical_payload(), signature)
    except Exception as exc:
        raise AvatarPackSignatureError("avatar pack signature verifier failed closed") from exc
    if not verified:
        raise AvatarPackSignatureError("avatar pack signature verification failed")
    return manifest


class BoundedChunkReader:
    """Lazy hash-verified reader with size ceilings and byte-bounded LRU cache."""

    def __init__(
        self,
        root: Path,
        manifest: AvatarPackManifest,
        *,
        cache_ceiling_bytes: int = 8 * 1024 * 1024,
        max_stored_chunk_bytes: int = 4 * 1024 * 1024,
        max_raw_chunk_bytes: int = 16 * 1024 * 1024,
    ) -> None:
        if cache_ceiling_bytes < 0 or max_stored_chunk_bytes <= 0 or max_raw_chunk_bytes <= 0:
            raise ValueError("avatar reader limits are invalid")
        self._root = root.resolve()
        self._index = {c.chunk_id: c for c in manifest.chunks}
        self._cache_ceiling = cache_ceiling_bytes
        self._max_stored = max_stored_chunk_bytes
        self._max_raw = max_raw_chunk_bytes
        self._cache: OrderedDict[str, bytes] = OrderedDict()
        self._cache_bytes = 0
        self._lock = RLock()

    @property
    def cache_bytes(self) -> int:
        return self._cache_bytes

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._cache_bytes = 0

    def read(self, chunk_id: str, *, cancellation: CancellationToken | None = None) -> bytes:
        if cancellation is not None and cancellation.cancelled:
            raise AvatarChunkError("chunk read cancelled")
        with self._lock:
            cached = self._cache.get(chunk_id)
            if cached is not None:
                self._cache.move_to_end(chunk_id)
                return cached
        meta = self._index.get(chunk_id)
        if meta is None:
            raise AvatarChunkError(f"unknown avatar chunk: {chunk_id}")
        if meta.stored_size > self._max_stored or meta.raw_size > self._max_raw:
            raise AvatarChunkError("chunk exceeds configured size ceiling")
        candidate = (self._root / meta.path).resolve()
        try:
            candidate.relative_to(self._root)
        except ValueError as exc:
            raise AvatarChunkError("chunk path escaped avatar pack root") from exc
        stored = candidate.read_bytes()
        if len(stored) != meta.stored_size:
            raise AvatarChunkError("stored chunk size mismatch")
        if sha256(stored).hexdigest() != meta.sha256_hex:
            raise AvatarChunkError("stored chunk hash mismatch")
        if cancellation is not None and cancellation.cancelled:
            raise AvatarChunkError("chunk read cancelled")
        if meta.compression == "none":
            raw = stored
        else:
            decoder = zlib.decompressobj()
            raw = decoder.decompress(stored, meta.raw_size + 1)
            if len(raw) > meta.raw_size or decoder.unconsumed_tail:
                raise AvatarChunkError("decompressed chunk exceeds declared size")
            raw += decoder.flush()
            if not decoder.eof or len(raw) != meta.raw_size:
                raise AvatarChunkError("decompressed chunk size mismatch")
        if len(raw) != meta.raw_size:
            raise AvatarChunkError("raw chunk size mismatch")
        with self._lock:
            if self._cache_ceiling and len(raw) <= self._cache_ceiling:
                while self._cache and self._cache_bytes + len(raw) > self._cache_ceiling:
                    _, evicted = self._cache.popitem(last=False)
                    self._cache_bytes -= len(evicted)
                self._cache[chunk_id] = raw
                self._cache_bytes += len(raw)
        return raw


@dataclass(frozen=True, slots=True)
class GazeTarget:
    x: float = 0.0
    y: float = 0.0

    def __post_init__(self) -> None:
        if not (-1.0 <= self.x <= 1.0 and -1.0 <= self.y <= 1.0):
            raise ValueError("gaze coordinates must be normalized to [-1, 1]")


@dataclass(frozen=True, slots=True)
class AvatarEvent:
    sequence: int
    generation: int
    state: AvatarState
    expression: str = "neutral"
    gesture: str = "none"
    gaze: GazeTarget = field(default_factory=GazeTarget)
    viseme: str = "sil"
    mouth_open: float = 0.0
    user_priority: bool = False

    def __post_init__(self) -> None:
        if self.sequence < 0 or self.generation < 0:
            raise ValueError("sequence and generation must be non-negative")
        if not 0.0 <= self.mouth_open <= 1.0:
            raise ValueError("mouth_open must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class AvatarSnapshot:
    sequence: int
    generation: int
    state: AvatarState
    expression: str
    gesture: str
    gaze: GazeTarget
    viseme: str
    mouth_open: float
    frame_number: int


class AvatarRenderer(Protocol):
    supports_zero_copy: bool
    def render(self, event: AvatarEvent) -> AvatarSnapshot: ...
    def stop(self) -> None: ...


class ByteBufferPool:
    """Fixed-capacity reusable scratch buffers; data is zeroized on release."""

    def __init__(self, *, buffer_size: int, capacity: int) -> None:
        if buffer_size <= 0 or capacity <= 0:
            raise ValueError("buffer pool dimensions must be positive")
        self._buffer_size = buffer_size
        self._available = [bytearray(buffer_size) for _ in range(capacity)]
        self._capacity = capacity
        self._lock = RLock()

    def acquire(self) -> bytearray:
        with self._lock:
            return self._available.pop() if self._available else bytearray(self._buffer_size)

    def release(self, buffer: bytearray) -> None:
        if len(buffer) != self._buffer_size:
            raise ValueError("buffer size mismatch")
        buffer[:] = b"\x00" * len(buffer)
        with self._lock:
            if len(self._available) < self._capacity:
                self._available.append(buffer)


class SoftwareAvatarRenderer:
    """Deterministic renderer-neutral fallback."""

    supports_zero_copy = False

    def __init__(self) -> None:
        self._frame = 0
        self._stopped = False

    def render(self, event: AvatarEvent) -> AvatarSnapshot:
        if self._stopped:
            raise RuntimeError("avatar renderer is stopped")
        self._frame += 1
        return AvatarSnapshot(
            event.sequence, event.generation, event.state, event.expression,
            event.gesture, event.gaze, event.viseme, event.mouth_open, self._frame
        )

    def stop(self) -> None:
        self._stopped = True


@dataclass(frozen=True, slots=True)
class PerformanceBudget:
    target_fps: int = 30
    resolution_scale: float = 1.0
    texture_quality: int = 3
    animation_hz: int = 60
    expression_complexity: int = 3
    audio_buffer_ms: int = 40
    cache_ceiling_bytes: int = 8 * 1024 * 1024
    effects_enabled: bool = True


@dataclass(frozen=True, slots=True)
class RuntimeMetrics:
    frame_time_ms: float | None = None
    memory_pressure: float | None = None
    thermal_level: int | None = None
    battery_saver: bool | None = None


class PerformanceController:
    """Degrade only in response to telemetry explicitly supplied by a platform."""

    def __init__(self, budget: PerformanceBudget | None = None) -> None:
        self._budget = budget or PerformanceBudget()

    @property
    def budget(self) -> PerformanceBudget:
        return self._budget

    def observe(self, metrics: RuntimeMetrics) -> PerformanceBudget:
        b = self._budget
        overloaded = metrics.frame_time_ms is not None and metrics.frame_time_ms > (1000.0 / b.target_fps) * 1.15
        memory_hot = metrics.memory_pressure is not None and metrics.memory_pressure >= 0.80
        thermal_hot = metrics.thermal_level is not None and metrics.thermal_level >= 2
        battery_limited = metrics.battery_saver is True
        if overloaded or memory_hot or thermal_hot or battery_limited:
            self._budget = PerformanceBudget(
                target_fps=max(15, b.target_fps - 5),
                resolution_scale=max(0.50, round(b.resolution_scale - 0.10, 2)),
                texture_quality=max(1, b.texture_quality - 1),
                animation_hz=max(24, b.animation_hz - 10),
                expression_complexity=max(1, b.expression_complexity - 1),
                audio_buffer_ms=min(120, b.audio_buffer_ms + 10),
                cache_ceiling_bytes=max(1024 * 1024, b.cache_ceiling_bytes // 2 if memory_hot else b.cache_ceiling_bytes),
                effects_enabled=False if thermal_hot or battery_limited else b.effects_enabled,
            )
        return self._budget


class AvatarRuntime:
    """Ordered event controller with stale-generation cancellation and kill switch."""

    def __init__(
        self,
        renderer: AvatarRenderer | None = None,
        *,
        chunk_reader: BoundedChunkReader | None = None,
        audio_drain: Callable[[], None] | None = None,
        capture_stop: Callable[[], None] | None = None,
    ) -> None:
        self._renderer = renderer or SoftwareAvatarRenderer()
        self._chunk_reader = chunk_reader
        self._audio_drain = audio_drain or (lambda: None)
        self._capture_stop = capture_stop or (lambda: None)
        self._generation = 0
        self._last_sequence = -1
        self._killed = False
        self._snapshot: AvatarSnapshot | None = None
        self._lock = RLock()

    @property
    def killed(self) -> bool:
        return self._killed

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def snapshot(self) -> AvatarSnapshot | None:
        return self._snapshot

    def next_generation(self) -> int:
        with self._lock:
            if self._killed:
                raise RuntimeError("avatar runtime is killed")
            self._generation += 1
            self._last_sequence = -1
            return self._generation

    def apply(self, event: AvatarEvent, *, cancellation: CancellationToken | None = None) -> AvatarSnapshot | None:
        with self._lock:
            if self._killed or (cancellation is not None and cancellation.cancelled):
                return None
            if event.generation != self._generation or event.sequence <= self._last_sequence:
                return None
            if event.user_priority and event.state is AvatarState.INTERRUPTED:
                self._audio_drain()
            self._snapshot = self._renderer.render(event)
            self._last_sequence = event.sequence
            return self._snapshot

    def request_zero_copy(self) -> bool:
        return bool(self._renderer.supports_zero_copy)

    def kill(self) -> None:
        with self._lock:
            if self._killed:
                return
            self._killed = True
            self._audio_drain()
            self._capture_stop()
            if self._chunk_reader is not None:
                self._chunk_reader.clear()
            self._renderer.stop()
            self._snapshot = None
