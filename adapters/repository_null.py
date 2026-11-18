"""Fail-closed repository provider used for Selma Repo Fabric contract tests."""

from __future__ import annotations

from typing import Any, Mapping

from core.protocols import (
    CAPABILITY_RISK_FLOORS,
    AdapterDescriptor,
    AdapterResult,
    InvocationContext,
    ResultStatus,
    SupportState,
)
from core.repository import RepositoryRequest, RepositoryScope


class NullRepositoryProviderAdapter:
    def __init__(self, scope: RepositoryScope) -> None:
        if not isinstance(scope, RepositoryScope):
            raise TypeError("scope must be a RepositoryScope")
        self._scope = scope
        self._shutdown = False
        self._descriptor = AdapterDescriptor(
            adapter_id=f"repository-null:{scope.provider}",
            capability=scope.capability,
            platform=f"repository:{scope.provider}",
            support_state=SupportState.UNAVAILABLE,
            risk_class=CAPABILITY_RISK_FLOORS[scope.capability],
            requires_network=(scope.capability.value == "network"),
            evidence=("fail-closed null repository adapter",),
        )

    @property
    def descriptor(self) -> AdapterDescriptor:
        return self._descriptor

    @property
    def scope(self) -> RepositoryScope:
        return self._scope

    def invoke(
        self,
        request: RepositoryRequest,
        payload: Mapping[str, Any],
        context: InvocationContext,
    ) -> AdapterResult:
        if not isinstance(request, RepositoryRequest):
            raise TypeError("request must be a RepositoryRequest")
        if not isinstance(payload, Mapping):
            raise TypeError("payload must be a mapping")
        if not isinstance(context, InvocationContext):
            raise TypeError("context must be an InvocationContext")

        if self._shutdown:
            return AdapterResult(
                self._scope.capability,
                ResultStatus.SHUTDOWN,
                "repository adapter is shut down",
            )

        preflight = context.preflight(
            self._scope.capability,
            self._scope.operation_name(request.operation),
        )
        if preflight is not None:
            return preflight

        if not self._scope.authenticated:
            return AdapterResult(
                self._scope.capability,
                ResultStatus.DENIED,
                "provider identity unavailable",
            )
        if request.repository != self._scope.repository:
            return AdapterResult(
                self._scope.capability,
                ResultStatus.DENIED,
                "repository scope mismatch",
            )
        if request.ref != self._scope.ref:
            return AdapterResult(
                self._scope.capability,
                ResultStatus.DENIED,
                "repository ref scope mismatch",
            )
        if request.operation not in self._scope.allowed_operations:
            return AdapterResult(
                self._scope.capability,
                ResultStatus.DENIED,
                "repository operation not allowed",
            )
        if not self._scope.allows_path(request.path):
            return AdapterResult(
                self._scope.capability,
                ResultStatus.DENIED,
                "repository path outside vault scope",
            )

        return AdapterResult(
            self._scope.capability,
            ResultStatus.UNAVAILABLE,
            "repository provider is unavailable",
            data={
                "provider": self._scope.provider,
                "repository": self._scope.repository,
                "ref": self._scope.ref,
                "vault_id": self._scope.vault_id,
            },
        )

    def shutdown(self) -> None:
        self._shutdown = True
