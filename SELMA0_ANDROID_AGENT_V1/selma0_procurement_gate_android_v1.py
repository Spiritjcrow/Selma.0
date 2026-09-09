from __future__ import annotations

import hashlib
import hmac
import re
from collections import OrderedDict, deque
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Tuple

_SHA256_RE_V1 = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(frozen=True)
class Selma0ProcurementDecisionAndroidV1:
    allowed: bool
    reason: str
    package: str
    version: str
    digest: str = ""


@dataclass(frozen=True)
class Selma0VerifiedArtifactAndroidV1:
    package: str
    version: str
    source: str
    digest: str
    capabilities: Tuple[str, ...]
    network_policy: str
    artifact: bytes


class Selma0ProcurementGateAndroidV1:
    """Fail-closed procurement gate for Hyperlogic Source Emporium artifacts.

    A package must pass source provenance, exact pin, SHA-256 integrity and
    capability policy before it can enter the verified cache. Runtime authority
    remains separate and must still pass Selma's permission engine.
    """

    DEFAULT_CAPABILITIES_V1 = frozenset(
        {"read", "sensitive_read", "write", "external_effect"}
    )

    def __init__(
        self,
        trusted_sources: Iterable[str],
        allowed_capabilities: Optional[Iterable[str]] = None,
        cache_capacity: int = 8,
        rollback_depth: int = 3,
        audit_log: Any = None,
    ):
        self.trusted_sources = frozenset(
            str(source).strip() for source in trusted_sources if str(source).strip()
        )
        self.allowed_capabilities = frozenset(
            str(item).strip()
            for item in (
                allowed_capabilities
                if allowed_capabilities is not None
                else self.DEFAULT_CAPABILITIES_V1
            )
            if str(item).strip()
        )
        self.cache_capacity = max(1, int(cache_capacity))
        self.rollback_depth = max(1, int(rollback_depth))
        self.audit_log = audit_log

        self._cache: "OrderedDict[str, Selma0VerifiedArtifactAndroidV1]" = OrderedDict()
        self._active: Dict[str, str] = {}
        self._history: Dict[str, deque[str]] = {}

    @staticmethod
    def _key_v1(package: str, version: str) -> str:
        return f"{package}@{version}"

    def _audit_v1(self, event_type: str, details: Dict[str, Any]) -> None:
        if self.audit_log is None:
            return
        append = getattr(self.audit_log, "append", None)
        if callable(append):
            append(event_type, details)

    def _decision_v1(
        self,
        allowed: bool,
        reason: str,
        package: str,
        version: str,
        digest: str = "",
    ) -> Selma0ProcurementDecisionAndroidV1:
        decision = Selma0ProcurementDecisionAndroidV1(
            bool(allowed), str(reason), str(package), str(version), str(digest)
        )
        self._audit_v1(
            "procurement_decision_v1",
            {
                "allowed": decision.allowed,
                "reason": decision.reason,
                "package": decision.package,
                "version": decision.version,
                "digest": decision.digest,
            },
        )
        return decision

    def procure(
        self,
        *,
        package: str,
        version: str,
        pinned_version: str,
        source: str,
        expected_sha256: str,
        artifact: bytes,
        capabilities: Iterable[str] = (),
        network_policy: str = "deny",
    ) -> Selma0ProcurementDecisionAndroidV1:
        package = str(package).strip()
        version = str(version).strip()
        pinned_version = str(pinned_version).strip()
        source = str(source).strip()
        expected_sha256 = str(expected_sha256).strip().lower()
        network_policy = str(network_policy).strip().lower() or "deny"

        if not package or not version:
            return self._decision_v1(
                False, "package and version are required", package, version
            )
        if source not in self.trusted_sources:
            return self._decision_v1(
                False, "source provenance is not trusted", package, version
            )
        if version != pinned_version:
            return self._decision_v1(
                False, "resolved version does not match exact pin", package, version
            )
        if not isinstance(artifact, (bytes, bytearray, memoryview)):
            return self._decision_v1(False, "artifact must be bytes", package, version)
        if not _SHA256_RE_V1.fullmatch(expected_sha256):
            return self._decision_v1(
                False, "expected SHA-256 is invalid", package, version
            )

        artifact_bytes = bytes(artifact)
        actual_sha256 = hashlib.sha256(artifact_bytes).hexdigest()
        if not hmac.compare_digest(actual_sha256, expected_sha256):
            return self._decision_v1(
                False, "artifact integrity check failed", package, version, actual_sha256
            )

        declared = tuple(
            sorted(
                {
                    str(item).strip()
                    for item in capabilities
                    if str(item).strip()
                }
            )
        )
        outside_policy = sorted(set(declared) - set(self.allowed_capabilities))
        if outside_policy:
            return self._decision_v1(
                False,
                "artifact requests capabilities outside procurement policy: "
                + ", ".join(outside_policy),
                package,
                version,
                actual_sha256,
            )
        if network_policy not in {"deny", "allow"}:
            return self._decision_v1(
                False,
                "network policy must be deny or allow",
                package,
                version,
                actual_sha256,
            )

        record = Selma0VerifiedArtifactAndroidV1(
            package=package,
            version=version,
            source=source,
            digest=actual_sha256,
            capabilities=declared,
            network_policy=network_policy,
            artifact=artifact_bytes,
        )
        key = self._key_v1(package, version)
        self._cache[key] = record
        self._cache.move_to_end(key)
        self._evict_v1()
        self._audit_v1(
            "procurement_cached_v1",
            {
                "package": package,
                "version": version,
                "digest": actual_sha256,
                "capabilities": list(declared),
                "network_policy": network_policy,
            },
        )
        return self._decision_v1(
            True, "artifact verified and cached", package, version, actual_sha256
        )

    def _evict_v1(self) -> None:
        while len(self._cache) > self.cache_capacity:
            active_keys = set(self._active.values())
            candidate = None
            for key in self._cache:
                if key not in active_keys:
                    candidate = key
                    break
            if candidate is None:
                raise RuntimeError("verified cache is full of active artifacts")
            removed = self._cache.pop(candidate)
            self._audit_v1(
                "procurement_cache_evicted_v1",
                {
                    "package": removed.package,
                    "version": removed.version,
                    "digest": removed.digest,
                },
            )

    def activate(self, package: str, version: str) -> Selma0VerifiedArtifactAndroidV1:
        package = str(package).strip()
        version = str(version).strip()
        key = self._key_v1(package, version)
        record = self._cache.get(key)
        if record is None:
            raise KeyError(f"artifact is not verified in cache: {key}")

        previous = self._active.get(package)
        if previous and previous != key:
            history = self._history.setdefault(
                package, deque(maxlen=self.rollback_depth)
            )
            history.append(previous)

        self._active[package] = key
        self._cache.move_to_end(key)
        self._audit_v1(
            "procurement_activated_v1",
            {
                "package": package,
                "version": version,
                "digest": record.digest,
            },
        )
        return record

    def rollback(self, package: str) -> Selma0VerifiedArtifactAndroidV1:
        package = str(package).strip()
        history = self._history.get(package)
        if not history:
            raise LookupError(f"no rollback generation is available for: {package}")

        while history:
            key = history.pop()
            record = self._cache.get(key)
            if record is None:
                continue
            self._active[package] = key
            self._cache.move_to_end(key)
            self._audit_v1(
                "procurement_rollback_v1",
                {
                    "package": record.package,
                    "version": record.version,
                    "digest": record.digest,
                },
            )
            return record
        raise LookupError(f"rollback generations were evicted for: {package}")

    def authorize_runtime(
        self,
        package: str,
        capability: str,
        permission_engine: Any,
        *,
        approved: bool = False,
    ):
        package = str(package).strip()
        capability = str(capability).strip()
        active_key = self._active.get(package)
        if active_key is None:
            raise PermissionError(f"package is not active: {package}")
        record = self._cache.get(active_key)
        if record is None:
            raise PermissionError(
                f"active package is missing from verified cache: {package}"
            )
        if capability not in record.capabilities:
            raise PermissionError(
                f"capability was not declared during procurement: {capability}"
            )

        evaluate = getattr(permission_engine, "evaluate", None)
        if not callable(evaluate):
            raise TypeError("permission engine does not expose evaluate()")
        decision = evaluate(
            {"risk": capability, "enabled": True},
            approved=bool(approved),
        )
        self._audit_v1(
            "procurement_runtime_authorization_v1",
            {
                "package": package,
                "version": record.version,
                "capability": capability,
                "allowed": bool(getattr(decision, "allowed", False)),
                "approved": bool(approved),
            },
        )
        return decision

    def cached(self):
        return [
            {
                "package": item.package,
                "version": item.version,
                "source": item.source,
                "digest": item.digest,
                "capabilities": list(item.capabilities),
                "network_policy": item.network_policy,
                "active": self._active.get(item.package)
                == self._key_v1(item.package, item.version),
            }
            for item in self._cache.values()
        ]

    def status(self):
        return {
            "policy": "fail_closed",
            "trusted_sources": sorted(self.trusted_sources),
            "allowed_capabilities": sorted(self.allowed_capabilities),
            "cache_capacity": self.cache_capacity,
            "cache_size": len(self._cache),
            "rollback_depth": self.rollback_depth,
            "active": dict(self._active),
            "default_network_policy": "deny",
        }
