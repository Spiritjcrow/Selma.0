"""Version 1 capability protocols for the platform-neutral SelmaOS core.

The contracts describe capabilities; they do not replace Selma's existing
tool registry, permission policy, replay protection, or append-only audit.
A real adapter receives an already-scoped invocation context and must still
route external effects through that single control plane.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from threading import Event
from time import monotonic
from types import MappingProxyType
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


_RISK_RANK = {
    RiskClass.READ: 0,
    RiskClass.SENSITIVE_READ: 1,
    RiskClass.APPROVED_WRITE: 2,
}

CAPABILITY_RISK_FLOORS: Mapping[Capability, RiskClass] = MappingProxyType(
    {
        Capability.MODEL: RiskClass.READ,
        Capability.MEMORY: RiskClass.SENSITIVE_READ,
        Capability.VOICE: RiskClass.SENSITIVE_READ,
        Capability.AVATAR: RiskClass.READ,
        Capability.DEVICE: RiskClass.SENSITIVE_READ,
        Capability.NOTIFICATION: RiskClass.APPROVED_WRITE,
        Capability.STORAGE: RiskClass.SENSITIVE_READ,
        Capability.PROCESS: RiskClass.APPROVED_WRITE,
        Capability.NETWORK: RiskClass.APPROVED_WRITE,
        Capability.PRESENTATION: RiskClass.APPROVED_WRITE,
    }
)


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
        if not isinstance(self.adapter_id, str) or not self.adapter_id.strip():
            raise ValueError("adapter_id must not be empty")
        if not isinstance(self.platform, str) or not self.platform.strip():
            raise ValueError("platform must not be empty")
        if not isinstance(self.contract_version, str) or not self.contract_version.strip():
            raise ValueError("contract_version must not be empty")
        if not isinstance(self.capability, Capability):
            raise TypeError("capability must be a Capability")
        if not isinstance(self.support_state, SupportState):
            raise TypeError("support_state must be a SupportState")
        if not isinstance(self.risk_class, RiskClass):
            raise TypeError("risk_class must be a RiskClass")
        floor = CAPABILITY_RISK_FLOORS[self.capability]
        if _RISK_RANK[self.risk_class] < _RISK_RANK[floor]:
            raise ValueError(
                f"{self.capability.value} adapters require at least {floor.value} risk"
            )


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
    capability: Capability | None = None
    operation: str | None = None
    deadline_monotonic: float | None = None
    cancellation: CancellationToken = field(default_factory=CancellationToken)

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not self.request_id.strip():
            raise ValueError("request_id must not be empty")
        if not isinstance(self.approved, bool):
            raise TypeError("approved must be a bool")
        if (self.capability is None) != (self.operation is None):
            raise ValueError("capability and operation scopes must be provided together")
        if self.capability is not None and not isinstance(self.capability, Capability):
            raise TypeError("capability scope must be a Capability")
        if self.operation is not None and (
            not isinstance(self.operation, str) or not self.operation.strip()
        ):
            raise ValueError("operation scope must not be empty")
        if self.approved and self.capability is None:
            raise ValueError("approved contexts require capability and operation scopes")
        if not isinstance(self.cancellation, CancellationToken):
            raise TypeError("cancellation must be a CancellationToken")
        if self.deadline_monotonic is not None:
            if isinstance(self.deadline_monotonic, bool) or not isinstance(
                self.deadline_monotonic, (int, float)
            ):
                raise TypeError("deadline_monotonic must be a number")
            if not isfinite(self.deadline_monotonic):
                raise ValueError("deadline_monotonic must be finite")

    @classmethod
    def approved_call(
        cls,
        request_id: str,
        *,
        capability: Capability,
        operation: str,
        timeout_seconds: float | None = None,
        cancellation: CancellationToken | None = None,
    ) -> "InvocationContext":
        if timeout_seconds is not None:
            if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
                raise TypeError("timeout_seconds must be a number")
            if not isfinite(timeout_seconds) or timeout_seconds < 0:
                raise ValueError("timeout_seconds must be finite and non-negative")
        deadline = None if timeout_seconds is None else monotonic() + float(timeout_seconds)
        return cls(
            request_id=request_id,
            approved=True,
            capability=capability,
            operation=operation,
            deadline_monotonic=deadline,
            cancellation=cancellation or CancellationToken(),
        )

    def preflight(self, capability: Capability, operation: str) -> AdapterResult | None:
        if self.cancellation.cancelled:
            return AdapterResult(capability, ResultStatus.CANCELLED, "request cancelled")
        if not self.approved:
            return AdapterResult(capability, ResultStatus.DENIED, "permission not granted")
        if self.capability is not capability or self.operation != operation:
            return AdapterResult(capability, ResultStatus.DENIED, "approval scope mismatch")
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
