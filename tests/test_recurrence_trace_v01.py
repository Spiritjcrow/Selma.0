"""Deterministic synthetic-data tests; no network, devices, or real accounts."""
import copy
import hashlib
import unittest

from core.recurrence_trace_v01 import checkpoint_hash, review_trace


def digest(text):
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def event(event_id="e1", evidence="v1", previous=None, state="REVIEW"):
    return {
        "task_id": "SELMA52-TRACE", "event_id": event_id,
        "owner_role": "Black", "state": state,
        "artifact_sha256": digest("synthetic-artifact"),
        "evidence_sha256": digest(evidence), "previous_hash": previous,
    }


class RecurrenceTraceTests(unittest.TestCase):
    def test_valid_chain_with_changed_evidence_is_not_unchanged_loop(self):
        first = event()
        second = event("e2", "v2", checkpoint_hash(first))
        result = review_trace([first, second])
        self.assertEqual([], result["chain_break_indices"])
        self.assertEqual([], result["unchanged_revisit_indices"])
        self.assertEqual([1], result["changed_evidence_revisit_indices"])
        self.assertEqual("none_data_only", result["authority"])

    def test_duplicate_event_id_detected_even_when_chain_valid(self):
        first = event()
        second = event("e1", "v2", checkpoint_hash(first))
        self.assertEqual([1], review_trace([first, second])["duplicate_event_indices"])

    def test_unchanged_revisit_detected_without_auto_rejection(self):
        first = event()
        second = event("e2", "v1", checkpoint_hash(first))
        result = review_trace([first, second])
        self.assertEqual([1], result["unchanged_revisit_indices"])
        self.assertEqual([], result["duplicate_event_indices"])

    def test_cross_role_handoff_is_not_misclassified_as_unchanged_revisit(self):
        # Same task/state/artifact/evidence, but distinct authorized logical
        # role labels. This is provenance metadata, NOT actor authentication.
        first = event()
        second = event("e2", "v1", checkpoint_hash(first))
        second["owner_role"] = "White"
        third = event("e3", "v1", checkpoint_hash(second))
        third["owner_role"] = "White"
        result = review_trace([first, second, third])
        self.assertEqual([], result["chain_break_indices"])
        self.assertEqual([], result["duplicate_event_indices"])
        self.assertEqual([2], result["unchanged_revisit_indices"])
        self.assertEqual("none_data_only", result["authority"])

    def test_chain_break_and_mutation_are_reported(self):
        first = event()
        second = event("e2", "v2", digest("wrong"))
        self.assertEqual([1], review_trace([first, second])["chain_break_indices"])
        first_copy = copy.deepcopy(first)
        first_copy["evidence_sha256"] = digest("tampered")
        self.assertNotEqual(checkpoint_hash(first), checkpoint_hash(first_copy))

    def test_raw_secret_field_and_invalid_types_fail_closed(self):
        for mutation in (
            {"secret": "SYNTHETIC_ONLY"},
            {"event_id": "bad\nnewline"},
            {"artifact_sha256": "not-a-sha"},
            {"owner_role": "Admin"},
            {"state": "AUTHORIZED"},
        ):
            with self.subTest(mutation=mutation):
                item = event()
                item.update(mutation)
                with self.assertRaises(ValueError):
                    checkpoint_hash(item)
        with self.assertRaises(ValueError):
            review_trace([event()] * 129)

    def test_restart_is_deterministic_and_no_authority_claim(self):
        first = event()
        second = event("e2", "v1", checkpoint_hash(first))
        self.assertEqual(review_trace([first, second]),
                         review_trace(copy.deepcopy([first, second])))
        self.assertNotIn("accepted", review_trace([first]))


if __name__ == "__main__":
    unittest.main()
