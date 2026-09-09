import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fdt_gate.canonical import fmt_time
from fdt_gate.crypto import Keyring, Signer
from fdt_gate.frameworks import equivalent_security_view, stack_a_to_envelope, stack_b_to_envelope
from fdt_gate.models import Decision
from fdt_gate.policy import compile_policy
from fdt_gate.security import WingDingynouse, issue_grant
from fdt_gate.store import SecurityStore


class AcceptanceTests(unittest.TestCase):
    def test_two_frameworks_same_security_semantics_and_decision(self):
        a = stack_a_to_envelope({"tool": "fs.read", "arguments": {"resource": "workspace/x.txt", "method": "READ", "payload": {}}}, principal="agent")
        b = stack_b_to_envelope({"action": {"effect": "fs.read", "target": "workspace/x.txt", "verb": "READ", "input": {}}}, principal="agent")
        self.assertTrue(equivalent_security_view(a, b))
        self.assertEqual(a.to_dict(), b.to_dict())
        self.assertEqual(a.action_hash, b.action_hash)

        source = """fdt-policy 0.7
policy acceptance
version 0.7.0
default DENY
rule read effect=fs.read resource=workspace/** capability=read decision=ALLOW methods=READ max_payload_bytes=1024 max_calls_per_minute=100
"""
        genesis = Signer.generate(); runtime = Signer.generate(); keys = Keyring(); keys.add_signer(genesis); keys.add_signer(runtime)
        now = datetime(2026, 9, 9, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as td:
            store = SecurityStore(Path(td) / "state.db")
            store.put_grant(issue_grant(
                signer=genesis, issuer="genesis", subject="agent", capability="read", resource_prefix="workspace/",
                effects=("fs.read",), methods=("READ",), not_before=fmt_time(now - timedelta(minutes=1)),
                expires_at=fmt_time(now + timedelta(hours=1)), issued_at=fmt_time(now),
            ))
            engine = WingDingynouse(policy=compile_policy(source, genesis), trusted_keys=keys,
                                    genesis_key_ids={genesis.key_id}, runtime_signer=runtime, store=store, clock=lambda: now)
            ra = engine.authorize(a, record_budget=False)
            rb = engine.authorize(b, record_budget=False)
            self.assertEqual(ra.decision, Decision.ALLOW)
            self.assertEqual(rb.decision, Decision.ALLOW)
            self.assertEqual(ra.reason_code, rb.reason_code)
            self.assertEqual(ra.policy_build_id, rb.policy_build_id)


if __name__ == "__main__": unittest.main()
