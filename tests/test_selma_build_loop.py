"""Isolated negative tests for the bounded local Selma build loop."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parent.parent / "tools" / "selma_build_loop.py"
spec = importlib.util.spec_from_file_location("selma_build_loop", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class BuildLoopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run_git("init", "-q")
        self.run_git("config", "user.email", "test@example.invalid")
        self.run_git("config", "user.name", "test")
        (self.root / "tools").mkdir()
        self.script = self.root / "tools" / "ci_free_local.py"
        self.script.write_text("import sys\nsys.exit(0)\n")
        self.run_git("add", ".")
        self.run_git("commit", "-qm", "fixture")

    def run_git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, check=True,
                              capture_output=True, text=True).stdout.strip()

    def test_clean_revision_is_sha(self):
        self.assertEqual(self.run_git("rev-parse", "HEAD"), mod.clean_revision(self.root))

    def test_dirty_checkout_rejected(self):
        (self.root / "changed.txt").write_text("uncommitted")
        with self.assertRaisesRegex(RuntimeError, "dirty"):
            mod.clean_revision(self.root)

    def test_clean_one_shot_executes(self):
        self.assertEqual(0, mod.loop(self.root))
        self.assertFalse(mod.git_control_file(self.root, "SELMA_BUILD_LOCK").exists())

    def test_validator_nonzero_rejected(self):
        self.script.write_text("import sys\nsys.exit(5)\n")
        self.run_git("add", ".")
        self.run_git("commit", "-qm", "failfixture")
        self.assertEqual(5, mod.loop(self.root))

    def test_partial_result_not_pass(self):
        self.script.write_text("import sys\nsys.exit(2)\n")
        self.run_git("add", ".")
        self.run_git("commit", "-qm", "partialfixture")
        self.assertEqual(2, mod.loop(self.root))

    def test_kill_switch_prevents_spawn(self):
        stop = mod.git_control_file(self.root, "SELMA_BUILD_STOP")
        stop.touch()
        with self.assertRaisesRegex(RuntimeError, "kill switch"):
            mod.loop(self.root)

    def test_existing_lock_prevents_concurrency(self):
        lock = mod.git_control_file(self.root, "SELMA_BUILD_LOCK")
        lock.write_text("owned by another process")
        with self.assertRaisesRegex(RuntimeError, "another loop lock"):
            mod.loop(self.root)
        self.assertTrue(lock.exists())

    def test_invalid_limits_fail(self):
        for kwargs in ({"max_runs": 0}, {"max_minutes": 0}, {"interval": 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                mod.loop(self.root, **kwargs)

    def test_wrong_repository_root(self):
        nested = self.root / "nested"
        nested.mkdir()
        with self.assertRaisesRegex(RuntimeError, "wrong Git checkout"):
            mod.clean_revision(nested)

    def test_source_mutated_during_execution_fails_closed(self):
        self.script.write_text("from pathlib import Path\nPath('changed.txt').write_text('change')\n")
        self.run_git("add", ".")
        self.run_git("commit", "-qm", "mutationfixture")
        with self.assertRaisesRegex(RuntimeError, "dirty"):
            mod.loop(self.root)

    def test_stop_terminates_active_validation(self):
        self.script.write_text("import time\ntime.sleep(5)\n")
        self.run_git("add", ".")
        self.run_git("commit", "-qm", "slowfixture")
        import threading
        stopper = mod.git_control_file(self.root, "SELMA_BUILD_STOP")
        timer = threading.Timer(0.6, stopper.touch)
        timer.start()
        try:
            self.assertEqual(130, mod.loop(self.root))
        finally:
            timer.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
