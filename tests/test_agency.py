import unittest
from dataclasses import replace
from time import time

from core.agency import (
    AgencyDescriptor,
    ComplianceController,
    ComplianceOutcome,
    Director,
    ExecutionEvidence,
    Orchestrator,
    TaskEnvelope,
    TaskState,
)
from core.protocols import Capability, RiskClass


class AgencyCompositionTests(unittest.TestCase):
    def setUp(self):
        self.descriptor = AgencyDescriptor(
            agent_id="build-orchestrator",
            purpose="schedule bounded build tasks",
            accepted_task_types=("compile", "publish"),
            required_capabilities=(Capability.PROCESS, Capability.PRESENTATION),
            risk_class=RiskClass.APPROVED_WRITE,
            concurrency_ceiling=1,
            evidence_requirements=("test-output",),
        )
        self.director = Director(
            AgencyDescriptor(
                agent_id="director",
                purpose="plan work without executing effects",
                accepted_task_types=("plan",),
            )
        )

    def envelope(self, **overrides):
        base = TaskEnvelope(
            task_id="task-1",
            parent_plan_id="plan-1",
            initiating_request_ref="user-request-1",
            selected_agent_id="build-orchestrator",
            capability=Capability.PROCESS,
            operation="compile",
            target="local-fixture",
            scope_constraints=("local-only",),
            risk_class=RiskClass.APPROVED_WRITE,
            approval_ref="approval-1",
            nonce="nonce-1",
            expected_evidence=("test-output",),
        )
        return replace(base, **overrides).bound()

    def plan(self, task=None):
        return self.director.compose_plan(
            plan_id="plan-1",
            objective="verify bounded orchestration",
            request_ref="user-request-1",
            tasks=(task or self.envelope(),),
        )

    def test_director_is_planning_only(self):
        self.assertFalse(hasattr(self.director, "invoke"))
        self.assertFalse(hasattr(self.director, "execute"))
        self.assertEqual(self.plan().tasks[0].operation, "compile")

    def test_narrow_approval_required_for_approved_write(self):
        task = self.envelope(approval_ref=None)
        decision = ComplianceController().evaluate(task, self.descriptor)
        self.assertEqual(decision.outcome, ComplianceOutcome.REQUIRE_OWNER_APPROVAL)

    def test_compliance_denies_undeclared_capability(self):
        task = self.envelope(capability=Capability.NETWORK)
        decision = ComplianceController(network_enabled=True).evaluate(task, self.descriptor)
        self.assertEqual(decision.outcome, ComplianceOutcome.DENY)

    def test_agent_binding_mismatch_fails_closed(self):
        task = self.envelope(selected_agent_id="other-agent")
        decision = ComplianceController().evaluate(task, self.descriptor)
        self.assertEqual(decision.outcome, ComplianceOutcome.DENY)

    def test_stale_envelope_is_rejected(self):
        task = self.envelope(issued_at=int(time()) - 100, ttl_seconds=1)
        decision = ComplianceController().evaluate(task, self.descriptor)
        self.assertEqual(decision.outcome, ComplianceOutcome.DENY)

    def test_tampered_envelope_is_rejected(self):
        task = self.envelope()
        tampered = replace(task, target="broadened-target")
        decision = ComplianceController().evaluate(tampered, self.descriptor)
        self.assertEqual(decision.outcome, ComplianceOutcome.DENY)

    def test_replay_is_rejected(self):
        orchestrator = Orchestrator(self.descriptor, ComplianceController())
        plan = self.plan()
        first = orchestrator.schedule(plan)
        second = orchestrator.schedule(plan)
        self.assertIn(first[0].outcome, (ComplianceOutcome.ALLOW, ComplianceOutcome.ALLOW_WITH_LIMITS))
        self.assertEqual(second[0].outcome, ComplianceOutcome.DENY)
        self.assertEqual(second[0].reason, "replay rejected")

    def test_network_policy_degrades_when_network_disabled(self):
        task = self.envelope(network_policy="authorized-network")
        decision = ComplianceController(network_enabled=False).evaluate(task, self.descriptor)
        self.assertEqual(decision.outcome, ComplianceOutcome.DEGRADED)

    def test_kill_switch_cancels_subordinate_work(self):
        orchestrator = Orchestrator(self.descriptor, ComplianceController())
        orchestrator.kill("plan-1")
        decisions = orchestrator.schedule(self.plan())
        self.assertEqual(decisions[0].outcome, ComplianceOutcome.DENY)
        self.assertTrue(any(event.state is TaskState.CANCELLED for event in orchestrator.events))

    def test_completion_requires_verified_evidence(self):
        orchestrator = Orchestrator(self.descriptor, ComplianceController())
        task = self.envelope()
        self.assertFalse(orchestrator.verify_completion(task, ()))
        evidence = ExecutionEvidence("task-1", "test-output", "local:test-1", True)
        self.assertTrue(orchestrator.verify_completion(task, (evidence,)))

    def test_unverified_evidence_does_not_complete(self):
        orchestrator = Orchestrator(self.descriptor, ComplianceController())
        task = self.envelope()
        evidence = ExecutionEvidence("task-1", "test-output", "model-claim", False)
        self.assertFalse(orchestrator.verify_completion(task, (evidence,)))


if __name__ == "__main__":
    unittest.main()
