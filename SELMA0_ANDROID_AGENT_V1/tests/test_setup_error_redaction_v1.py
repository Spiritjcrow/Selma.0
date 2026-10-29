"""Offline synthetic regressions: setup errors must not disclose local paths."""

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import selma0_first_run_android_v1 as setup


class TestSetupErrorRedaction(unittest.TestCase):
    @staticmethod
    def handler_for():
        options = {"profile": "eco", "scene": "coast", "motion": "reduced"}
        raw = json.dumps(options).encode("utf-8")
        handler = object.__new__(setup.WizardHandler)
        handler.path = "/start"
        handler.headers = {
            "Host": "127.0.0.1:8766",
            "X-Selma-Setup-Token": setup.TOKEN,
            "Content-Type": "application/json",
            "Content-Length": str(len(raw)),
        }
        handler.rfile = io.BytesIO(raw)
        responses = []
        handler.reply = lambda code, payload: responses.append((code, payload))
        return handler, responses, options

    def test_spawn_error_redacts_local_path_and_rolls_back(self):
        marker = "SYNTHETIC_PRIVATE_PATH_SPAWN_83"
        with tempfile.TemporaryDirectory() as tmp:
            prefs = Path(tmp) / "prefs.json"
            real_save = setup.save_preferences
            handler, responses, _ = self.handler_for()
            with mock.patch.object(setup, "HOME", Path(tmp)), \
                 mock.patch.object(setup, "PREFS", prefs), \
                 mock.patch.object(setup, "RUNTIME", Path(__file__)), \
                 mock.patch.object(setup, "save_preferences", side_effect=lambda value: real_save(value, prefs)), \
                 mock.patch.object(setup.subprocess, "Popen", side_effect=OSError(f"[Errno 2] {marker}")):
                handler.do_POST()
            self.assertEqual(responses[0][0], 503)
            self.assertIn("incomplete", responses[0][1]["error"])
            self.assertNotIn(marker, json.dumps(responses))
            self.assertFalse(prefs.exists())

    def test_preference_write_error_redacts_local_path(self):
        marker = "SYNTHETIC_PRIVATE_PATH_PREFS_83"
        with tempfile.TemporaryDirectory() as tmp:
            handler, responses, _ = self.handler_for()
            with mock.patch.object(setup, "PREFS", Path(tmp) / "prefs.json"), \
                 mock.patch.object(setup, "RUNTIME", Path(__file__)), \
                 mock.patch.object(setup, "save_preferences", side_effect=OSError(f"[Errno 13] {marker}")), \
                 mock.patch.object(setup.subprocess, "Popen") as spawn:
                handler.do_POST()
            self.assertEqual(responses[0][0], 503)
            self.assertNotIn(marker, json.dumps(responses))
            spawn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
