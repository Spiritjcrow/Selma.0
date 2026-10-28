"""Deterministic offline boundary regressions for PR #50 handoff validation.

Synthetic records only; no network, device, authentication or CI assertions.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest

from core.duo_handoff import HandoffMessage, validate_exchange
from tests.test_duo_handoff import record

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "tools" / "selma_duo_validate.py"


class HandoffBoundaryMatrixTests(unittest.TestCase):
    def run_cli(self, payload: bytes):
        process = subprocess.run(
            [sys.executable, str(CLI)], input=payload, cwd=ROOT,
            capture_output=True, timeout=10, check=False,
        )
        self.assertFalse(process.stderr, process.stderr.decode("utf-8", "replace"))
        return process.returncode, json.loads(process.stdout)

    def test_all_structural_identifiers_reject_invisible_modifiers(self):
        for field in ("task_id", "repository", "ref", "actor_role", "status", "artifact"):
            for modifier in ("\u200b", "\u034f", "\u202e", "\ufe0f"):
                with self.subTest(field=field, modifier=hex(ord(modifier))):
                    message = record()
                    message[field] += modifier
                    with self.assertRaises(ValueError):
                        HandoffMessage.from_mapping(message)

    def test_every_shared_identity_field_must_match_exactly(self):
        for field in ("task_id", "repository", "ref", "artifact"):
            with self.subTest(field=field):
                tester = record("tester", "pass")
                tester[field] += "-other"
                with self.assertRaisesRegex(ValueError, f"tester {field} does not match"):
                    validate_exchange([record(), tester])

    def test_escaped_duplicate_json_key_fails_closed(self):
        # JSON escapes are decoded before duplicate-key detection.
        raw = json.dumps(record()).replace('"task_id":', '"ta\\u0073k_id": "shadow", "task_id":', 1)
        code, result = self.run_cli(("[" + raw + "]").encode())
        self.assertEqual(2, code)
        self.assertFalse(result["ok"])
        self.assertIn("duplicate JSON object key", result["error"])

    def test_nonfinite_json_evidence_is_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value):
                raw = json.dumps(record("tester", "pass")).replace(
                    '"evidence": ["Manual steps and observed result"]',
                    f'"evidence": [{value}]', 1,
                )
                code, result = self.run_cli(("[" + json.dumps(record()) + "," + raw + "]").encode())
                self.assertEqual(2, code)
                self.assertFalse(result["ok"])

    def test_utf8_bom_is_rejected_without_traceback(self):
        code, result = self.run_cli(b"\xef\xbb\xbf" + json.dumps([record()]).encode())
        self.assertEqual(2, code)
        self.assertFalse(result["ok"])

    def test_untrusted_tester_pass_never_becomes_acceptance(self):
        tester = record("tester", "pass")
        tester["evidence"] = ["source: synthetic", "command: unittest", "observed: PASS"]
        result = validate_exchange([record(), tester])
        self.assertEqual("tester_reported_pass", result["state"])
        self.assertEqual("source_labeled_unverified", result["evidence_trace"])
        self.assertNotIn("accepted", result)


if __name__ == "__main__":
    unittest.main()
