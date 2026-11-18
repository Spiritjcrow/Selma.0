"""Repository-provider scope contracts for Selma's federated development fabric.

This module defines scope and request validation only. It does not authenticate to
providers, open network connections, execute builds, or authorize external effects.
Real provider adapters must still receive an approved InvocationContext from the
existing Selma control plane.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any, Mapping, Protocol, runtime_checkable

from .protocols import AdapterDescriptor, AdapterResult, Capability, InvocationContext


class RepositoryOperation(StrEnum):
    READ = "read"
    WRITE = "write"
    BUILD = "build"
    DEPLOY = "deploy"


@dataclass(frozen=True, slots=True)
class RepositoryScope:
    provider: str
    repository: str
    ref: str
    vault_id: str
    identity: str | None = None
    capability: Capability = Capability.NETWORK
    allowed_operations: frozenset[RepositoryOperation] = field(
        default_factory=lambda: frozenset({RepositoryOperation.READ})
    )
    path_prefixes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, value in (
            ("provider", self.provider),
            ("repository", self.repository),
            ("ref", self.ref),
            ("vault_id", self.vault_id),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must not be empty")
            if len(value) > 512:
                raise ValueError(f"{name} is too long")
        if self.identity is not None and (
            not isinstance(self.identity, str) or not self.identity.strip()
        ):
            raise ValueError("identity must be non-empty when provided")
        if not isinstance(self.capability, Capability):
            raise TypeError("capability must be a Capability")
        if not self.allowed_operations:
            raise ValueError("allowed_operations must not be empty")
        for operation in self.allowed_operations:
            if not isinstance(operation, RepositoryOperation):
                raise TypeError("allowed_operations must contain RepositoryOperation values")
        normalized = tuple(self._normalize_prefix(prefix) for prefix in self.path_prefixes)
        if len(set(normalized)) != len(normalized):
            raise ValueError("path_prefixes must not contain duplicates")
        object.__setattr__(self, "path_prefixes", normalized)

    @staticmethod
    def _normalize_prefix(prefix: str) -> str:
        if not isinstance(prefix, str) or not prefix.strip():
            raise ValueError("path prefix must not be empty")
        value = prefix.replace("\\", "/").strip().strip("/")
        RepositoryScope._validate_relative_path(value)
        return value.rstrip("/")

    @staticmethod
    def _validate_relative_path(path: str) -> str:
        if not isinstance(path, str):
            raise TypeError("repository path must be a string")
        if "\x00" in path:
            raise ValueError("repository path contains NUL")
        value = path.replace("\\", "/").strip()
        if not value:
            return ""
        pure = PurePosixPath(value)
        if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
            raise ValueError("repository path must be normalized and relative")
        return pure.as_posix()

    @property
    def authenticated(self) -> bool:
        return bool(self.identity and self.identity.strip())

    def allows_path(self, path: str) -> bool:
        normalized = self._validate_relative_path(path)
        if not self.path_prefixes or not normalized:
            return True
        return any(
            normalized == prefix or normalized.startswith(prefix + "/")
            for prefix in self.path_prefixes
        )

    def operation_name(self, operation: RepositoryOperation) -> str:
        if not isinstance(operation, RepositoryOperation):
            raise TypeError("operation must be a RepositoryOperation")
        return f"repo.{operation.value}"


@dataclass(frozen=True, slots=True)
class RepositoryRequest:
    operation: RepositoryOperation
    repository: str
    ref: str
    path: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.operation, RepositoryOperation):
            raise TypeError("operation must be a RepositoryOperation")
        if not isinstance(self.repository, str) or not self.repository.strip():
            raise ValueError("repository must not be empty")
        if not isinstance(self.ref, str) or not self.ref.strip():
            raise ValueError("ref must not be empty")
        object.__setattr__(self, "path", RepositoryScope._validate_relative_path(self.path))


@runtime_checkable
class RepositoryProviderAdapter(Protocol):
    @property
    def descriptor(self) -> AdapterDescriptor: ...

    @property
    def scope(self) -> RepositoryScope: ...

    def invoke(
        self,
        request: RepositoryRequest,
        payload: Mapping[str, Any],
        context: InvocationContext,
    ) -> AdapterResult: ...

    def shutdown(self) -> None: ...
