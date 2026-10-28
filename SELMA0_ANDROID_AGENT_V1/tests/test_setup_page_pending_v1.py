"""Offline, portable contract checks for truthful first-run launch messaging.

These are source/UI contract checks, not a browser, Android, or HTTP readiness test.
"""
import inspect
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import selma0_first_run_android_v1 as setup


class TestFirstRunPendingCopy(unittest.TestCase):
    def test_pending_response_requires_explicit_unverified_ui(self):
        page = setup.PAGE
        self.assertIn("j.status==='launch_pending' && j.ready===false", page)
        self.assertIn("Selma runtime launch pending; readiness NOT verified.", page)
        self.assertIn("Try Selma chat after startup", page)
        self.assertNotIn(">Open Selma chat</a>", page)

    def test_unknown_success_response_does_not_claim_readiness(self):
        page = setup.PAGE
        self.assertIn("Unexpected launch response; readiness NOT verified.", page)
        source = inspect.getsource(setup.WizardHandler.do_POST)
        self.assertIn('"ready": False', source)
        self.assertIn('"status": "launch_pending"', source)


    def test_timeout_does_not_leave_stale_pending_message(self):
        page = setup.PAGE
        self.assertIn("if(++attempts>60)", page)
        self.assertIn("Launch remains unverified after two minutes.", page)
        self.assertIn("Check the Termux startup log and existing launcher before any retry", page)
        self.assertIn("clearInterval(watcher);return;", page)


if __name__ == "__main__":
    unittest.main()
