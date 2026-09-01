"""Fail-closed null adapter for unsupported or absent capabilities."""

from __future__ import annotations

from typing import Any, Mapping

from core.protocols import (
    CAPABILITY_RISK_FLOORS,
    AdapterDescriptor,
    AdapterResult,
    Capability,
    InvocationContext,
    ResultStatus,
    SupportState,
)


class NullAdapter:
    """An adapter that can never report a successful capability operation."""

    def __init__(self, capability: Capability, *, reason: str = "adapter not configured") -> None:
        self._reason = reason
        self._shutdown = False
        self._descriptor = AdapterDescriptor(
            adapter_id=f"null.{capability.value}.v1",
            capability=capability,
            platform="portable-null",
            support_state=SupportState.TESTED,
            risk_class=CAPABILITY_RISK_FLOORS[capability],
            requires_network=False,
            evidence=("tests/test_gate1_contracts.py",),
        )

    @property
    def descriptor(self) -> AdapterDescriptor:
        return self._descriptor

    def invoke(
        self,
        operation: str,
        payload: Mapping[str, Any],
        context: InvocationContext,
    ) -> AdapterResult:
        del payload
        capability = self._descriptor.capability
        if self._shutdown:
            return AdapterResult(capability, ResultStatus.SHUTDOWN, "adapter is shut down")
        preflight = context.preflight(capability, operation)
        if preflight is not None:
            return preflight
        return AdapterResult(capability, ResultStatus.UNAVAILABLE, self._reason)

    def shutdown(self) -> None:
        self._shutdown = True
