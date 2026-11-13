from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

from .canonical import canonical_json, sha256_hex, stable_id


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    ESCALATE = "ESCALATE"


class Risk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class ActionEnvelope:
    actor: str
    effect: str
    resource: str
    method: str = "*"
    payload: dict[str, Any] = field(default_factory=dict)
    on_behalf_of: str | None = None
    provenance: tuple[str, ...] = ()
    version: str = "fdt.action.v1"

    def __post_init__(self) -> None:
        for name in ("actor", "effect", "resource", "method"):
            if not getattr(self, name) or not isinstance(getattr(self, name), str):
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.payload, dict):
            raise ValueError("payload must be an object")
        canonical_json(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["provenance"] = list(self.provenance)
        return d

    @property
    def action_hash(self) -> str:
        return "sha256:" + sha256_hex(canonical_json(self.to_dict()))

    @property
    def action_id(self) -> str:
        return stable_id("action", self.to_dict())

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ActionEnvelope":
        return cls(
            actor=d["actor"], effect=d["effect"], resource=d["resource"],
            method=d.get("method", "*"), payload=d.get("payload", {}),
            on_behalf_of=d.get("on_behalf_of"), provenance=tuple(d.get("provenance", [])),
            version=d.get("version", "fdt.action.v1"),
        )


@dataclass(frozen=True)
class CapabilityGrant:
    grant_id: str
    issuer: str
    issuer_key_id: str
    subject: str
    capability: str
    resource_prefix: str
    effects: tuple[str, ...]
    methods: tuple[str, ...]
    not_before: str
    expires_at: str
    issued_at: str
    parent_id: str | None = None
    signature: str = ""
    version: str = "fdt.capability.v1"

    def unsigned_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("signature", None)
        d["effects"] = list(self.effects)
        d["methods"] = list(self.methods)
        return d

    def to_dict(self) -> dict[str, Any]:
        d = self.unsigned_dict()
        d["signature"] = self.signature
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CapabilityGrant":
        return cls(**{**d, "effects": tuple(d["effects"]), "methods": tuple(d["methods"])})


@dataclass(frozen=True)
class Approval:
    approval_id: str
    action_hash: str
    approver: str
    signer_key_id: str
    issued_at: str
    expires_at: str
    signature: str = ""
    one_time: bool = True
    version: str = "fdt.approval.v1"

    def unsigned_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("signature", None)
        return d

    def to_dict(self) -> dict[str, Any]:
        d = self.unsigned_dict()
        d["signature"] = self.signature
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Approval":
        return cls(**d)


@dataclass(frozen=True)
class PolicyRule:
    rule_id: str
    effect: str
    resource: str
    capability: str
    decision: Decision
    risk: Risk = Risk.LOW
    methods: tuple[str, ...] = ("*",)
    max_payload_bytes: int = 65536
    max_calls_per_minute: int = 60

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["decision"] = self.decision.value
        d["risk"] = self.risk.value
        d["methods"] = list(self.methods)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PolicyRule":
        return cls(
            rule_id=d["rule_id"], effect=d["effect"], resource=d["resource"],
            capability=d["capability"], decision=Decision(d["decision"]),
            risk=Risk(d.get("risk", "LOW")), methods=tuple(d.get("methods", ["*"])),
            max_payload_bytes=int(d.get("max_payload_bytes", 65536)),
            max_calls_per_minute=int(d.get("max_calls_per_minute", 60)),
        )


@dataclass(frozen=True)
class PolicyBundle:
    policy_id: str
    policy_version: str
    default_decision: Decision
    rules: tuple[PolicyRule, ...]
    build_id: str
    source_hash: str
    signer_key_id: str
    signature: str
    schema_version: str = "fdt.policy.v1"

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "default_decision": self.default_decision.value,
            "rules": [r.to_dict() for r in self.rules],
            "build_id": self.build_id,
            "source_hash": self.source_hash,
            "signer_key_id": self.signer_key_id,
        }

    def to_dict(self) -> dict[str, Any]:
        d = self.unsigned_dict()
        d["signature"] = self.signature
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PolicyBundle":
        return cls(
            policy_id=d["policy_id"], policy_version=d["policy_version"],
            default_decision=Decision(d["default_decision"]),
            rules=tuple(PolicyRule.from_dict(x) for x in d["rules"]),
            build_id=d["build_id"], source_hash=d["source_hash"],
            signer_key_id=d["signer_key_id"], signature=d["signature"],
            schema_version=d.get("schema_version", "fdt.policy.v1"),
        )


@dataclass(frozen=True)
class DecisionReceipt:
    decision: Decision
    reason_code: str
    action_hash: str
    policy_build_id: str
    evaluated_at: str
    runtime_key_id: str
    rule_id: str | None = None
    grant_id: str | None = None
    approval_id: str | None = None
    state_hash: str | None = None
    signature: str = ""
    version: str = "fdt.receipt.v1"

    def unsigned_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("signature", None)
        d["decision"] = self.decision.value
        return d

    def to_dict(self) -> dict[str, Any]:
        d = self.unsigned_dict()
        d["signature"] = self.signature
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DecisionReceipt":
        return cls(**{**d, "decision": Decision(d["decision"])})
