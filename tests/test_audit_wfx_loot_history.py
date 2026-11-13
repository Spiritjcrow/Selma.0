"""Isolated local Git fixture tests; no network, credentials, or CI needed."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "tools" / "audit_wfx_loot_history.py"
spec = importlib.util.spec_from_file_location("audit_wfx_loot_history", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AuditWfxLootTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Fixture")
        (self.repo / "README.md").write_text("Safe fixture\n", encoding="utf-8")
        self.commit("baseline")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True,
                              text=True, check=True).stdout

    def commit(self, title):
        self.git("add", "-A")
        self.git("-c", "commit.gpgsign=false", "commit", "-qm", title)

    def scan(self):
        return module.scan(self.repo, "2000-01-01T00:00:00Z")

    def test_clean_repo_does_not_claim_security(self):
        result = self.scan()
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["assessment"], "NO_MATCHES_IN_SCANNED_REACHABLE_HISTORY")
        self.assertIn("does not prove", result["limitations"][-1])

    def test_probe_branch_detected(self):
        self.git("branch", "wfx-docs")
        self.assertTrue(any(f["type"] == "suspicious_branch_name" for f in self.scan()["findings"]))

    def test_suspicious_commit_and_installer_filename_detected(self):
        (self.repo / ".ci-abc123.sh").write_text("# harmless fixture\n", encoding="utf-8")
        self.commit("ci: refresh build cache")
        types = {f["type"] for f in self.scan()["findings"]}
        self.assertIn("suspicious_commit_subject", types)
        self.assertIn("suspicious_historical_path", types)

    def test_content_marker_only_reports_path(self):
        (self.repo / "payload.txt").write_text("WF_CALLBACK=placeholder-only\n", encoding="utf-8")
        self.commit("fixture marker")
        marks = [f for f in self.scan()["findings"] if f["type"] == "current_file_content_marker"]
        self.assertEqual(marks, [{"type": "current_file_content_marker", "path": "payload.txt"}])

    def test_deleted_file_detected_from_history(self):
        (self.repo / ".ci-abc123.sh").write_text("harmless fixture\n", encoding="utf-8")
        self.commit("initial fixture")
        (self.repo / ".ci-abc123.sh").unlink()
        self.commit("remove fixture")
        self.assertTrue(any(f["type"] == "suspicious_historical_path" for f in self.scan()["findings"]))


if __name__ == "__main__":
    unittest.main()
