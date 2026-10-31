"""Offline synthetic Git fixtures for truthful PR #50 test reporting."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

RUNNER = Path(__file__).resolve().parents[1] / "verify_duo_handoff_offline.py"
spec = importlib.util.spec_from_file_location("duo_skip_runner", RUNNER)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True,
        capture_output=True, text=True,
    ).stdout.strip()


class SkippedTestReportingFixtures(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.name", "Synthetic QA")
        git(self.root, "config", "user.email", "qa@example.invalid")
        for filename in runner.SOURCE_FILES + runner.TEST_FILES:
            path = self.root / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            if filename in runner.TEST_FILES:
                path.write_text(
                    "import unittest\nclass Fixture(unittest.TestCase):\n"
                    "    def test_ok(self): self.assertTrue(True)\n",
                    encoding="utf-8",
                )
            else:
                path.write_text("def local_only(): return True\n", encoding="utf-8")

    def run_fixture(self):
        git(self.root, "add", ".")
        git(self.root, "commit", "-qm", "synthetic pinned source")
        return runner.verify(self.root, git(self.root, "rev-parse", "HEAD"), 20)

    def test_all_skipped_does_not_claim_pass(self):
        for filename in runner.TEST_FILES:
            (self.root / filename).write_text(
                "import unittest\nclass Fixture(unittest.TestCase):\n"
                "    @unittest.skip('synthetic')\n"
                "    def test_skipped(self): pass\n",
                encoding="utf-8",
            )
        report, code = self.run_fixture()
        self.assertEqual(code, 2, report)
        self.assertEqual(report["tests"], "INCOMPLETE")
        self.assertEqual(report["state"], "BLOCKED")
        self.assertEqual(report["test_methods_reported"], 4)
        self.assertEqual(report["test_methods_skipped"], 4)

    def test_partially_skipped_does_not_claim_full_pass(self):
        (self.root / runner.TEST_FILES[0]).write_text(
            "import unittest\nclass Fixture(unittest.TestCase):\n"
            "    @unittest.skip('synthetic')\n"
            "    def test_skipped(self): pass\n",
            encoding="utf-8",
        )
        report, code = self.run_fixture()
        self.assertEqual(code, 2, report)
        self.assertEqual(report["tests"], "INCOMPLETE")
        self.assertEqual(report["test_methods_skipped"], 1)

    def test_no_skips_keeps_review_only_pass(self):
        report, code = self.run_fixture()
        self.assertEqual(code, 0, report)
        self.assertEqual(report["tests"], "PASS")
        self.assertEqual(report["state"], "REVIEW")
        self.assertEqual(report["test_methods_skipped"], 0)
        self.assertEqual(report["independent_tester"], "NOT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
