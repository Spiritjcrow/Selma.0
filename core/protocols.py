"""Version 1 capability protocols for the platform-neutral SelmaOS core.

The contracts describe capabilities; they do not replace Selma's existing
tool registry, permission policy, replay protection, or append-only audit.
A real adapter receives an already-scoped invocation context and must still
route external effects through that single control plane.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from threading import Event
from time import monotonic
from typing import Any, Mapping, Protocol, runtime_checkable

CONTRACT_VERSION = "1.0.0"


class Capability(StrEnum):
    MODEL = "model"
    MEMORY = "memory"
    VOICE = "voice"
    AVATAR = "avatar"
    DEVICE = "device"
    NOTIFICATION = "notification"
    STORAGE = "storage"
    PROCESS = "process"
    NETWORK = "network"
    PRESENTATION = "presentation"


ALL_CAPABILITIES = tuple(Capability)


class SupportState(StrEnum):
    IMPLEMENTED = "implemented"
    TESTED = "tested"
    UNAVAILABLE = "unavailable"
    PLANNED = "planned"


class RiskClass(StrEnum):
    READ = "read"
    SENSITIVE_READ = "sensitive_read"
    APPROVED_WRITE = "approved_write"


class ResultStatus(StrEnum):
    SUCCESS = "success"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    DENIED = "denied"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    SHUTDOWN = "shutdown"
    ERROR = "error"


class AvatarState(StrEnum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    INTERRUPTED = "INTERRUPTED"
    SLEEPING = "SLEEPING"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class AdapterDescriptor:
    adapter_id: str
    capability: Capability
    platform: str
    support_state: SupportState
    risk_class: RiskClass
    contract_version: str = CONTRACT_VERSION
    requires_network: bool = False
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.adapter_id.strip():
            raise ValueError("adapter_id must not be empty")
        if not self.platform.strip():
            raise ValueError("platform must not be empty")
        if not self.contract_version.strip():
            raise ValueError("contract_version must not be empty")


@dataclass(frozen=True, slots=True)
class AdapterResult:
    capability: Capability
    status: ResultStatus
    message: str
    data: Mapping[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Success is derived from the status and cannot be self-reported."""

        return self.status is ResultStatus.SUCCESS


class CancellationToken:
    """Thread-safe, local cancellation signal shared across adapter calls."""

    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()


@dataclass(frozen=True, slots=True)
class InvocationContext:
    """A bounded call context issued by the existing Selma control plane.

    ``approved`` is deliberately false by default. This object carries a
    decision; it does not make or persist permission decisions itself.
    """

    request_id: str
    approved: bool = False
    deadline_monotonic: float | None = None
    cancellation: CancellationToken = field(default_factory=CancellationToken)

    @classmethod
    def approved_call(
        cls,
        request_id: str,
        *,
        timeout_seconds: float | None = None,
        cancellation: CancellationToken | None = None,
    ) -> "InvocationContext":
        if timeout_seconds is not None and timeout_seconds < 0:
            raise ValueError("timeout_seconds must be non-negative")
        deadline = None if timeout_seconds is None else monotonic() + timeout_seconds
        return cls(
            request_id=request_id,
            approved=True,
            deadline_monotonic=deadline,
            cancellation=cancellation or CancellationToken(),
        )

    def preflight(self, capability: Capability) -> AdapterResult | None:
        if self.cancellation.cancelled:
            return AdapterResult(capability, ResultStatus.CANCELLED, "request cancelled")
        if not self.approved:
            return AdapterResult(capability, ResultStatus.DENIED, "permission not granted")
        if self.deadline_monotonic is not None and monotonic() >= self.deadline_monotonic:
            return AdapterResult(capability, ResultStatus.TIMED_OUT, "deadline expired")
        return None


@runtime_checkable
class CapabilityAdapter(Protocol):
    @property
    def descriptor(self) -> AdapterDescriptor: ...

    def invoke(
        self,
        operation: str,
        payload: Mapping[str, Any],
        context: InvocationContext,
    ) -> AdapterResult: ...

    def shutdown(self) -> None: ...


@runtime_checkable
class ModelAdapter(CapabilityAdapter, Protocol):
    def generate(self, prompt: str, context: InvocationContext) -> AdapterResult: ...


@runtime_checkable
class MemoryAdapter(CapabilityAdapter, Protocol):
    def retrieve(self, query: str, limit: int, context: InvocationContext) -> AdapterResult: ...


@runtime_checkable
class VoiceAdapter(CapabilityAdapter, Protocol):
    def transcribe(self, audio: bytes, context: InvocationContext) -> AdapterResult: ...

    def synthesize(self, text: str, context: InvocationContext) -> AdapterResult: ...


@runtime_checkable
class AvatarAdapter(CapabilityAdapter, Protocol):
    def transition(
        self,
        state: AvatarState,
        sequence: int,
        context: InvocationContext,
    ) -> AdapterResult: ...


@runtime_checkable
class DeviceAdapter(CapabilityAdapter, Protocol):
    def read(self, resource: str, context: InvocationContext) -> AdapterResult: ...

    def perform(
        self,
        action: str,
        arguments: Mapping[str, Any],
        context: InvocationContext,
    ) -> AdapterResult: ...


@runtime_checkable
class NotificationAdapter(CapabilityAdapter, Protocol):
    def publish(self, message: str, context: InvocationContext) -> AdapterResult: ...


@runtime_checkable
class StorageAdapter(CapabilityAdapter, Protocol):
    def read(self, key: str, context: InvocationContext) -> AdapterResult: ...

    def write(self, key: str, value: bytes, context: InvocationContext) -> AdapterResult: ...


@runtime_checkable
class ProcessAdapter(CapabilityAdapter, Protocol):
    def run(
        self,
        executable_id: str,
        arguments: tuple[str, ...],
        context: InvocationContext,
    ) -> AdapterResult: ...


@runtime_checkable
class NetworkAdapter(CapabilityAdapter, Protocol):
    def request(
        self,
        endpoint_id: str,
        payload: Mapping[str, Any],
        context: InvocationContext,
    ) -> AdapterResult: ...


@runtime_checkable
class PresentationAdapter(CapabilityAdapter, Protocol):
    def present(self, mode: str, context: InvocationContext) -> AdapterResult: ...

    def dismiss(self, context: InvocationContext) -> AdapterResult: ...
