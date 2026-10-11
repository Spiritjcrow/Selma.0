"""Fail-closed source contracts for first-run readiness integration.

Portable tests: no Android device, model server, network, or root required.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FirstRunRuntimeGateContract(unittest.TestCase):
    def test_wizard_uses_pid_bound_readiness(self):
        wizard = (ROOT / "selma0_first_run_android_v1.py").read_text(encoding="utf-8")
        self.assertIn("from selma0_first_run_ready_v1 import", wizard)
        self.assertIn("wait_for_runtime_ready(child", wizard)

    def test_preferences_saved_only_after_readiness(self):
        wizard = (ROOT / "selma0_first_run_android_v1.py").read_text(encoding="utf-8")
        post = wizard.split("    def do_POST(self):", 1)[1].split("\ndef main():", 1)[0]
        self.assertLess(post.index("wait_for_runtime_ready(child"), post.index("save_preferences(opts)"))
        self.assertIn("stop_runtime_child(child)", post)
        self.assertIn("configuration was not saved", post)

    def test_command_core_exposes_own_pid(self):
        core = (ROOT / "selma0_runtime_command_core_android_v1.py").read_text(encoding="utf-8")
        self.assertIn('status["runtime_pid_v1"] = os.getpid()', core)

    def test_ready_helper_requires_child_pid(self):
        helper = (ROOT / "selma0_first_run_ready_v1.py").read_text(encoding="utf-8")
        self.assertIn('data["runtime_pid_v1"] == process.pid', helper)
        self.assertIn('connection = http.client.HTTPConnection("127.0.0.1"', helper)


if __name__ == "__main__":
    unittest.main()
