"""Side-effect-free Sol Blue/Red resource and capability contracts.

This is a policy *preflight*, not a credential broker or executor. Actual
mutations must also pass the existing SelmaOS authority/audit control plane.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from types import MappingProxyType
from typing import Iterable, Mapping
from urllib.parse import urlsplit


class SolMode(StrEnum):
    BLUE = "blue"
    RED = "red"


class ResourceKind(StrEnum):
    DEVICE = "device"
    NETWORK = "network"
    SERVER = "server"
    STORAGE = "storage"
    REPOSITORY = "repository"
    MIRROR = "mirror"
    CI = "ci"
    ARTIFACT = "artifact"
    DATABASE = "database"
    MESSAGING = "messaging"
    OBSERVABILITY = "observability"


class TrustState(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    QUARANTINED = "quarantined"


class Operation(StrEnum):
    READ = "read"
    VERIFY = "verify"
    PLAN = "plan"
    BRANCH_WRITE = "branch-write"
    SYNC = "sync"
    MERGE = "merge"
    RELEASE = "release"
    DELETE = "delete"
    CHANGE_SECURITY = "change-security"
    ROTATE_CREDENTIALS = "rotate-credentials"
    EXPOSE_PUBLIC = "expose-public"
    PURCHASE = "purchase"
    BYPASS_PERMISSIONS = "bypass-permissions"


BLUE_OPERATIONS = frozenset({Operation.READ, Operation.VERIFY, Operation.PLAN})
HIGH_IMPACT_OPERATIONS = frozenset({
    Operation.MERGE, Operation.RELEASE, Operation.DELETE,
    Operation.CHANGE_SECURITY, Operation.ROTATE_CREDENTIALS,
    Operation.EXPOSE_PUBLIC, Operation.PURCHASE, Operation.BYPASS_PERMISSIONS,
})
# Bypassing a provider/OS permission is never authorized by this preflight.
PROHIBITED_OPERATIONS = frozenset({Operation.BYPASS_PERMISSIONS})


class DecisionState(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"
    APPROVAL_REQUIRED = "approval_required"


class TruthState(StrEnum):
    REAL = "real"
    PREVIEW = "preview"
    INFERRED = "inferred"
    UNVERIFIED = "unverified"
    BLOCKED = "blocked"


def _nonempty(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")


def _aware(value: datetime, name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _validate_scope(scope: str, *, pattern: bool = False) -> None:
    if not isinstance(scope, str):
        raise TypeError("scope must be a string")
    if not scope or scope.startswith("/") or ".." in scope.split("/") or "\\" in scope:
        raise ValueError("scope must be a relative, nonempty path without traversal")
    if any(ord(ch) < 32 for ch in scope):
        raise ValueError("scope must not contain control characters")
    if "?" in scope or "[" in scope or "]" in scope:
        raise ValueError("ambiguous scope wildcard")
    if pattern:
        if scope.count("*") > 1 or ("*" in scope and not scope.endswith("/*")):
            raise ValueError("only a terminal /* prefix wildcard is supported")
    elif "*" in scope:
        raise ValueError("request scope must be concrete")


@dataclass(frozen=True, slots=True)
class Resource:
    resource_id: str
    kind: ResourceKind
    provider: str
    endpoint: str
    owner: str
    authorized: bool = False
    trust: TrustState = TrustState.UNVERIFIED
    operations: frozenset[Operation] = field(default_factory=frozenset)
    credential_ref: str | None = None
    mirror_of: str | None = None
    provenance: str | None = None

    def __post_init__(self) -> None:
        for name in ("resource_id", "provider", "endpoint", "owner"):
            _nonempty(getattr(self, name), name)
        if any(ch in self.resource_id for ch in "*?[]"):
            raise ValueError("resource_id must identify one concrete resource")
        if not isinstance(self.kind, ResourceKind) or not isinstance(self.trust, TrustState):
            raise TypeError("kind and trust must use their declared enums")
        if type(self.authorized) is not bool:
            raise TypeError("authorized must be boolean")
        if not isinstance(self.operations, frozenset) or not all(
            isinstance(op, Operation) for op in self.operations
        ):
            raise TypeError("operations must be frozenset[Operation]")
        if self.credential_ref is not None:
            _nonempty(self.credential_ref, "credential_ref")
            if not self.credential_ref.startswith("secret-ref:"):
                raise ValueError("credential_ref must be a secret broker reference")
        parts = urlsplit(self.endpoint)
        if parts.username is not None or parts.password is not None:
            raise ValueError("endpoint must not embed credentials")
        if self.mirror_of is not None:
            _nonempty(self.mirror_of, "mirror_of")
            if self.mirror_of == self.resource_id:
                raise ValueError("resource cannot mirror itself")


class ResourceRegistry:
    """Immutable snapshot; no network discovery or credential access."""

    def __init__(self, resources: Iterable[Resource] = ()) -> None:
        index: dict[str, Resource] = {}
        for resource in resources:
            if not isinstance(resource, Resource):
                raise TypeError("registry entries must be Resource objects")
            if resource.resource_id in index:
                raise ValueError("duplicate resource_id")
            index[resource.resource_id] = resource
        for resource in index.values():
            if resource.mirror_of is not None and resource.mirror_of not in index:
                raise ValueError("mirror references unknown canonical resource")
        self._resources: Mapping[str, Resource] = MappingProxyType(index)

    def get(self, resource_id: str) -> Resource | None:
        return self._resources.get(resource_id)

    def authorized_resources(self) -> tuple[Resource, ...]:
        return tuple(sorted((r for r in self._resources.values() if r.authorized),
                            key=lambda r: r.resource_id))

    def mirrors_of(self, resource_id: str) -> tuple[Resource, ...]:
        return tuple(sorted((r for r in self._resources.values() if r.mirror_of == resource_id),
                            key=lambda r: r.resource_id))


@dataclass(frozen=True, slots=True)
class CapabilityGrant:
    """An externally issued claim, never proof of authentication by itself."""

    issuer: str
    principal: str
    resource_id: str
    operations: frozenset[Operation]
    scopes: tuple[str, ...]
    expires_at: datetime

    def __post_init__(self) -> None:
        for name in ("issuer", "principal", "resource_id"):
            _nonempty(getattr(self, name), name)
        if self.issuer == self.principal:
            raise ValueError("self-issued grants are forbidden")
        if any(ch in self.resource_id for ch in "*?[]"):
            raise ValueError("grant target must be concrete")
        if not isinstance(self.operations, frozenset) or not self.operations or not all(
            isinstance(op, Operation) for op in self.operations
        ):
            raise ValueError("operations must be a nonempty frozenset[Operation]")
        if not isinstance(self.scopes, tuple):
            raise TypeError("scopes must be a tuple")
        for scope in self.scopes:
            _validate_scope(scope, pattern=True)
        _aware(self.expires_at, "expires_at")

    def covers(self, scope: str) -> bool:
        if not self.scopes:
            return False
        for pattern in self.scopes:
            if pattern.endswith("/*"):
                prefix = pattern[:-1]
                if scope.startswith(prefix) and len(scope) > len(prefix):
                    return True
            elif scope == pattern:
                return True
        return False


@dataclass(frozen=True, slots=True)
class ActionRequest:
    principal: str
    resource_id: str
    operation: Operation
    scope: str

    def __post_init__(self) -> None:
        _nonempty(self.principal, "principal")
        _nonempty(self.resource_id, "resource_id")
        if not isinstance(self.operation, Operation):
            raise TypeError("operation must be Operation")
        _validate_scope(self.scope)


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    state: DecisionState
    reason: str
    truth: TruthState = TruthState.PREVIEW

    @property
    def allowed(self) -> bool:
        return self.state is DecisionState.ALLOWED


def evaluate_action(
    registry: ResourceRegistry,
    mode: SolMode,
    request: ActionRequest,
    *,
    grant: CapabilityGrant | None = None,
    human_approved_now: bool = False,
    now: datetime | None = None,
) -> PolicyDecision:
    """Fail-closed local policy preflight; never executes or issues grants.

    A returned ALLOWED state is only a PREVIEW of policy eligibility. The
    existing Selma control plane must authenticate issuer, validate signatures,
    check revocation, obtain required approvals, and audit before execution.
    """
    if not isinstance(registry, ResourceRegistry) or not isinstance(mode, SolMode):
        raise TypeError("registry and mode must use declared types")
    if not isinstance(request, ActionRequest):
        raise TypeError("request must be ActionRequest")
    if type(human_approved_now) is not bool:
        raise TypeError("human_approved_now must be boolean")
    now = datetime.now(timezone.utc) if now is None else now
    _aware(now, "now")
    resource = registry.get(request.resource_id)
    if resource is None or not resource.authorized or resource.trust is not TrustState.VERIFIED:
        return PolicyDecision(DecisionState.DENIED, "resource absent, unauthorized or unverified")
    if request.operation not in resource.operations:
        return PolicyDecision(DecisionState.DENIED, "operation unsupported by resource")
    if request.operation in PROHIBITED_OPERATIONS:
        return PolicyDecision(DecisionState.DENIED, "permission bypass is not permitted")
    if mode is SolMode.BLUE:
        if request.operation not in BLUE_OPERATIONS:
            return PolicyDecision(DecisionState.DENIED, "Sol Blue is read-only")
        return PolicyDecision(DecisionState.ALLOWED, "read-only preflight eligible")
    if grant is None:
        return PolicyDecision(DecisionState.DENIED, "Sol Red requires an external grant")
    if (grant.principal != request.principal or grant.resource_id != request.resource_id
            or request.operation not in grant.operations or now >= grant.expires_at
            or not grant.covers(request.scope)):
        return PolicyDecision(DecisionState.DENIED, "grant mismatch, scope mismatch or expired")
    if request.operation in HIGH_IMPACT_OPERATIONS and not human_approved_now:
        return PolicyDecision(DecisionState.APPROVAL_REQUIRED, "fresh human approval required")
    return PolicyDecision(DecisionState.ALLOWED, "grant preflight eligible; executor must revalidate")
