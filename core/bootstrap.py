"""Offline Gate 1 bootstrap using fail-closed null capability adapters."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping

from adapters.null import NullAdapter
from core.protocols import ALL_CAPABILITIES, Capability, ResultStatus


class RuntimeState(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"


@dataclass(frozen=True, slots=True)
class RuntimeHealth:
    state: RuntimeState
    offline: bool
    capability_status: Mapping[str, str]


class OfflineCore:
    """Minimal side-effect-free core used to prove honest degraded boot."""

    def __init__(self) -> None:
        self._state = RuntimeState.CREATED
        self._adapters = {capability: NullAdapter(capability) for capability in ALL_CAPABILITIES}

    @property
    def state(self) -> RuntimeState:
        return self._state

    def boot(self, *, allow_network: bool = False) -> RuntimeHealth:
        if allow_network:
            raise ValueError("Gate 1 null bootstrap is offline-only")
        if self._state is RuntimeState.STOPPED:
            raise RuntimeError("a stopped core cannot be rebooted; construct a new instance")
        self._state = RuntimeState.RUNNING
        return self.health()

    def adapter(self, capability: Capability) -> NullAdapter:
        return self._adapters[capability]

    def health(self) -> RuntimeHealth:
        statuses = {
            capability.value: ResultStatus.UNAVAILABLE.value
            for capability in ALL_CAPABILITIES
        }
        return RuntimeHealth(
            state=self._state,
            offline=True,
            capability_status=MappingProxyType(statuses),
        )

    def shutdown(self) -> RuntimeHealth:
        for adapter in self._adapters.values():
            adapter.shutdown()
        self._state = RuntimeState.STOPPED
        return self.health()
