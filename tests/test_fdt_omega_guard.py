import base64
import json
import tempfile
import time
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from prototypes.fdt_omega.guard import OmegaGate, ReplayStore, canonical_bytes


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "replay.sqlite")
        self.key = Ed25519PrivateKey.generate()
        pub = self.key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.gate = OmegaGate({("node-A", "key-1"): pub}, ReplayStore(self.db))
        self.t = 1700000000

    def envelope(self, *, action="HEALTH_REPORT", protocol="FDT-Omega", nonce="once"):
        e = dict(protocol=protocol, version=1, node_id="node-A", key_id="key-1", issued_at=self.t,
                 expires_at=self.t+60, nonce=nonce, action=action, payload={"state": "ready"})
        e["signature"] = base64.b64encode(self.key.sign(canonical_bytes(e))).decode("ascii")
        return e

    def test_valid_signature(self):
        r = self.gate.verify(self.envelope(), now=self.t + 1)
        self.assertTrue(r.accepted)
        self.assertFalse(r.freeze_node)

    def test_old_alias_is_accepted(self):
        r = self.gate.verify(self.envelope(protocol="FTD-Omega"), now=self.t+1)
        self.assertTrue(r.accepted)
        self.assertEqual("FDT-Omega", r.protocol)

    def test_tampering_fails(self):
        e = self.envelope(); e["payload"]["state"] = "mutated"
        r = self.gate.verify(e, now=self.t+1)
        self.assertFalse(r.accepted); self.assertTrue(r.freeze_node)

    def test_alias_must_be_signed(self):
        e = self.envelope(); e["protocol"] = "FTD-Omega"
        self.assertEqual("signature_verification_failed", self.gate.verify(e, now=self.t+1).reason)

    def test_unknown_node_fails(self):
        e=self.envelope(); e["node_id"]="untrusted"
        self.assertEqual("untrusted_node_key", self.gate.verify(e, now=self.t+1).reason)

    def test_replay_fails_and_survives_recreation(self):
        e = self.envelope(); self.assertTrue(self.gate.verify(e,now=self.t+1).accepted)
        another=OmegaGate(self.gate.trusted_keys,ReplayStore(self.db))
        self.assertEqual("replay_detected",another.verify(e,now=self.t+2).reason)

    def test_expired_does_not_freeze(self):
        r=self.gate.verify(self.envelope(),now=self.t+300)
        self.assertFalse(r.accepted); self.assertFalse(r.freeze_node)

    def test_future_does_not_freeze(self):
        r=self.gate.verify(self.envelope(),now=self.t-300)
        self.assertFalse(r.accepted); self.assertFalse(r.freeze_node)

    def test_mutation_execution_blocked(self):
        r=self.gate.verify(self.envelope(action="PROTOCOL_MUTATION"),now=self.t+1)
        self.assertEqual("action_not_authorized",r.reason)
        self.assertTrue(r.freeze_node)

    def test_settlements_blocked(self):
        r=self.gate.verify(self.envelope(action="SETTLE"),now=self.t+1)
        self.assertFalse(r.accepted)

    def test_mutation_proposals_allowed_but_not_executed(self):
        self.assertTrue(self.gate.verify(self.envelope(action="MUTATION_PROPOSAL"),now=self.t+1).accepted)

    def test_extra_schema_fields_blocked(self):
        e=self.envelope();e["debug"]=1
        self.assertEqual("invalid_envelope_schema",self.gate.verify(e,now=self.t+1).reason)

    def test_nonfinite_numbers_blocked(self):
        e=self.envelope();e["payload"]["value"]=float("nan")
        self.assertEqual("verification_error",self.gate.verify(e,now=self.t+1).reason)

    def test_wrong_key_rejected(self):
        wrong = Ed25519PrivateKey.generate()
        e=self.envelope(); e["signature"]=base64.b64encode(wrong.sign(canonical_bytes({k:v for k,v in e.items() if k!="signature"}))).decode()
        self.assertEqual("signature_verification_failed",self.gate.verify(e,now=self.t+1).reason)

    def test_missing_trust_list_rejects(self):
        empty=OmegaGate({},ReplayStore(self.db))
        self.assertFalse(empty.verify(self.envelope(),now=self.t+1).accepted)

if __name__ == "__main__": unittest.main()