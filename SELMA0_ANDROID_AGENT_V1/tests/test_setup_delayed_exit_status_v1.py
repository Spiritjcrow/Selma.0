"""Synthetic late-exit observability tests. No Android, network or model."""
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import selma0_first_run_android_v1 as setup


class DelayedExitObservationTests(unittest.TestCase):
    def get_status(self):
        handler = object.__new__(setup.WizardHandler)
        handler.path = "/launch-status"
        handler.headers = {"Host": "127.0.0.1:8766"}
        responses = []
        handler.reply = lambda code, payload: responses.append((code, payload))
        handler.do_GET()
        self.assertEqual(len(responses), 1)
        return responses[0]

    def test_untracked_after_wizard_restart_is_not_ready(self):
        with mock.patch.object(setup, "LAUNCHED_CHILD", None):
            self.assertEqual((200, {"status": "untracked", "ready": False}),
                             self.get_status())

    def test_live_child_is_pending_not_ready(self):
        child = mock.Mock()
        child.poll.return_value = None
        with mock.patch.object(setup, "LAUNCHED_CHILD", child):
            self.assertEqual((200, {"status": "launch_pending", "ready": False}),
                             self.get_status())

    def test_delayed_child_exit_is_detected_without_auto_retry(self):
        child = mock.Mock()
        child.poll.return_value = 7
        with mock.patch.object(setup, "LAUNCHED_CHILD", child):
            self.assertEqual((200, {"status": "exited_after_launch", "ready": False}),
                             self.get_status())
        child.terminate.assert_not_called()
        child.kill.assert_not_called()

    def test_successful_post_tracks_child_but_never_claims_ready(self):
        options = {"profile": "eco", "scene": "coast", "motion": "reduced"}
        raw = json.dumps(options).encode("utf-8")
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            prefs = home / "selma0_setup_v1.json"
            handler = object.__new__(setup.WizardHandler)
            handler.path = "/start"
            handler.headers = {
                "Host": "127.0.0.1:8766",
                "Content-Type": "application/json",
                "Content-Length": str(len(raw)),
                "X-Selma-Setup-Token": setup.TOKEN,
            }
            handler.rfile = io.BytesIO(raw)
            replies = []
            handler.reply = lambda code, payload: replies.append((code, payload))
            real_save = setup.save_preferences
            with mock.patch.object(setup, "HOME", home), \
                 mock.patch.object(setup, "PREFS", prefs), \
                 mock.patch.object(setup, "RUNTIME", Path(__file__)), \
                 mock.patch.object(setup, "LAUNCHED_CHILD", None), \
                 mock.patch.object(setup, "save_preferences",
                                   side_effect=lambda v: real_save(v, prefs)), \
                 mock.patch.object(setup.subprocess, "Popen") as spawn:
                spawn.return_value.wait.side_effect = subprocess.TimeoutExpired("synthetic", 1.5)
                handler.do_POST()
                self.assertEqual(replies[0][0], 202)
                self.assertIs(replies[0][1]["ready"], False)
                self.assertIs(setup.LAUNCHED_CHILD, spawn.return_value)
                self.assertEqual((200, {"status": "launch_pending", "ready": False}),
                                 self.get_status())
                self.assertTrue(prefs.is_file())


if __name__ == "__main__":
    unittest.main()
