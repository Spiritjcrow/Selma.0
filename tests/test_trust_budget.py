"""Proof-gated, irreversible trust increases and authorization invariants."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import unittest
import tempfile
from pathlib import Path

from core.protocols import RiskClass
from core.trust_budget import EvidenceTrustLedger, VerifiedSuccess


START = datetime(2026, 10, 1, tzinfo=timezone.utc)


def proof(number, *, actor="sol", scope="validate", verifier="ci", day=0):
    return VerifiedSuccess(
        actor_id=actor,
        scope=scope,
        proof_id=f"{actor}:{scope}:{number}",
        verifier_id=verifier,
        observed_at=START + timedelta(days=day),
    )


class EvidenceTrustLedgerTests(unittest.TestCase):
    def setUp(self):
        self.now = START + timedelta(days=100)
        self.ledger = EvidenceTrustLedger(
            verify_proof=lambda p: p.proof_id.startswith("sol:"),
            database_path=":memory:",
            clock=lambda: self.now,
        )

    def test_starts_with_baseline_and_no_auto_authority(self):
        b = self.ledger.budget("sol", "validate", RiskClass.READ)
        self.assertEqual((b.trust.tier, b.max_parallel, b.max_retries), (0, 1, 0))
        self.assertTrue(b.requires_authorization)

    def test_gains_never_decay_even_after_time_advances(self):
        previous = self.ledger.state("sol", "validate").tier
        for n in range(1, 30):
            self.ledger.accept(proof(n, verifier=f"ci-{n%3}", day=n%6))
            current = self.ledger.state("sol", "validate").tier
            self.assertGreaterEqual(current, previous)
            previous = current
        before = self.ledger.budget("sol", "validate", RiskClass.READ)
        self.assertEqual((before.trust.tier, before.max_parallel), (3, 8))
        self.now += timedelta(days=3000)
        after = self.ledger.budget("sol", "validate", RiskClass.READ)
        self.assertEqual(after, before)

    def test_multiple_collaborators_and_days_needed(self):
        for n in range(1, 26):
            self.ledger.accept(proof(n))
        self.assertEqual(self.ledger.state("sol", "validate").tier, 1)
        for n in range(26, 30):
            self.ledger.accept(proof(n, verifier=f"ci-{n}", day=n-25))
        self.assertEqual(self.ledger.state("sol", "validate").tier, 3)

    def test_scoped_trust_never_spills_into_another_operation(self):
        for n in range(1, 30):
            self.ledger.accept(proof(n, verifier=f"ci-{n%3}", day=n%6))
        self.assertEqual(self.ledger.state("sol", "write").tier, 0)
        self.assertEqual(self.ledger.state("another-agent", "validate").tier, 0)

    def test_sensitive_work_remains_at_baseline_even_at_peak(self):
        for n in range(1, 30):
            self.ledger.accept(proof(n, verifier=f"ci-{n%3}", day=n%6))
        for risk in (RiskClass.SENSITIVE_READ, RiskClass.APPROVED_WRITE, None):
            with self.subTest(risk=risk):
                b = self.ledger.budget("sol", "validate", risk)
                self.assertEqual((b.max_parallel, b.max_retries), (1, 0))
                self.assertTrue(b.requires_authorization)

    def test_unverified_replay_self_report_and_bad_time_rejected(self):
        with self.assertRaises(ValueError):
            self.ledger.accept(proof(1, actor="unknown"))
        with self.assertRaises(ValueError):
            self.ledger.accept(proof(1, actor="sol", verifier="sol"))
        with self.assertRaises(ValueError):
            self.ledger.accept(VerifiedSuccess("sol", "validate", "sol:x", "ci", datetime.now()))
        with self.assertRaises(ValueError):
            self.ledger.accept(proof(1, day=150))
        self.ledger.accept(proof(1))
        with self.assertRaises(ValueError):
            self.ledger.accept(proof(1))
        self.assertEqual(self.ledger.state("sol", "validate").successes, 1)

    def test_verifier_errors_do_not_issue_credit(self):
        ledger = EvidenceTrustLedger(lambda _: (_ for _ in ()).throw(RuntimeError("bad proof")), database_path=":memory:")
        with self.assertRaises(RuntimeError):
            ledger.accept(proof(1))
        self.assertEqual(ledger.state("sol", "validate").successes, 0)

    def test_saturated_ledger_preserves_existing_credit(self):
        ledger = EvidenceTrustLedger(lambda _: True, database_path=":memory:", clock=lambda: self.now, max_records=1)
        ledger.accept(proof(1))
        with self.assertRaises(RuntimeError):
            ledger.accept(proof(2))
        self.assertEqual(ledger.state("sol", "validate").successes, 1)

    def test_parallel_duplicate_submission_counts_once(self):
        ledger = EvidenceTrustLedger(lambda _: True, database_path=":memory:", clock=lambda: self.now)
        def submit(_):
            try:
                ledger.accept(proof(1))
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(submit, range(20)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(ledger.state("sol", "validate").successes, 1)


    def test_credit_survives_process_restarts_and_replay_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "verified_trust.sqlite3"
            first = EvidenceTrustLedger(
                lambda _: True, database_path=path, clock=lambda: self.now,
            )
            first.accept(proof(1))
            first.close()
            reopened = EvidenceTrustLedger(
                lambda _: True, database_path=path, clock=lambda: self.now,
            )
            self.assertEqual(reopened.state("sol", "validate").successes, 1)
            with self.assertRaises(ValueError):
                reopened.accept(proof(1))
            reopened.accept(proof(2))
            self.assertEqual(reopened.state("sol", "validate").successes, 2)
            reopened.close()


if __name__ == "__main__":
    unittest.main()
