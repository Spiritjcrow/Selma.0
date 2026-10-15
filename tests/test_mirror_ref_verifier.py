"""Fail-closed contracts for offline destination mirror verification."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / ".migration" / "repository-inventory-2026-10-14.json"
VERIFIER = ROOT / ".migration" / "verify_mirror_refs.py"


class MirrorRefVerifierContracts(unittest.TestCase):
    def run_verifier(self, destination, repository="Androidfixfactory"):
        if not VERIFIER.exists():
            self.fail("mirror verifier is missing")
        with tempfile.TemporaryDirectory() as tmp:
            destination_path = Path(tmp) / "destination.json"
            destination_path.write_text(json.dumps(destination), encoding="utf-8")
            return subprocess.run(
                [
                    sys.executable,
                    str(VERIFIER),
                    str(INVENTORY),
                    repository,
                    str(destination_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

    def test_exact_private_destination_matches(self):
        result = self.run_verifier(
            {
                "visibility": "private",
                "branches": {
                    "main": "4763aea2e291c37a51eaadccfaa58776fb51b77c"
                },
                "tags": {},
            },
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "MATCH")

    def test_changed_missing_and_extra_refs_fail_closed(self):
        result = self.run_verifier(
            {
                "visibility": "private",
                "branches": {
                    "main": "0000000000000000000000000000000000000000",
                    "unexpected": "1111111111111111111111111111111111111111",
                },
                "tags": {"unexpected-tag": "2222222222222222222222222222222222222222"},
            },
            repository="Replika-style-offline-online-AI.Agent-Assistant",
        )
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "MISMATCH")
        self.assertEqual(report["missing_branches"], ["Spiritjcrow-patch-1"])
        self.assertEqual(report["changed_branches"], ["main"])
        self.assertEqual(report["extra_branches"], ["unexpected"])
        self.assertEqual(report["extra_tags"], ["unexpected-tag"])

    def test_non_private_destination_fails_closed(self):
        result = self.run_verifier(
            {
                "visibility": "public",
                "branches": {
                    "main": "4763aea2e291c37a51eaadccfaa58776fb51b77c"
                },
                "tags": {},
            }
        )
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "MISMATCH")
        self.assertEqual(report["visibility"], "public")


if __name__ == "__main__":
    unittest.main()
