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
        for control in ("\n", "\r", "\u2028", "\u2029",
                        "\u202e", "\u200b", "\x00", "\t"):
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

    def test_control_in_provenance_label_is_ambiguous(self):
        # strip() must not conceal controls in source/command/observed labels.
        for control in ("\t", "\r", "\n", "\u2028", "\u2029"):
            with self.subTest(control=repr(control)):
                item = record("tester", "pass")
                item["evidence"] = [
                    f"source{control}: synthetic fixture",
                    "command: python3 -m unittest",
                    "observed: synthetic PASS",
                ]
                result = validate_exchange([record(), item])
                self.assertEqual("ambiguous_unverified", result["evidence_trace"])
                self.assertEqual("tester_reported_pass", result["state"])
                self.assertNotIn("accepted", result)

    def test_evidence_edge_controls_downgrade_without_trimming(self):
        # Validated free text must preserve edge controls for trace analysis.
        # These are synthetic reports, never independently verified tests.
        for control in ("\t", "\r", "\n", "\u2028", "\u2029",
                        "\x00", "\u200b"):
            for side in ("leading", "trailing"):
                with self.subTest(control=repr(control), side=side):
                    item = record("tester", "pass")
                    source = ("source: synthetic fixture" + control if side == "trailing"
                              else control + "source: synthetic fixture")
                    item["evidence"] = [
                        source, "command: python3 -m unittest",
                        "observed: synthetic PASS",
                    ]
                    self.assertEqual(
                        source, HandoffMessage.from_mapping(item).evidence[0]
                    )
                    result = validate_exchange([record(), item])
                    self.assertEqual("ambiguous_unverified", result["evidence_trace"])
                    self.assertNotIn("accepted", result)

    def test_plain_edge_spaces_remain_source_labeled_unverified(self):
        item = record("tester", "pass")
        item["evidence"] = [
            " source: synthetic fixture ", "command: python3 -m unittest",
            "observed: synthetic PASS",
        ]
        result = validate_exchange([record(), item])
        self.assertEqual("source_labeled_unverified", result["evidence_trace"])
        self.assertNotIn("accepted", result)

    def test_hidden_label_lookalikes_downgrade_provenance(self):
        # Unrecognized labels must not hide contradictory source claims.
        # Free-text evidence is retained, but derived labels stay unverified.
        for hidden_label in ("sour\u200bce", "source\u034f", "comm\u200band", "observed\u202e"):
            with self.subTest(hidden_label=repr(hidden_label)):
                item = record("tester", "pass")
                item["evidence"] = [
                    "source: synthetic fixture A",
                    "command: python3 -m unittest",
                    "observed: synthetic PASS",
                    f"{hidden_label}: contradictory fixture B",
                ]
                result = validate_exchange([record(), item])
                self.assertEqual("ambiguous_unverified", result["evidence_trace"])
                self.assertEqual("tester_reported_pass", result["state"])
                self.assertNotIn("accepted", result)

    def test_controls_in_unrelated_notes_cannot_hide_second_provenance_claim(self):
        # Unrecognized notes remain untrusted; hidden separators must not
        # make a conflicting claim look like a clean three-label trace.
        for control in ("\n", "\r", "\t", "\u200b", "\u202e", "\ue000"):
            for note_format in ("notes: benign{}source: forged FAIL",
                                "notes benign{}source: forged FAIL"):
                with self.subTest(control=repr(control), note_format=note_format):
                    item = record("tester", "pass")
                    item["evidence"] = [
                        "source: synthetic fixture",
                        "command: unittest",
                        "observed: synthetic PASS",
                        note_format.format(control),
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

    def test_structural_identifiers_reject_surrounding_whitespace(self):
        # Do not turn distinct supplied refs/IDs into the same normalized ID.
        for field in ("task_id", "repository", "ref", "actor_role", "status", "artifact"):
            for padding in (" ", "\u00a0"):
                for side in ("left", "right"):
                    with self.subTest(field=field, padding=repr(padding), side=side):
                        item = record()
                        item[field] = (padding + item[field] if side == "left"
                                       else item[field] + padding)
                        with self.assertRaisesRegex(ValueError, "surrounding whitespace"):
                            HandoffMessage.from_mapping(item)

    def test_structural_identifiers_reject_decomposed_unicode_aliases(self):
        # Visually identical NFC and NFD spellings must not silently alias.
        for field in ("task_id", "repository", "ref", "actor_role", "status", "artifact"):
            with self.subTest(field=field):
                item = record()
                item[field] += "Cafe\u0301"  # decomposed e + combining acute
                with self.assertRaisesRegex(ValueError, "non-NFC"):
                    HandoffMessage.from_mapping(item)
        # Preserve legitimate precomposed Unicode in structural IDs.
        item = record()
        item["task_id"] += "Caf\u00e9"
        self.assertEqual(HandoffMessage.from_mapping(item).task_id, item["task_id"])

    def test_nfc_stable_invisible_identifier_modifiers_rejected(self):
        # NFC alone does not reject these invisible Mn code points.
        modifiers = ("\u034f", "\ufe0e", "\ufe0f", "\U000e0100", "\U000e01ef")
        for field in ("task_id", "repository", "ref", "actor_role", "status", "artifact"):
            for char in modifiers:
                with self.subTest(field=field, codepoint=hex(ord(char))):
                    item = record()
                    item[field] += char
                    with self.assertRaisesRegex(ValueError, "unsafe identifier characters"):
                        HandoffMessage.from_mapping(item)

    def test_invisible_provenance_detail_stays_ambiguous(self):
        # Evidence is free text, but hidden modifiers cannot create clean labels.
        for char in ("\u034f", "\ufe0f", "\U000e0100"):
            with self.subTest(codepoint=hex(ord(char))):
                item = record("tester", "pass")
                item["evidence"] = [
                    "source: synthetic fixture" + char,
                    "command: python3 -m unittest",
                    "observed: synthetic PASS",
                ]
                result = validate_exchange([record(), item])
                self.assertEqual("ambiguous_unverified", result["evidence_trace"])
                self.assertNotIn("accepted", result)

    def test_structural_identifier_allows_visible_non_ascii_text(self):
        item = record()
        item["task_id"] = "SELMA-Café-001"
        self.assertEqual("SELMA-Café-001", HandoffMessage.from_mapping(item).task_id)

    def test_repository_slug_rejects_unicode_lookalikes_and_bad_structure(self):
        # Repository labels are untrusted data, never proof of actor identity.
        bad = (
            "Spiritjcr\u043ew/Selma.0",  # Cyrillic o
            "Spiritjcrow/\uff33elma.0",  # fullwidth S
            "Spiritjcrow/Selma.0/extra",
            "/Selma.0", "Spiritjcrow/", "Spiritjcrow/..",
            "Spiritjcrow/Selma 0", "Spiritjcrow/Selma.0?x",
            "Spiritjcrow\\\\Selma.0",
        )
        for slug in bad:
            with self.subTest(slug=slug):
                item = record()
                item["repository"] = slug
                with self.assertRaisesRegex(ValueError, "ASCII owner/name slug"):
                    HandoffMessage.from_mapping(item)
        for slug in ("Spiritjcrow/Selma.0", "owner/repo_name-v1.2"):
            with self.subTest(valid=slug):
                item = record()
                item["repository"] = slug
                self.assertEqual(HandoffMessage.from_mapping(item).repository, slug)

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
