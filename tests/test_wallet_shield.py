"""Portable, offline WalletShield security regression tests."""
import copy
import json
import socket
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from core.wallet_shield import (
    append_audit, assess, export_report, validate_case, verify_audit,
)

D = "a" * 64


class WalletShieldTests(unittest.TestCase):
    def case(self, observations=None):
        return {"case_id": "case_0001", "observations": observations or []}

    def test_default_is_not_claimed_safe_or_scanned(self):
        result = assess(self.case())
        self.assertEqual("no_reported_indicators", result["status"])
        self.assertFalse(result["hardware_scanned"])
        self.assertFalse(result["network_used"])
        self.assertFalse(result["external_report_sent"])
        self.assertIn("user_supplied_metadata_only", result["assessment_basis"])

    def test_vendor_attestation_fail_needs_independent_verification(self):
        observation = {
            "kind": "vendor_attestation", "result": "fail",
            "method": "official_vendor_client", "evidence_sha256": D,
        }
        result = assess(self.case([observation]))
        self.assertEqual("urgent_review", result["status"])
        self.assertFalse(result["signals"][0]["independently_verified"])

    def test_unqualified_radio_report_cannot_claim_confirmed_implant(self):
        result = assess(self.case([{"kind": "rf_survey", "result": "fail"}]))
        self.assertEqual("review", result["status"])
        self.assertIn("unrelated emitters", result["signals"][0]["reason"])
        self.assertFalse(result["hardware_scanned"])

    def test_qualified_rf_is_still_only_an_urgent_review(self):
        result = assess(self.case([{
            "kind": "rf_survey", "result": "fail",
            "method": "calibrated_external_receiver", "evidence_sha256": D,
        }]))
        self.assertEqual("urgent_review", result["status"])
        self.assertFalse(result["signals"][0]["independently_verified"])

    def test_untrusted_reseller_is_not_a_criminal_finding(self):
        result = assess(self.case([{
            "kind": "supply_chain", "result": "fail",
            "method": "documented_receipt", "evidence_sha256": D,
        }]))
        self.assertEqual("review", result["status"])
        self.assertIn("not proof", result["signals"][0]["reason"])

    def test_rejects_secrets_and_unbounded_free_text(self):
        examples = [
            {"seed_phrase": "word " * 24},
            {"device_id": "my private address"},
            {"raw_rf_capture": "sensitive"},
        ]
        for extra in examples:
            with self.subTest(extra=extra):
                case = self.case([{"kind": "rf_survey", "result": "fail", **extra}])
                with self.assertRaises(ValueError):
                    validate_case(case)
        for extra in ("seed_phrase", "wallet_address", "private_key"):
            payload = self.case()
            payload[extra] = "SECRET"
            with self.assertRaises(ValueError):
                assess(payload)

    def test_rejects_forged_methods_and_digest(self):
        with self.assertRaises(ValueError):
            assess(self.case([{"kind": "vendor_attestation", "result": "fail",
                               "method": "calibrated_external_receiver"}]))
        with self.assertRaises(ValueError):
            assess(self.case([{"kind": "rf_survey", "result": "fail",
                               "evidence_sha256": "bad"}]))

    def test_offline_no_network_access(self):
        with (
            patch.object(socket, "create_connection", side_effect=AssertionError("network")),
            patch.object(urllib.request, "urlopen", side_effect=AssertionError("network")),
        ):
            assess(self.case([{"kind": "physical_inspection", "result": "unknown"}]))

    def test_audit_linkage_catches_modification(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            first = assess(self.case())
            second = assess(self.case([{"kind": "supply_chain", "result": "fail"}]))
            append_audit(path, first)
            append_audit(path, second)
            self.assertEqual(2, verify_audit(path)["entries"])
            lines = path.read_text(encoding="utf-8").splitlines()
            tampered = json.loads(lines[0])
            tampered["assessment"]["case_id"] = "case_7777"
            lines[0] = json.dumps(tampered)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            self.assertFalse(verify_audit(path)["valid"])
            with self.assertRaises(ValueError):
                append_audit(path, first)

    def test_exports_require_explicit_approval(self):
        result = assess(self.case())
        with self.assertRaises(PermissionError):
            export_report(result)
        report = export_report(result, owner_approved=True)
        self.assertTrue(report["requires_independent_review"])
        self.assertTrue(report["report_not_transmitted"])

    def test_crafted_assessment_cannot_sneak_secrets_into_audit_or_export(self):
        result = assess(self.case())
        crafted = copy.deepcopy(result)
        crafted["seed_phrase"] = "SECRET"
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                append_audit(Path(tmp) / "log.jsonl", crafted)
            with self.assertRaises(ValueError):
                export_report(crafted, owner_approved=True)


if __name__ == "__main__":
    unittest.main()
