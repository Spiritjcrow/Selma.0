"""Offline behavioral regression tests for first-run readiness gating.

Mocks subprocess and HTTP; no Android, network, or filesystem writes outside temp.
These are expected to FAIL until wizard runtime-readiness integration lands.
"""
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import selma0_first_run_android_v1 as wizard


class FakeRequest:
    path = "/start"
    headers = {
        "Host": "127.0.0.1:8766",
        "Origin": "http://127.0.0.1:8766",
        "Content-Type": "application/json",
        "X-Selma-Setup-Token": wizard.TOKEN,
    }

    def __init__(self):
        body = json.dumps({"profile": "eco", "scene": "coast",
                           "motion": "reduced"}).encode()
        self.headers = dict(self.headers, **{"Content-Length": str(len(body))})
        self.rfile = io.BytesIO(body)
        self.response = None

    def headers_ok(self):
        return True

    def reply(self, code, payload):
        self.response = (code, payload)


class WizardReadinessBehavior(unittest.TestCase):
    def exercise_start(self, ready):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            runtime = home / "fake_runtime.py"
            runtime.write_text("# mock runtime, never executed\n")
            events = []
            child = mock.Mock()
            child.pid = 12345
            child.poll.return_value = None

            def save(*_):
                events.append("save")
                return {"profile": "eco"}

            def start(*_, **__):
                events.append("launch")
                return child

            def check(*_, **__):
                events.append("ready")
                return ready

            request = FakeRequest()
            with mock.patch.object(wizard, "HOME", home), \
                 mock.patch.object(wizard, "RUNTIME", runtime), \
                 mock.patch.object(wizard, "save_preferences", side_effect=save), \
                 mock.patch.object(wizard.subprocess, "Popen", side_effect=start), \
                 mock.patch.object(wizard, "wait_for_runtime_ready",
                                   side_effect=check, create=True), \
                 mock.patch.object(wizard, "stop_runtime_child", create=True) as stop:
                wizard.WizardHandler.do_POST(request)
                return request.response, events, stop.called

    def test_failed_readiness_never_saves(self):
        response, events, stopped = self.exercise_start(False)
        self.assertEqual(response[0], 503)
        self.assertNotIn("save", events)
        self.assertTrue(stopped)

    def test_success_saves_only_after_readiness(self):
        response, events, stopped = self.exercise_start(True)
        self.assertEqual(response[0], 202)
        self.assertEqual(events, ["launch", "ready", "save"])
        self.assertFalse(stopped)


if __name__ == "__main__":
    unittest.main()
