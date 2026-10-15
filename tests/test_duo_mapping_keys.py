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
