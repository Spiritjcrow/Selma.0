from __future__ import annotations

import unittest

from fdt_gate.models import ActionEnvelope, Decision, DecisionReceipt
from fdt_gate.selma_bridge import (
    SelmaBridgeError,
    SelmaControlPlaneBridge,
    SelmaIntegratedFDTGate,
    SelmaRoute,
)


def receipt_for(action: ActionEnvelope, decision: Decision = Decision.ALLOW) -> DecisionReceipt:
    return DecisionReceipt(
        decision=decision,
        reason_code="test",
        action_hash=action.action_hash,
        policy_build_id="fdtir:test",
        evaluated_at="2026-09-09T00:00:00Z",
        runtime_key_id="runtime:test",
        grant_id="grant:test",
        approval_id="approval:test",
        signature="sig:test",
    )


class FakeEngine:
    def __init__(self, receipt: DecisionReceipt):
        self.receipt = receipt
        self.calls = []

    def authorize(self, action, *, consume_approval, record_budget):
        self.calls.append((action, consume_approval, record_budget))
        return self.receipt


class SelmaBridgeTests(unittest.TestCase):
    def setUp(self):
        self.action = ActionEnvelope(
            actor="subject:agent-a",
            on_behalf_of="subject:owner",
            effect="fs.write",
            resource="workspace/docs/status.txt",
            method="WRITE",
            payload={"text": "ready"},
            provenance=("source:task-7", "policy:owner-approved"),
        )
        self.route = SelmaRoute(
            capability="storage",
            operation="write",
            tool_name="storage.write",
        )

    def test_bridge_rejects_non_allow_receipt(self):
        bridge = SelmaControlPlaneBridge(lambda _: {"status": "success"}, {"fs.write": self.route})
        with self.assertRaises(SelmaBridgeError):
            bridge.execute(self.action, receipt_for(self.action, Decision.DENY))

    def test_bridge_rejects_receipt_for_different_action(self):
        other = ActionEnvelope(
            actor=self.action.actor,
            effect=self.action.effect,
            resource="workspace/docs/other.txt",
            method=self.action.method,
            payload=self.action.payload,
        )
        bridge = SelmaControlPlaneBridge(lambda _: {"status": "success"}, {"fs.write": self.route})
        with self.assertRaises(SelmaBridgeError):
            bridge.execute(self.action, receipt_for(other))

    def test_bridge_requires_explicit_effect_route(self):
        bridge = SelmaControlPlaneBridge(lambda _: {"status": "success"}, {"http.request": self.route})
        with self.assertRaises(SelmaBridgeError):
            bridge.execute(self.action, receipt_for(self.action))

    def test_bridge_preserves_identity_scope_payload_hash_and_provenance(self):
        seen = []

        def dispatch(invocation):
            seen.append(invocation)
            return {"status": "success", "message": "canonical Selma control plane accepted"}

        bridge = SelmaControlPlaneBridge(dispatch, {"fs.write": self.route})
        result = bridge.execute(self.action, receipt_for(self.action))
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(seen), 1)
        invocation = seen[0]
        self.assertEqual(invocation.actor, self.action.actor)
        self.assertEqual(invocation.on_behalf_of, self.action.on_behalf_of)
        self.assertEqual(invocation.capability, "storage")
        self.assertEqual(invocation.operation, "write")
        self.assertEqual(invocation.tool_name, "storage.write")
        self.assertEqual(invocation.resource, self.action.resource)
        self.assertEqual(invocation.payload, self.action.payload)
        self.assertEqual(invocation.provenance, self.action.provenance)
        self.assertEqual(invocation.action_hash, self.action.action_hash)
        self.assertEqual(invocation.fdt_approval_id, "approval:test")

    def test_kill_switch_blocks_before_dispatch(self):
        calls = []
        bridge = SelmaControlPlaneBridge(
            lambda invocation: calls.append(invocation) or {"status": "success"},
            {"fs.write": self.route},
            kill_switch_active=lambda: True,
        )
        with self.assertRaises(SelmaBridgeError):
            bridge.execute(self.action, receipt_for(self.action))
        self.assertEqual(calls, [])

    def test_integrated_gate_treats_non_success_selma_result_as_not_executed(self):
        receipt = receipt_for(self.action)
        engine = FakeEngine(receipt)
        bridge = SelmaControlPlaneBridge(
            lambda _: {"status": "denied", "message": "Selma permission policy denied"},
            {"fs.write": self.route},
        )
        gate = SelmaIntegratedFDTGate(engine, bridge)
        result = gate.execute(self.action)
        self.assertFalse(result["executed"])
        self.assertEqual(result["selma_result"]["status"], "denied")
        self.assertEqual(engine.calls, [(self.action, True, True)])

    def test_integrated_gate_denial_never_reaches_dispatcher(self):
        calls = []
        denied = receipt_for(self.action, Decision.REQUIRE_APPROVAL)
        engine = FakeEngine(denied)
        bridge = SelmaControlPlaneBridge(
            lambda invocation: calls.append(invocation) or {"status": "success"},
            {"fs.write": self.route},
        )
        result = SelmaIntegratedFDTGate(engine, bridge).execute(self.action)
        self.assertFalse(result["executed"])
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
