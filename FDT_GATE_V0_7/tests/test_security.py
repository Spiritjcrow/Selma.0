import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fdt_gate.canonical import fmt_time
from fdt_gate.crypto import Keyring, Signer
from fdt_gate.models import ActionEnvelope, Decision
from fdt_gate.policy import compile_policy
from fdt_gate.security import WingDingynouse, issue_approval, issue_grant
from fdt_gate.store import SecurityStore

POLICY = """fdt-policy 0.7
policy tests
version 0.7.0
default DENY
rule r effect=fs.write resource=workspace/** capability=write decision=REQUIRE_APPROVAL risk=HIGH methods=WRITE max_payload_bytes=1024 max_calls_per_minute=10
"""


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.genesis = Signer.generate(); self.runtime = Signer.generate()
        self.keys = Keyring(); self.keys.add_signer(self.genesis); self.keys.add_signer(self.runtime)
        self.bundle = compile_policy(POLICY, self.genesis)
        self.now = datetime(2026, 9, 9, 0, 0, tzinfo=timezone.utc)
        self.store = SecurityStore(Path(self.tmp.name) / "state.db")
        self.grant = issue_grant(
            signer=self.genesis, issuer="genesis", subject="agent", capability="write",
            resource_prefix="workspace/", effects=("fs.write",), methods=("WRITE",),
            not_before=fmt_time(self.now - timedelta(minutes=1)), expires_at=fmt_time(self.now + timedelta(hours=1)),
            issued_at=fmt_time(self.now),
        )
        self.store.put_grant(self.grant)
        self.engine = WingDingynouse(
            policy=self.bundle, trusted_keys=self.keys, genesis_key_ids={self.genesis.key_id},
            runtime_signer=self.runtime, store=self.store, clock=lambda: self.now,
        )

    def tearDown(self): self.tmp.cleanup()

    def test_exact_action_approval_and_reuse_blocked(self):
        a = ActionEnvelope(actor="agent", effect="fs.write", resource="workspace/a.txt", method="WRITE", payload={"text": "a"})
        self.assertEqual(self.engine.authorize(a).decision, Decision.REQUIRE_APPROVAL)
        ap = issue_approval(signer=self.genesis, action_hash=a.action_hash, approver="genesis",
                            issued_at=fmt_time(self.now), expires_at=fmt_time(self.now + timedelta(minutes=5)))
        self.store.put_approval(ap)
        self.assertEqual(self.engine.authorize(a, consume_approval=True).decision, Decision.ALLOW)
        self.assertEqual(self.engine.authorize(a, consume_approval=True).decision, Decision.REQUIRE_APPROVAL)

    def test_approval_cannot_cross_action(self):
        a = ActionEnvelope(actor="agent", effect="fs.write", resource="workspace/a.txt", method="WRITE", payload={"text": "a"})
        b = ActionEnvelope(actor="agent", effect="fs.write", resource="workspace/b.txt", method="WRITE", payload={"text": "b"})
        ap = issue_approval(signer=self.genesis, action_hash=a.action_hash, approver="genesis",
                            issued_at=fmt_time(self.now), expires_at=fmt_time(self.now + timedelta(minutes=5)))
        self.store.put_approval(ap)
        self.assertEqual(self.engine.authorize(b).decision, Decision.REQUIRE_APPROVAL)

    def test_revocation_is_immediate(self):
        a = ActionEnvelope(actor="agent", effect="fs.write", resource="workspace/a.txt", method="WRITE", payload={"text": "a"})
        self.store.revoke(self.grant.grant_id, "capability", fmt_time(self.now), "test")
        self.assertEqual(self.engine.authorize(a).reason_code, "NO_VALID_CAPABILITY")

    def test_scope_cannot_escape(self):
        a = ActionEnvelope(actor="agent", effect="fs.write", resource="other/a.txt", method="WRITE", payload={"text": "a"})
        self.assertEqual(self.engine.authorize(a).decision, Decision.DENY)


if __name__ == "__main__": unittest.main()
