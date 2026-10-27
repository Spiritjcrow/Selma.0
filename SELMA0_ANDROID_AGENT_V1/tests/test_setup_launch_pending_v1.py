"""Offline contract regression: process survival does not prove Selma runtime readiness."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import selma0_first_run_android_v1 as setup


class TestLaunchPending(unittest.TestCase):
    @staticmethod
    def request(options):
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
        replies = []
        handler.reply = lambda code, data: replies.append((code, data))
        return handler, replies

    def test_mocked_live_child_is_explicitly_not_ready(self):
        options = {"profile": "eco", "scene": "coast", "motion": "reduced"}
        with tempfile.TemporaryDirectory() as temp:
            prefs = Path(temp) / "selma0_setup_v1.json"
            real_save = setup.save_preferences
            with mock.patch.object(setup, "HOME", Path(temp)), \
                 mock.patch.object(setup, "PREFS", prefs), \
                 mock.patch.object(setup, "RUNTIME", Path(__file__)), \
                 mock.patch.object(setup, "save_preferences", side_effect=lambda value: real_save(value, prefs)), \
                 mock.patch.object(setup.subprocess, "Popen") as spawn:
                spawn.return_value.wait.side_effect = subprocess.TimeoutExpired("synthetic", 1.5)
                handler, replies = self.request(options)
                handler.do_POST()
            self.assertEqual(replies[0][0], 202)
            self.assertIs(replies[0][1]["ready"], False)
            self.assertEqual(replies[0][1]["status"], "launch_pending")
            self.assertTrue(prefs.is_file())
            spawn.assert_called_once()

    def test_real_sleeping_child_is_not_mistaken_for_ready_runtime(self):
        options = {"profile": "eco", "scene": "forest", "motion": "normal"}
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            child_script = home / "synthetic_sleep.py"
            child_script.write_text("import time\ntime.sleep(10)\n", encoding="utf-8")
            prefs = home / "selma0_setup_v1.json"
            real_save = setup.save_preferences
            real_spawn = subprocess.Popen
            started = []

            def capture_spawn(*args, **kwargs):
                proc = real_spawn(*args, **kwargs)
                started.append(proc)
                return proc

            try:
                with mock.patch.object(setup, "HOME", home), \
                     mock.patch.object(setup, "PREFS", prefs), \
                     mock.patch.object(setup, "RUNTIME", child_script), \
                     mock.patch.object(setup, "save_preferences", side_effect=lambda value: real_save(value, prefs)), \
                     mock.patch.object(setup.subprocess, "Popen", side_effect=capture_spawn):
                    handler, replies = self.request(options)
                    handler.do_POST()
                self.assertEqual(replies[0][0], 202)
                self.assertIs(replies[0][1]["ready"], False)
                self.assertEqual(replies[0][1]["status"], "launch_pending")
                self.assertTrue(prefs.is_file())
                self.assertEqual(len(started), 1)
                self.assertIsNone(started[0].poll())
            finally:
                for child in started:
                    if child.poll() is None:
                        child.terminate()
                    try:
                        child.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=2)


if __name__ == "__main__":
    unittest.main()
