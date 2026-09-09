import hashlib
import os
import sys
import unittest

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

from selma0_permission_engine_android_v1 import Selma0PermissionEngineAndroidV1
from selma0_procurement_gate_android_v1 import Selma0ProcurementGateAndroidV1


TRUSTED = "https://github.com/Spiritjcrow/Selma.0"


def digest(data):
    return hashlib.sha256(data).hexdigest()


class ProcurementGateAndroidV1Tests(unittest.TestCase):
    def make_gate(self, **overrides):
        params = {
            "trusted_sources": [TRUSTED],
            "cache_capacity": 3,
            "rollback_depth": 2,
        }
        params.update(overrides)
        return Selma0ProcurementGateAndroidV1(**params)

    def procure(self, gate, version="1.0.0", artifact=b"selma", **overrides):
        params = {
            "package": "demo.runtime",
            "version": version,
            "pinned_version": version,
            "source": TRUSTED,
            "expected_sha256": digest(artifact),
            "artifact": artifact,
            "capabilities": ["read"],
        }
        params.update(overrides)
        return gate.procure(**params)

    def test_01_trusted_source_correct_digest_is_accepted(self):
        decision = self.procure(self.make_gate())
        self.assertTrue(decision.allowed)

    def test_02_untrusted_source_is_rejected(self):
        decision = self.procure(
            self.make_gate(), source="https://example.invalid/untrusted"
        )
        self.assertFalse(decision.allowed)
        self.assertIn("provenance", decision.reason)

    def test_03_tampered_artifact_is_rejected(self):
        gate = self.make_gate()
        decision = gate.procure(
            package="demo.runtime",
            version="1.0.0",
            pinned_version="1.0.0",
            source=TRUSTED,
            expected_sha256=digest(b"original"),
            artifact=b"tampered",
            capabilities=["read"],
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(gate.status()["cache_size"], 0)

    def test_04_out_of_policy_capability_is_rejected(self):
        decision = self.procure(
            self.make_gate(), capabilities=["read", "ambient_root"]
        )
        self.assertFalse(decision.allowed)
        self.assertIn("outside procurement policy", decision.reason)

    def test_05_version_drift_is_rejected(self):
        decision = self.procure(
            self.make_gate(), version="1.0.1", pinned_version="1.0.0"
        )
        self.assertFalse(decision.allowed)
        self.assertIn("exact pin", decision.reason)

    def test_06_cache_capacity_evicts_oldest_inactive_artifact(self):
        gate = self.make_gate(cache_capacity=2)
        self.procure(gate, version="1.0.0", artifact=b"one")
        self.procure(gate, version="1.1.0", artifact=b"two")
        self.procure(gate, version="1.2.0", artifact=b"three")
        versions = [item["version"] for item in gate.cached()]
        self.assertEqual(versions, ["1.1.0", "1.2.0"])

    def test_07_previous_verified_generation_can_rollback(self):
        gate = self.make_gate()
        self.procure(gate, version="1.0.0", artifact=b"one")
        gate.activate("demo.runtime", "1.0.0")
        self.procure(gate, version="2.0.0", artifact=b"two")
        gate.activate("demo.runtime", "2.0.0")
        restored = gate.rollback("demo.runtime")
        self.assertEqual(restored.version, "1.0.0")

    def test_08_rollback_history_limit_is_enforced(self):
        gate = self.make_gate(cache_capacity=5, rollback_depth=2)
        for version in ("1.0.0", "2.0.0", "3.0.0", "4.0.0"):
            self.procure(gate, version=version, artifact=version.encode())
            gate.activate("demo.runtime", version)
        self.assertEqual(gate.rollback("demo.runtime").version, "3.0.0")
        self.assertEqual(gate.rollback("demo.runtime").version, "2.0.0")
        with self.assertRaises(LookupError):
            gate.rollback("demo.runtime")

    def test_09_sensitive_runtime_capability_requires_approval(self):
        gate = self.make_gate()
        self.procure(gate, capabilities=["read", "sensitive_read"])
        gate.activate("demo.runtime", "1.0.0")
        decision = gate.authorize_runtime(
            "demo.runtime",
            "sensitive_read",
            Selma0PermissionEngineAndroidV1(),
            approved=False,
        )
        self.assertFalse(decision.allowed)
        self.assertTrue(decision.requires_approval)

    def test_10_sensitive_runtime_capability_allows_explicit_approval(self):
        gate = self.make_gate()
        self.procure(gate, capabilities=["read", "sensitive_read"])
        gate.activate("demo.runtime", "1.0.0")
        decision = gate.authorize_runtime(
            "demo.runtime",
            "sensitive_read",
            Selma0PermissionEngineAndroidV1(),
            approved=True,
        )
        self.assertTrue(decision.allowed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
