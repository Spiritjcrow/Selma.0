"""Portable tests for the SelmaOS dual-phone JSON handoff contract."""

from __future__ import annotations

import unittest

from core.duo_handoff import HandoffMessage, validate_exchange


def record(role="builder", status="submitted"):
    return {
        "schema_version": 1,
        "task_id": "SELMA49-001",
        "repository": "Spiritjcrow/Selma.0",
        "ref": "feature/selmaos-dual-agent-handoff-20261017",
        "actor_role": role,
        "status": status,
        "artifact": "commit:abc123",
        "evidence": [] if role == "builder" else ["Manual steps and observed result"],
        "summary": "Scoped handoff sample; not physical-device evidence",
    }


class HandoffTests(unittest.TestCase):
    def test_builder_is_pending_until_tester_report(self):
        self.assertEqual(
            "awaiting_tester", validate_exchange([record()])["state"]
        )

    def test_tester_reported_pass_fail_blocked(self):
        for status in ("pass", "fail", "blocked"):
            with self.subTest(status=status):
                result = validate_exchange([record(), record("tester", status)])
                self.assertEqual(f"tester_reported_{status}", result["state"])

    def test_unattributed_tester_pass_stays_unverified(self):
        result = validate_exchange([record(), record("tester", "pass")])
        self.assertEqual(result["state"], "tester_reported_pass")
        self.assertEqual(result["evidence_trace"], "unattributed_unverified")

    def test_source_labels_do_not_claim_independent_verification(self):
        item = record("tester", "pass")
        item["evidence"] = [
            "source: synthetic fixture (not a device)",
            "command: python3 -m unittest test_duo_handoff",
            "observed: 11 local checks PASS; no independent device",
        ]
        result = validate_exchange([record(), item])
        self.assertEqual(result["evidence_trace"], "source_labeled_unverified")
        self.assertEqual(result["state"], "tester_reported_pass")
        self.assertNotIn("accepted", result)

    def test_empty_and_embedded_labels_are_not_source_labeled(self):
        for evidence in (
            ["source:", "command: test", "observed: PASS"],
            ["notes source: fake", "command: test", "observed: PASS"],
            ["source: fixture", "command: ", "observed: PASS"],
            ["source: fixture", "command: test"],
        ):
            with self.subTest(evidence=evidence):
                item = record("tester", "pass")
                item["evidence"] = evidence
                self.assertEqual(
                    validate_exchange([record(), item])["evidence_trace"],
                    "unattributed_unverified",
                )

    def test_duplicate_provenance_labels_stay_ambiguous_and_unverified(self):
        for repeated in ("source", "command", "observed"):
            with self.subTest(repeated=repeated):
                item = record("tester", "pass")
                item["evidence"] = [
                    "source: synthetic fixture A",
                    "command: python3 -m unittest test_duo_handoff",
                    "observed: synthetic PASS",
                    f"{repeated.upper()}: conflicting second report",
                ]
                result = validate_exchange([record(), item])
                self.assertEqual("ambiguous_unverified", result["evidence_trace"])
                self.assertEqual("tester_reported_pass", result["state"])
                self.assertNotIn("accepted", result)

    def test_embedded_control_in_provenance_detail_is_ambiguous(self):
        # Free-text evidence remains allowed, but source labels with hidden
        # lines or directional/zero-width controls are not clean provenance.
        for control in ("\\n", "\\r", "\\u2028", "\\u2029",
                        "\\u202e", "\\u200b", "\\x00", "\\t"):
            with self.subTest(control=repr(control)):
                item = record("tester", "pass")
                item["evidence"] = [
                    "source: synthetic fixture" + control + "source: conflicting",
                    "command: python3 -m unittest",
                    "observed: synthetic PASS",
                ]
                result = validate_exchange([record(), item])
                self.assertEqual("ambiguous_unverified", result["evidence_trace"])
                self.assertEqual("tester_reported_pass", result["state"])
                self.assertNotIn("accepted", result)

    def test_duplicate_unrelated_notes_do_not_spoil_source_labels(self):
        item = record("tester", "pass")
        item["evidence"] = [
            "source: synthetic fixture",
            "command: python3 -m unittest test_duo_handoff",
            "observed: synthetic PASS",
            "notes: unverified",
            "notes: second note",
        ]
        self.assertEqual(
            "source_labeled_unverified",
            validate_exchange([record(), item])["evidence_trace"],
        )

    def test_blank_first_label_never_becomes_source_labeled(self):
        item = record("tester", "pass")
        item["evidence"] = [
            "source: ", "source: synthetic fixture",
            "command: python3 -m unittest test_duo_handoff",
            "observed: synthetic PASS",
        ]
        self.assertEqual(
            "unattributed_unverified",
            validate_exchange([record(), item])["evidence_trace"],
        )

    def test_structural_identifiers_reject_invisible_or_control_text(self):
        # Source-only negative cases. A label is never an authenticated actor.
        unsafe = ("\x00", "\n", "\u202e", "\u200b", "\u2028", "\ud800")
        for field in ("task_id", "repository", "ref", "actor_role", "status", "artifact"):
            for char in unsafe:
                with self.subTest(field=field, codepoint=hex(ord(char))):
                    item = record()
                    item[field] += char
                    with self.assertRaisesRegex(ValueError, "unsafe identifier characters"):
                        HandoffMessage.from_mapping(item)

    def test_structural_identifier_allows_visible_non_ascii_text(self):
        item = record()
        item["task_id"] = "SELMA-Café-001"
        self.assertEqual("SELMA-Café-001", HandoffMessage.from_mapping(item).task_id)

    def test_builder_cannot_claim_verified_state(self):
        with self.assertRaisesRegex(ValueError, "role cannot report"):
            HandoffMessage.from_mapping(record("builder", "pass"))

    def test_tester_cannot_submit_as_builder(self):
        with self.assertRaisesRegex(ValueError, "role cannot report"):
            HandoffMessage.from_mapping(record("tester", "submitted"))

    def test_tester_evidence_must_be_present(self):
        item = record("tester", "pass")
        item["evidence"] = []
        with self.assertRaisesRegex(ValueError, "require reproducible evidence"):
            validate_exchange([record(), item])

    def test_task_and_artifact_must_match(self):
        for field, changed in (
            ("task_id", "OTHER"), ("repository", "other/repo"),
            ("ref", "other"), ("artifact", "another"),
        ):
            with self.subTest(field=field):
                item = record("tester", "pass")
                item[field] = changed
                with self.assertRaisesRegex(ValueError, "does not match"):
                    validate_exchange([record(), item])

    def test_unsupported_schema_fails_closed(self):
        for value in (True, 2, "1", None):
            with self.subTest(value=value):
                item = record()
                item["schema_version"] = value
                with self.assertRaisesRegex(ValueError, "unsupported schema"):
                    HandoffMessage.from_mapping(item)

    def test_rejects_missing_and_extra_keys(self):
        missing = record()
        del missing["ref"]
        extra = record()
        extra["approved"] = True
        for item in (missing, extra):
            with self.assertRaisesRegex(ValueError, "fields mismatch"):
                HandoffMessage.from_mapping(item)

    def test_rejects_empty_or_malformed_evidence(self):
        for evidence in ([""], [None], "not an array"):
            with self.subTest(evidence=evidence):
                item = record("tester", "pass")
                item["evidence"] = evidence
                with self.assertRaises(ValueError):
                    HandoffMessage.from_mapping(item)

    def test_rejects_non_builder_start_and_multiple_testers(self):
        with self.assertRaisesRegex(ValueError, "begin with a builder"):
            validate_exchange([record("tester", "pass")])
        with self.assertRaisesRegex(ValueError, "1 or 2 messages"):
            validate_exchange([
                record(), record("tester", "pass"), record("tester", "pass")
            ])

    def test_rejects_non_json_object_or_unknown_roles(self):
        with self.assertRaises(ValueError):
            HandoffMessage.from_mapping(None)
        item = record()
        item["actor_role"] = "admin"
        with self.assertRaises(ValueError):
            HandoffMessage.from_mapping(item)


if __name__ == "__main__":
    unittest.main()
