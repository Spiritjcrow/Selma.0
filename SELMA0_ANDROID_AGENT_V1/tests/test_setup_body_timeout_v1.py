"""Synthetic regressions for stalled first-run POST request bodies.

No real socket, process, Android device or external network is used.
"""
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import selma0_first_run_android_v1 as setup


class TestSetupBodyTimeout(unittest.TestCase):
    @staticmethod
    def make_handler():
        options = {"profile": "eco", "scene": "coast", "motion": "reduced"}
        body = json.dumps(options).encode("utf-8")
        handler = object.__new__(setup.WizardHandler)
        handler.path = "/start"
        handler.headers = {
            "Host": "127.0.0.1:8766",
            "X-Selma-Setup-Token": setup.TOKEN,
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
        }
        handler.connection = mock.Mock()
        handler.rfile = io.BytesIO(body)
        replies = []
        handler.reply = lambda code, payload: replies.append((code, payload))
        return handler, replies

    def test_stalled_body_returns_408_without_persisting_or_spawning(self):
        handler, replies = self.make_handler()
        handler.rfile = mock.Mock()
        handler.rfile.read.side_effect = TimeoutError("SYNTHETIC_CLIENT_PATH_91")
        with mock.patch.object(setup, "save_preferences") as save, \\
             mock.patch.object(setup.subprocess, "Popen") as spawn:
            handler.do_POST()
        self.assertEqual(replies, [(408, {"error": "request body timed out"})])
        handler.connection.settimeout.assert_called_once_with(5.0)
        save.assert_not_called()
        spawn.assert_not_called()
        self.assertNotIn("SYNTHETIC_CLIENT_PATH_91", str(replies))

    def test_complete_body_sets_timeout_and_reaches_runtime_preflight(self):
        handler, replies = self.make_handler()
        with tempfile.TemporaryDirectory() as temp, \\
             mock.patch.object(setup, "RUNTIME", Path(temp) / "missing.py"), \\
             mock.patch.object(setup, "save_preferences") as save, \\
             mock.patch.object(setup.subprocess, "Popen") as spawn:
            handler.do_POST()
        self.assertEqual(replies[0][0], 503)
        self.assertIn("runtime script is missing", replies[0][1]["error"])
        handler.connection.settimeout.assert_called_once_with(5.0)
        save.assert_not_called()
        spawn.assert_not_called()

    def test_short_body_is_not_confused_with_timeout(self):
        handler, replies = self.make_handler()
        handler.rfile = io.BytesIO(b"{}")
        with mock.patch.object(setup, "save_preferences") as save, \\
             mock.patch.object(setup.subprocess, "Popen") as spawn:
            handler.do_POST()
        self.assertEqual(replies, [(400, {"error": "incomplete request body"})])
        handler.connection.settimeout.assert_called_once_with(5.0)
        save.assert_not_called()
        spawn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
