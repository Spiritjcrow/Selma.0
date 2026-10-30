"""Fail-closed direct Python mapping-key tests (synthetic fixtures only)."""
import unittest

from core.duo_handoff import HandoffMessage, validate_exchange
from tests.test_duo_handoff import record


class MappingKeyGuardTests(unittest.TestCase):
    def test_rejects_mixed_type_extra_keys_without_typeerror(self):
        for bad_key in (1, True, ("tuple",), None):
            with self.subTest(bad_key=repr(bad_key)):
                item = record()
                item[bad_key] = "extra"
                item["also_extra"] = "extra"
                with self.assertRaisesRegex(ValueError, "field names must be strings"):
                    HandoffMessage.from_mapping(item)

    def test_rejects_non_string_key_even_when_only_extra(self):
        item = record()
        item[9] = "extra"
        with self.assertRaisesRegex(ValueError, "field names must be strings"):
            validate_exchange([item])

    def test_existing_string_key_mismatch_still_diagnosed(self):
        item = record()
        item["also_extra"] = "extra"
        with self.assertRaisesRegex(ValueError, "fields mismatch"):
            HandoffMessage.from_mapping(item)

    def test_normal_exchange_still_passes(self):
        self.assertEqual("tester_reported_pass", validate_exchange([record(), record("tester", "pass")])["state"])

    def test_rejects_duplicate_enumerated_mapping_key(self):
        # Custom Mapping iteration may repeat a key while __getitem__
        # resolves both to the same value. Reject this ambiguity.
        from collections.abc import Mapping

        class DuplicateEnumeratingMapping(Mapping):
            def __init__(self, data):
                self.data = data

            def __iter__(self):
                yield from self.data
                yield "task_id"

            def __len__(self):
                return len(self.data) + 1

            def __getitem__(self, key):
                return self.data[key]

        ambiguous = DuplicateEnumeratingMapping(record())
        with self.assertRaisesRegex(ValueError, "duplicate message field names"):
            HandoffMessage.from_mapping(ambiguous)
        with self.assertRaisesRegex(ValueError, "duplicate message field names"):
            validate_exchange([ambiguous])

    def test_unique_enumerated_mapping_still_passes(self):
        from collections.abc import Mapping

        class UniqueMapping(Mapping):
            def __init__(self, data):
                self.data = data

            def __iter__(self):
                return iter(self.data)

            def __len__(self):
                return len(self.data)

            def __getitem__(self, key):
                return self.data[key]

        self.assertEqual(record()["task_id"],
                         HandoffMessage.from_mapping(UniqueMapping(record())).task_id)

    def test_rejects_list_subclass_that_spoofs_evidence_bound(self):
        class MisleadingList(list):
            def __len__(self):
                return 1

        item = record("tester", "pass")
        item["evidence"] = MisleadingList([f"note-{n}" for n in range(11)])
        with self.assertRaisesRegex(ValueError, "at most 10 strings"):
            HandoffMessage.from_mapping(item)

    def test_rejects_exchange_list_subclass_spoofing_length(self):
        class MisleadingExchange(list):
            def __len__(self):
                return 2

        # A third report must not be ignored when __len__ lies.
        payload = MisleadingExchange([
            record(), record("tester", "pass"), record("tester", "pass"),
        ])
        self.assertEqual(3, len(list(payload)))
        with self.assertRaisesRegex(ValueError, "exchange must be a JSON array"):
            validate_exchange(payload)

    def test_rejects_exchange_list_subclass_with_two_items(self):
        class ExchangeList(list):
            pass

        with self.assertRaisesRegex(ValueError, "exchange must be a JSON array"):
            validate_exchange(ExchangeList([record(), record("tester", "pass")]))

    def test_exact_list_bound_still_accepts_ten(self):
        item = record("tester", "pass")
        item["evidence"] = [f"note-{n}" for n in range(10)]
        self.assertEqual(10, len(HandoffMessage.from_mapping(item).evidence))

    def test_rejects_str_subclasses_that_spoof_identifier_validation(self):
        class SpoofedStr(str):
            def __len__(self):
                return 1

            def __iter__(self):
                return iter("safe")

            def strip(self, *args):
                return self

            def __eq__(self, other):
                return True

            __hash__ = str.__hash__

        for field in ("task_id", "repository", "ref", "actor_role",
                      "status", "artifact", "summary"):
            with self.subTest(field=field):
                item = record()
                item[field] = SpoofedStr(item[field] + "\x00forged")
                with self.assertRaisesRegex(ValueError, "must be a non-empty string"):
                    HandoffMessage.from_mapping(item)

        with self.subTest(field="evidence"):
            item = record("tester", "pass")
            item["evidence"] = [SpoofedStr("observed: PASS\x00forged")]
            with self.assertRaisesRegex(ValueError, "must be a non-empty string"):
                HandoffMessage.from_mapping(item)

    def test_exact_builtin_strings_remain_accepted(self):
        self.assertEqual("tester_reported_pass", validate_exchange(
            [record(), record("tester", "pass")])["state"])


class NoncharacterIdentifierTests(unittest.TestCase):
    def test_unicode_noncharacters_rejected_in_structural_fields(self):
        # These are category Cn, not covered by Cc/Cf/Cs controls.
        for char in ("\ufdd0", "\ufffe", "\U0010ffff"):
            for field in ("task_id", "repository", "ref", "artifact"):
                with self.subTest(field=field, codepoint=hex(ord(char))):
                    item = record()
                    item[field] += char
                    with self.assertRaisesRegex(ValueError, "unsafe identifier characters"):
                        HandoffMessage.from_mapping(item)

    def test_noncharacter_in_evidence_detail_downgrades_trace(self):
        item = record("tester", "pass")
        item["evidence"] = [
            "source: synthetic\ufdd0other", "command: unittest", "observed: PASS",
        ]
        self.assertEqual("ambiguous_unverified", validate_exchange([record(), item])["evidence_trace"])


class PrivateUseIdentifierTests(unittest.TestCase):
    def test_private_use_codepoints_rejected_in_structural_fields(self):
        # Private-use characters may render as invisible or custom glyphs.
        # This is a display guard, not proof of actor authentication.
        for char in ("\ue000", "\U000f0000", "\U0010fffd"):
            for field in ("task_id", "repository", "ref", "artifact"):
                with self.subTest(field=field, codepoint=hex(ord(char))):
                    item = record()
                    item[field] += char
                    with self.assertRaisesRegex(ValueError, "unsafe identifier characters"):
                        HandoffMessage.from_mapping(item)

    def test_private_use_provenance_label_and_detail_stay_unverified(self):
        for char in ("\ue000", "\U000f0000"):
            for location in ("label", "detail"):
                with self.subTest(location=location, codepoint=hex(ord(char))):
                    item = record("tester", "pass")
                    source = ("sou" + char + "rce: synthetic" if location == "label"
                              else "source: synthetic" + char)
                    item["evidence"] = [
                        source, "command: unittest", "observed: synthetic PASS",
                    ]
                    result = validate_exchange([record(), item])
                    self.assertEqual("ambiguous_unverified", result["evidence_trace"])
                    self.assertNotIn("accepted", result)


class NonAsciiSpacingGuardTests(unittest.TestCase):
    def test_non_ascii_internal_spacing_rejected_in_structural_fields(self):
        for char in ("\u00a0", "\u2007", "\u202f"):
            for field in ("task_id", "repository", "ref", "artifact"):
                with self.subTest(field=field, codepoint=hex(ord(char))):
                    item = record()
                    item[field] += "part" + char + "two"
                    with self.assertRaisesRegex(ValueError, "unsafe identifier characters"):
                        HandoffMessage.from_mapping(item)

    def test_non_ascii_spacing_provenance_label_downgraded(self):
        for char in ("\u00a0", "\u2007", "\u202f"):
            with self.subTest(codepoint=hex(ord(char))):
                item = record("tester", "pass")
                item["evidence"] = [
                    "source" + char + ": synthetic A",
                    "command: unittest",
                    "observed: synthetic PASS",
                ]
                result = validate_exchange([record(), item])
                self.assertEqual("ambiguous_unverified", result["evidence_trace"])
                self.assertNotIn("accepted", result)


class HomoglyphProvenanceTests(unittest.TestCase):
    def test_confusable_non_ascii_colon_labels_downgrade_trace(self):
        # Visual lookalikes must not be ignored as unrelated evidence when
        # another clean source/command/observed set is present.
        for label in (
            "s\u043eurce: conflicting fixture",  # Cyrillic o
            "\u0455ource: conflicting fixture",  # Cyrillic dze
            "sourc\u0435: conflicting fixture",  # Cyrillic e
            "c\u043emmand: conflicting command",
            "\u043ebserved: conflicting FAIL",
        ):
            with self.subTest(label=repr(label)):
                tester = record("tester", "pass")
                tester["evidence"] = [
                    "source: synthetic fixture",
                    "command: unittest",
                    "observed: synthetic PASS",
                    label,
                ]
                result = validate_exchange([record(), tester])
                self.assertEqual("ambiguous_unverified", result["evidence_trace"])
                self.assertNotIn("accepted", result)

    def test_confusable_colons_downgrade_conflicting_provenance(self):
        # Colon lookalikes must not hide a second conflicting source, command,
        # or observed statement behind a visually similar delimiter.
        for colon in ("\uff1a", "\ufe55", "\ua789", "\u2236"):
            for label in ("source", "command", "observed"):
                with self.subTest(label=label, colon=hex(ord(colon))):
                    tester = record("tester", "pass")
                    tester["evidence"] = [
                        "source: synthetic fixture",
                        "command: unittest",
                        "observed: synthetic PASS",
                        f"{label}{colon} contradictory synthetic claim",
                    ]
                    result = validate_exchange([record(), tester])
                    self.assertEqual("ambiguous_unverified", result["evidence_trace"])
                    self.assertNotIn("accepted", result)

    def test_unrelated_confusable_colon_notes_remain_compatible(self):
        tester = record("tester", "pass")
        tester["evidence"] = [
            "source: synthetic fixture",
            "command: unittest",
            "observed: synthetic PASS",
            "notes\uff1a synthetic context, not a provenance key",
        ]
        result = validate_exchange([record(), tester])
        self.assertEqual("source_labeled_unverified", result["evidence_trace"])
        self.assertNotIn("accepted", result)

    def test_unrelated_ascii_notes_and_visible_detail_remain_compatible(self):
        tester = record("tester", "pass")
        tester["evidence"] = [
            "source: synthetic fixture",
            "command: unittest",
            "observed: synthetic PASS",
            "notes: Caf\u00e9 is untrusted context",
        ]
        result = validate_exchange([record(), tester])
        self.assertEqual("source_labeled_unverified", result["evidence_trace"])
        self.assertNotIn("accepted", result)
