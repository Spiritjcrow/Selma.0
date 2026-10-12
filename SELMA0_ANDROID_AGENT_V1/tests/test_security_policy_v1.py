import os
import sys
import tempfile
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from selma0_security_policy_v1 import ApprovalGate, private_directory, redact_metadata

class SecurityPolicyTests(unittest.TestCase):
    def test_approval_single_use(self):
        gate = ApprovalGate()
        session = gate.new_session()
        ticket = gate.approve(session, "write", {"x": 1}, trusted_gesture=True)
        self.assertTrue(gate.consume(session, ticket, "write", {"x": 1}))
        self.assertFalse(gate.consume(session, ticket, "write", {"x": 1}))

    def test_approval_binding(self):
        gate = ApprovalGate()
        session = gate.new_session()
        ticket = gate.approve(session, "write", {"x": 1}, trusted_gesture=True)
        self.assertFalse(gate.consume(session, ticket, "write", {"x": 2}))

    def test_untrusted_gesture(self):
        gate = ApprovalGate()
        with self.assertRaises(PermissionError):
            gate.approve(gate.new_session(), "write", {}, trusted_gesture=False)

    def test_metadata_minimization(self):
        self.assertEqual(redact_metadata({"operation": "chat", "message": "dummy-secret", "error": "dummy-secret"}), {"operation": "chat"})

    def test_private_directory(self):
        with tempfile.TemporaryDirectory() as root:
            path = private_directory(os.path.join(root, "private"))
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o700)

if __name__ == "__main__":
    unittest.main()
