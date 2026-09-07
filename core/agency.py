"""Bounded Director -> Orchestrator -> Compliance agency composition.

This module is deliberately side-effect free. It may plan, validate and schedule
work, but it does not execute device/network/filesystem/account effects. Any real
execution must continue through Selma's existing Gate 1 control plane.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from hashlib import sha256
import json
from time import time
from typing import Any, Iterable, Mapping

from .protocols import Capability, RiskClass

AGENCY_CONTRACT_VERSION = "1.0.0"


class ComplianceOutcome(StrEnum):
    ALLOW = "ALLOW"
    ALLOW_WITH_LIMITS = "ALLOW_WITH_LIMITS"
    REQUIRE_OWNER_APPROVAL = "REQUIRE_OWNER_APPROVAL"
    DENY = "DENY"
    DEGRADED = "DEGRADED"


class TaskState(StrEnum):
    PROPOSED = "PROPOSED"
    PLANNED = "PLANNED"
    COMPLIANCE_CHECK = "COMPLIANCE_CHECK"
    APPROVED = "APPROVED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    COMPLETE = "COMPLETE"
    AWAITING_OWNER = "AWAITING_OWNER"
    BLOCKED = "BLOCKED"
    DEGRADED = "DEGRADED"
    CANCELLED = "CANCELLED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class AgencyDescriptor:
    agent_id: str
    purpose: str
    accepted_task_types: tuple[str, ...]
    required_capabilities: tuple[Capability, ...] = ()
    allowed_side_effects: tuple[str, ...] = ()
    risk_class: RiskClass = RiskClass.READ
    concurrency_ceiling: int = 1
    time_budget_seconds: int = 300
    input_schema_version: str = AGENCY_CONTRACT_VERSION
    output_schema_version: str = AGENCY_CONTRACT_VERSION
    evidence_requirements: tuple[str, ...] = ()
    rollback_strategy: str = "cancel-only"
    human_gate_requirements: tuple[str, ...] = ()
    platform_support: tuple[str, ...] = ("local",)
    degraded_behavior: str = "fail-closed"

    def __post_init__(self) -> None:
        if not self.agent_id.strip() or not self.purpose.strip():
            raise ValueError("agent_id and purpose are required")
        if self.concurrency_ceiling < 1 or self.time_budget_seconds < 1:
            raise ValueError("budgets must be positive")
        if not self.accepted_task_types:
            raise ValueError("accepted_task_types must not be empty")


@dataclass(frozen=True, slots=True)
class TaskEnvelope:
    task_id: str
    parent_plan_id: str
    initiating_request_ref: str
    selected_agent_id: str
    capability: Capability
    operation: str
    target: str
    scope_constraints: tuple[str, ...]
    risk_class: RiskClass
    approval_ref: str | None = None
    issued_at: int = field(default_factory=lambda: int(time()))
    ttl_seconds: int = 300
    max_attempts: int = 1
    network_policy: str = "offline"
    data_handling_policy: str = "minimum-necessary"
    rollback_metadata: str = "cancel-only"
    expected_evidence: tuple[str, ...] = ()
    audit_chain_ref: str | None = None
    nonce: str = ""
    envelope_hash: str = ""

    def __post_init__(self) -> None:
        for value, name in (
            (self.task_id, "task_id"),
            (self.parent_plan_id, "parent_plan_id"),
            (self.initiating_request_ref, "initiating_request_ref"),
            (self.selected_agent_id, "selected_agent_id"),
            (self.operation, "operation"),
            (self.target, "target"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if self.ttl_seconds < 1 or self.max_attempts < 1:
            raise ValueError("ttl_seconds and max_attempts must be positive")

    def canonical_payload(self) -> Mapping[str, Any]:
        return {
            "task_id": self.task_id,
            "parent_plan_id": self.parent_plan_id,
            "initiating_request_ref": self.initiating_request_ref,
            "selected_agent_id": self.selected_agent_id,
            "capability": self.capability.value,
            "operation": self.operation,
            "target": self.target,
            "scope_constraints": list(self.scope_constraints),
            "risk_class": self.risk_class.value,
            "approval_ref": self.approval_ref,
            "issued_at": self.issued_at,
            "ttl_seconds": self.ttl_seconds,
            "max_attempts": self.max_attempts,
            "network_policy": self.network_policy,
            "data_handling_policy": self.data_handling_policy,
            "rollback_metadata": self.rollback_metadata,
            "expected_evidence": list(self.expected_evidence),
            "audit_chain_ref": self.audit_chain_ref,
            "nonce": self.nonce,
        }

    def digest(self) -> str:
        raw = json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":"))
        return sha256(raw.encode("utf-8")).hexdigest()

    def bound(self) -> "TaskEnvelope":
        return replace(self, envelope_hash=self.digest())

    def verify(self, *, now: int | None = None) -> bool:
        current = int(time()) if now is None else now
        return bool(self.envelope_hash) and self.envelope_hash == self.digest() and current < self.issued_at + self.ttl_seconds


@dataclass(frozen=True, slots=True)
class Plan:
    plan_id: str
    objective: str
    tasks: tuple[TaskEnvelope, ...]
    created_from_request_ref: str

    def __post_init__(self) -> None:
        if not self.plan_id.strip() or not self.objective.strip() or not self.created_from_request_ref.strip():
            raise ValueError("plan identity, objective and request reference are required")
        if not self.tasks:
            raise ValueError("plan requires at least one task")
        if any(task.parent_plan_id != self.plan_id for task in self.tasks):
            raise ValueError("all tasks must belong to this plan")


@dataclass(frozen=True, slots=True)
class ComplianceDecision:
    outcome: ComplianceOutcome
    reason: str
    limits: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExecutionEvidence:
    task_id: str
    kind: str
    reference: str
    verified: bool


@dataclass(frozen=True, slots=True)
class AgencyEvent:
    sequence: int
    plan_id: str
    task_id: str | None
    state: TaskState
    message: str


class Director:
    """Planning-only strategic layer. It never invokes capability adapters."""

    def __init__(self, descriptor: AgencyDescriptor) -> None:
        self.descriptor = descriptor

    def compose_plan(
        self,
        *,
        plan_id: str,
        objective: str,
        request_ref: str,
        tasks: Iterable[TaskEnvelope],
    ) -> Plan:
        bounded = tuple(task.bound() if not task.envelope_hash else task for task in tasks)
        return Plan(plan_id, objective, bounded, request_ref)


class ComplianceController:
    """Non-bypassable, non-authority-expanding policy evaluator."""

    def __init__(self, *, network_enabled: bool = False, paused: bool = False) -> None:
        self.network_enabled = network_enabled
        self.paused = paused

    def evaluate(self, envelope: TaskEnvelope, descriptor: AgencyDescriptor) -> ComplianceDecision:
        if self.paused:
            return ComplianceDecision(ComplianceOutcome.DENY, "agency is paused")
        if not envelope.verify():
            return ComplianceDecision(ComplianceOutcome.DENY, "stale or invalid task envelope")
        if envelope.selected_agent_id != descriptor.agent_id:
            return ComplianceDecision(ComplianceOutcome.DENY, "agent binding mismatch")
        if envelope.capability not in descriptor.required_capabilities:
            return ComplianceDecision(ComplianceOutcome.DENY, "undeclared capability")
        if envelope.operation not in descriptor.accepted_task_types:
            return ComplianceDecision(ComplianceOutcome.DENY, "undeclared operation")
        if envelope.network_policy != "offline" and not self.network_enabled:
            return ComplianceDecision(ComplianceOutcome.DEGRADED, "network unavailable by policy")
        if envelope.risk_class is RiskClass.APPROVED_WRITE and not envelope.approval_ref:
            return ComplianceDecision(
                ComplianceOutcome.REQUIRE_OWNER_APPROVAL,
                "approved-write task requires narrow owner approval",
            )
        if descriptor.concurrency_ceiling == 1:
            return ComplianceDecision(ComplianceOutcome.ALLOW_WITH_LIMITS, "single-task concurrency", {"max_concurrency": 1})
        return ComplianceDecision(ComplianceOutcome.ALLOW, "policy checks passed")


class Orchestrator:
    """Deterministic scheduler that produces auditable state, not side effects."""

    def __init__(self, descriptor: AgencyDescriptor, compliance: ComplianceController) -> None:
        self.descriptor = descriptor
        self.compliance = compliance
        self._seen_hashes: set[str] = set()
        self._events: list[AgencyEvent] = []
        self._sequence = 0
        self._kill_switch = False

    @property
    def events(self) -> tuple[AgencyEvent, ...]:
        return tuple(self._events)

    def _emit(self, plan_id: str, task_id: str | None, state: TaskState, message: str) -> None:
        self._sequence += 1
        self._events.append(AgencyEvent(self._sequence, plan_id, task_id, state, message))

    def kill(self, plan_id: str) -> None:
        self._kill_switch = True
        self._emit(plan_id, None, TaskState.CANCELLED, "kill switch engaged")

    def schedule(self, plan: Plan) -> tuple[ComplianceDecision, ...]:
        decisions: list[ComplianceDecision] = []
        self._emit(plan.plan_id, None, TaskState.PLANNED, "plan accepted for compliance evaluation")
        for task in plan.tasks:
            if self._kill_switch:
                decision = ComplianceDecision(ComplianceOutcome.DENY, "kill switch engaged")
                decisions.append(decision)
                self._emit(plan.plan_id, task.task_id, TaskState.CANCELLED, decision.reason)
                continue
            self._emit(plan.plan_id, task.task_id, TaskState.COMPLIANCE_CHECK, "evaluating task")
            if task.envelope_hash in self._seen_hashes:
                decision = ComplianceDecision(ComplianceOutcome.DENY, "replay rejected")
            else:
                decision = self.compliance.evaluate(task, self.descriptor)
                self._seen_hashes.add(task.envelope_hash)
            decisions.append(decision)
            if decision.outcome in (ComplianceOutcome.ALLOW, ComplianceOutcome.ALLOW_WITH_LIMITS):
                self._emit(plan.plan_id, task.task_id, TaskState.QUEUED, decision.reason)
            elif decision.outcome is ComplianceOutcome.REQUIRE_OWNER_APPROVAL:
                self._emit(plan.plan_id, task.task_id, TaskState.AWAITING_OWNER, decision.reason)
            elif decision.outcome is ComplianceOutcome.DEGRADED:
                self._emit(plan.plan_id, task.task_id, TaskState.DEGRADED, decision.reason)
            else:
                self._emit(plan.plan_id, task.task_id, TaskState.BLOCKED, decision.reason)
        return tuple(decisions)

    def verify_completion(self, task: TaskEnvelope, evidence: Iterable[ExecutionEvidence]) -> bool:
        verified_kinds = {item.kind for item in evidence if item.task_id == task.task_id and item.verified}
        return set(task.expected_evidence).issubset(verified_kinds)
