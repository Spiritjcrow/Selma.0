"""Offline subprocess regressions for the v0.1 handoff CLI (no device/network)."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "tools" / "selma_duo_validate.py"
LIMIT = 1_048_576


def message(role="builder", status="submitted"):
    return {
        "schema_version": 1,
        "task_id": "SELMA49-CLI",
        "repository": "Spiritjcrow/Selma.0",
        "ref": "feature/selmaos-dual-agent-handoff-20261017",
        "actor_role": role,
        "status": status,
        "artifact": "commit:synthetic-fixture",
        "evidence": [] if role == "builder" else ["Synthetic test observation"],
        "summary": "Offline fixture, not device evidence",
    }


class DuoCliRegressionTests(unittest.TestCase):
    def run_cli(self, raw, path=None):
        command = [sys.executable, str(CLI)]
        if path is not None:
            command.append(str(path))
        result = subprocess.run(
            command, input=raw if path is None else None,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=10, cwd=ROOT, check=False,
        )
        self.assertEqual(b"", result.stderr, result.stderr.decode("utf-8", "replace"))
        return result.returncode, json.loads(result.stdout.decode("utf-8"))

    def test_builder_stays_pending(self):
        code, result = self.run_cli(json.dumps([message()]).encode())
        self.assertEqual((0, True, "awaiting_tester"),
                         (code, result["ok"], result["state"]))

    def test_tester_status_is_reported_not_authenticated(self):
        for status in ("pass", "fail", "blocked"):
            with self.subTest(status=status):
                data = [message(), message("tester", status)]
                code, result = self.run_cli(json.dumps(data).encode())
                self.assertEqual((0, f"tester_reported_{status}"),
                                 (code, result["state"]))

    def test_mismatched_ref_fails_closed(self):
        tester = message("tester", "pass")
        tester["ref"] = "other-branch"
        code, result = self.run_cli(json.dumps([message(), tester]).encode())
        self.assertEqual(2, code)
        self.assertFalse(result["ok"])
        self.assertIn("ref does not match", result["error"])

    def test_duplicate_top_level_key_rejected(self):
        raw = json.dumps(message()).replace('"task_id":', '"task_id":"shadow", "task_id":', 1)
        code, result = self.run_cli(("[" + raw + "]").encode())
        self.assertEqual(2, code)
        self.assertIn("duplicate JSON object key", result["error"])

    def test_duplicate_nested_key_rejected(self):
        raw = json.dumps(message()).replace('"evidence": []',
                                            '"evidence": [{"a": 1, "a": 2}]', 1)
        code, result = self.run_cli(("[" + raw + "]").encode())
        self.assertEqual(2, code)
        self.assertIn("duplicate JSON object key", result["error"])

    def test_oversized_stdin_rejected_before_parsing(self):
        code, result = self.run_cli(b"[" + b" " * LIMIT + b"]")
        self.assertEqual(2, code)
        self.assertIn("exceeds maximum", result["error"])

    def test_invalid_utf8_rejected_without_traceback(self):
        code, result = self.run_cli(b"[\xff]")
        self.assertEqual(2, code)
        self.assertFalse(result["ok"])

    def test_malformed_json_rejected(self):
        code, result = self.run_cli(b"[{]")
        self.assertEqual(2, code)
        self.assertFalse(result["ok"])

    def test_file_mode_matches_stdin(self):
        raw = json.dumps([message()]).encode()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "handoff.json"
            path.write_bytes(raw)
            self.assertEqual(self.run_cli(raw), self.run_cli(None, path))

    def test_empty_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.json"
            path.write_bytes(b"")
            code, result = self.run_cli(None, path)
        self.assertEqual(2, code)
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
