import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fdt_gate.canonical import fmt_time
from fdt_gate.crypto import Keyring, Signer
from fdt_gate.models import ActionEnvelope, Decision
from fdt_gate.policy import compile_policy, verify_policy
from fdt_gate.security import WingDingynouse, issue_grant, verify_decision_receipt
from fdt_gate.store import SecurityStore

POLICY = """fdt-policy 0.7
policy delegation
version 0.7.0
default DENY
rule write effect=fs.write resource=* capability=write decision=ALLOW methods=WRITE max_payload_bytes=1024 max_calls_per_minute=100
"""


class DelegationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.genesis = Signer.generate(); self.delegate = Signer.generate(); self.runtime = Signer.generate()
        self.keys = Keyring()
        for s in (self.genesis, self.delegate, self.runtime): self.keys.add_signer(s)
        self.now = datetime(2026, 9, 9, tzinfo=timezone.utc)
        self.store = SecurityStore(Path(self.tmp.name) / "state.db")
        self.bundle = compile_policy(POLICY, self.genesis)

    def tearDown(self): self.tmp.cleanup()

    def engine(self):
        return WingDingynouse(policy=self.bundle, trusted_keys=self.keys,
                              genesis_key_ids={self.genesis.key_id}, runtime_signer=self.runtime,
                              store=self.store, clock=lambda: self.now)

    def parent(self):
        p = issue_grant(signer=self.genesis, issuer="genesis", subject="delegator", capability="write",
                        resource_prefix="workspace/", effects=("fs.write",), methods=("WRITE",),
                        not_before=fmt_time(self.now - timedelta(minutes=1)),
                        expires_at=fmt_time(self.now + timedelta(hours=2)), issued_at=fmt_time(self.now))
        self.store.put_grant(p)
        return p

    def test_narrow_delegation_allows(self):
        p = self.parent()
        c = issue_grant(signer=self.delegate, issuer="delegator", subject="agent", capability="write",
                        resource_prefix="workspace/sub/", effects=("fs.write",), methods=("WRITE",),
                        not_before=fmt_time(self.now), expires_at=fmt_time(self.now + timedelta(hours=1)),
                        issued_at=fmt_time(self.now), parent_id=p.grant_id)
        self.store.put_grant(c)
        action = ActionEnvelope(actor="agent", effect="fs.write", resource="workspace/sub/x", method="WRITE")
        receipt = self.engine().authorize(action)
        self.assertEqual(receipt.decision, Decision.ALLOW)
        self.assertTrue(verify_decision_receipt(receipt, self.keys))

    def test_broadening_delegation_denied(self):
        p = self.parent()
        c = issue_grant(signer=self.delegate, issuer="delegator", subject="agent", capability="write",
                        resource_prefix="other/", effects=("fs.write",), methods=("WRITE",),
                        not_before=fmt_time(self.now), expires_at=fmt_time(self.now + timedelta(hours=1)),
                        issued_at=fmt_time(self.now), parent_id=p.grant_id)
        self.store.put_grant(c)
        action = ActionEnvelope(actor="agent", effect="fs.write", resource="other/x", method="WRITE")
        self.assertEqual(self.engine().authorize(action).reason_code, "NO_VALID_CAPABILITY")

    def test_policy_tamper_breaks_verification(self):
        self.assertTrue(verify_policy(self.bundle, self.keys))
        tampered = replace(self.bundle, source_hash="sha256:" + "0" * 64)
        self.assertFalse(verify_policy(tampered, self.keys))


if __name__ == "__main__": unittest.main()
