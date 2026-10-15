import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from selma0_security_policy_v1 import ApprovalGate, private_directory, redact_metadata

OWNER = "synthetic-owner-" + "a" * 40
APPROVAL = "synthetic-approval-" + "b" * 40
ROUTE = "/api/selma0/chat/v1"


class SecurityPolicyTests(unittest.TestCase):
    def setUp(self):
        self.now = [1000]
        self.gate = ApprovalGate(OWNER, APPROVAL, clock=lambda: self.now[0])

    def session(self):
        return self.gate.new_session(OWNER)

    def issue(self, session, **kwargs):
        return self.gate.approve(
            session, kwargs.get("route", ROUTE), "selma.chat",
            {"message": "synthetic"}, kwargs.get("request_id", "req-1"),
            approval_proof=kwargs.get("proof", APPROVAL),
        )

    def consume(self, session, ticket, **kwargs):
        return self.gate.consume(
            session, ticket, kwargs.get("route", ROUTE), "selma.chat",
            {"message": "synthetic"}, kwargs.get("request_id", "req-1"),
        )

    def test_owner_proof_required(self):
        with self.assertRaises(PermissionError):
            self.gate.new_session(None)
        with self.assertRaises(PermissionError):
            self.gate.new_session("wrong")

    def test_independent_approval_proof_required(self):
        session = self.session()
        with self.assertRaises(PermissionError):
            self.gate.approve(session, ROUTE, "selma.chat",
                              {"message": "synthetic"}, "req-1",
                              trusted_gesture=True)

    def test_single_use_and_request_id(self):
        session = self.session()
        ticket = self.issue(session)
        self.assertTrue(self.consume(session, ticket))
        self.assertFalse(self.consume(session, ticket))
        with self.assertRaises(PermissionError):
            self.issue(session)

    def test_route_substitution_rejected(self):
        session = self.session()
        ticket = self.issue(session)
        self.assertFalse(self.consume(
            session, ticket, route="/api/selma0/tools/execute/v1"))
        self.assertTrue(self.consume(session, ticket))

    def test_request_id_substitution_rejected(self):
        session = self.session()
        ticket = self.issue(session)
        self.assertFalse(self.consume(session, ticket, request_id="req-2"))
        self.assertTrue(self.consume(session, ticket))

    def test_cross_session_rejected(self):
        first = self.session()
        second = self.session()
        ticket = self.issue(first)
        self.assertFalse(self.consume(second, ticket))
        self.assertTrue(self.consume(first, ticket))

    def test_expired_ticket_rejected(self):
        session = self.session()
        ticket = self.issue(session)
        self.now[0] += 31
        self.assertFalse(self.consume(session, ticket))

    def test_expired_session_rejected(self):
        session = self.session()
        self.now[0] += 901
        with self.assertRaises(PermissionError):
            self.issue(session)

    def test_nonfinite_arguments_rejected(self):
        session = self.session()
        with self.assertRaises(ValueError):
            self.gate.approve(session, ROUTE, "selma.chat",
                              {"x": float("nan")}, "req-1", APPROVAL)

    def test_metadata_minimization(self):
        self.assertEqual(
            redact_metadata({"operation": "chat", "message": "synthetic",
                             "error": "synthetic"}),
            {"operation": "chat"},
        )

    def test_private_directory(self):
        with tempfile.TemporaryDirectory() as root:
            path = private_directory(os.path.join(root, "private"))
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o700)


if __name__ == "__main__":
    unittest.main()
