import sys
import io
import json
from unittest import mock
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import selma0_first_run_android_v1 as setup


class TestSetup(unittest.TestCase):
    def test_recommendation_unknown_fails_safe(self):
        self.assertEqual(setup.recommended_profile({"available_ram_mb": None}), "eco")
        self.assertEqual(setup.recommended_profile({"available_ram_mb": 2048}), "eco")
        self.assertEqual(setup.recommended_profile({"available_ram_mb": 4000}), "balanced")

    def test_allowlist_and_local_only(self):
        prefs = setup.checked_preferences({"profile": "eco", "scene": "coast", "motion": "reduced"})
        self.assertFalse(prefs["autogrant_permissions"])
        self.assertFalse(prefs["model_installed"])
        self.assertEqual(prefs["network"], "local_only")
        with self.assertRaises(ValueError):
            setup.checked_preferences({"profile": "eco", "scene": "coast", "motion": "normal", "api_key": "secret"})
        with self.assertRaises(ValueError):
            setup.checked_preferences({"profile": "ultra", "scene": "coast", "motion": "normal"})

    def test_permissions_on_disk(self):
        with tempfile.TemporaryDirectory() as t:
            file = Path(t) / "prefs.json"
            setup.save_preferences({"profile": "eco", "scene": "forest", "motion": "normal"}, file)
            self.assertEqual(file.stat().st_mode & 0o777, 0o600)
            self.assertEqual(__import__("json").loads(file.read_text())["scene"], "forest")


    def test_existing_fixed_temp_symlink_cannot_overwrite_other_file(self):
        # Source-only regression; never touches an external path or device.
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            victim = root / "unrelated.txt"
            victim.write_text("unchanged", encoding="utf-8")
            fixed_temp = root / "prefs.json.tmp"
            try:
                fixed_temp.symlink_to(victim)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable on this test host")
            prefs = root / "prefs.json"
            setup.save_preferences({"profile": "eco", "scene": "forest", "motion": "normal"}, prefs)
            self.assertEqual(victim.read_text(encoding="utf-8"), "unchanged")
            self.assertEqual(json.loads(prefs.read_text(encoding="utf-8"))["scene"], "forest")
            self.assertEqual(prefs.stat().st_mode & 0o777, 0o600)
            self.assertTrue(fixed_temp.is_symlink())
            self.assertFalse(list(root.glob(".prefs.json.*.tmp")))

    def test_replace_failure_preserves_previous_preferences_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as t:
            prefs = Path(t) / "prefs.json"
            prefs.write_text("prior", encoding="utf-8")
            with mock.patch.object(setup.os, "replace", side_effect=OSError("synthetic replace failure")):
                with self.assertRaises(OSError):
                    setup.save_preferences({"profile": "eco", "scene": "coast", "motion": "reduced"}, prefs)
            self.assertEqual(prefs.read_text(encoding="utf-8"), "prior")
            self.assertFalse(list(Path(t).glob(".prefs.json.*.tmp")))

    def test_repeated_atomic_saves_preserve_private_file_mode(self):
        with tempfile.TemporaryDirectory() as t:
            prefs = Path(t) / "prefs.json"
            for scene in ("coast", "city"):
                setup.save_preferences({"profile": "eco", "scene": scene, "motion": "reduced"}, prefs)
            self.assertEqual(prefs.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(prefs.read_text(encoding="utf-8"))["scene"], "city")


class TestStartRecovery(unittest.TestCase):
    """Offline HTTP-handler simulation; no real process, port, or Android device."""

    @staticmethod
    def handler_for(options):
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
        return handler, responses

    def test_missing_runtime_keeps_first_run_incomplete(self):
        options = {"profile": "eco", "scene": "coast", "motion": "reduced"}
        handler, responses = self.handler_for(options)
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(setup, "RUNTIME", Path(temp) / "missing_runtime.py"), \
                 mock.patch.object(setup, "save_preferences") as save:
                handler.do_POST()
        self.assertEqual(responses[0][0], 503)
        self.assertIn("incomplete", responses[0][1]["error"])
        save.assert_not_called()

    def test_retry_after_restoring_runtime_can_launch(self):
        options = {"profile": "eco", "scene": "forest", "motion": "normal"}
        handler, responses = self.handler_for(options)
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(setup, "RUNTIME", Path(__file__)), \
                 mock.patch.object(setup, "HOME", Path(temp)), \
                 mock.patch.object(setup, "save_preferences", return_value=setup.checked_preferences(options)) as save, \
                 mock.patch.object(setup.subprocess, "Popen") as spawn:
                spawn.return_value.wait.side_effect = setup.subprocess.TimeoutExpired("synthetic runtime", 1.5)
                handler.do_POST()
        self.assertEqual(responses[0][0], 202)
        save.assert_called_once_with(options)
        spawn.assert_called_once()

    def test_invalid_preferences_rejected_before_runtime_preflight(self):
        options = {"profile": "invalid", "scene": "coast", "motion": "reduced"}
        handler, responses = self.handler_for(options)
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(setup, "RUNTIME", Path(temp) / "missing_runtime.py"), \
                 mock.patch.object(setup, "save_preferences") as save:
                handler.do_POST()
        self.assertEqual(responses[0][0], 400)
        save.assert_not_called()


    def test_spawn_failure_does_not_mark_setup_complete_and_retry_succeeds(self):
        options = {"profile": "eco", "scene": "coast", "motion": "reduced"}
        with tempfile.TemporaryDirectory() as temp:
            prefs = Path(temp) / "selma0_setup_v1.json"
            real_save = setup.save_preferences
            with mock.patch.object(setup, "HOME", Path(temp)), \
                 mock.patch.object(setup, "PREFS", prefs), \
                 mock.patch.object(setup, "RUNTIME", Path(__file__)), \
                 mock.patch.object(setup, "save_preferences", side_effect=lambda value: real_save(value, prefs)), \
                 mock.patch.object(setup.subprocess, "Popen", side_effect=OSError("synthetic spawn failure")) as spawn:
                handler, responses = self.handler_for(options)
                handler.do_POST()
                self.assertEqual(responses[0][0], 503)
                self.assertIn("incomplete", responses[0][1]["error"])
                self.assertFalse(prefs.exists(), "failed spawn must not skip first-run on restart")
                spawn.assert_called_once()
            with mock.patch.object(setup, "HOME", Path(temp)), \
                 mock.patch.object(setup, "PREFS", prefs), \
                 mock.patch.object(setup, "RUNTIME", Path(__file__)), \
                 mock.patch.object(setup, "save_preferences", side_effect=lambda value: real_save(value, prefs)), \
                 mock.patch.object(setup.subprocess, "Popen") as spawn:
                handler, responses = self.handler_for(options)
                spawn.return_value.wait.side_effect = setup.subprocess.TimeoutExpired("synthetic runtime", 1.5)
                handler.do_POST()
                self.assertEqual(responses[0][0], 202)
                self.assertTrue(prefs.is_file())
                self.assertEqual(prefs.stat().st_mode & 0o777, 0o600)
                spawn.assert_called_once()

    def test_wait_observation_failure_preserves_spawn_guard(self):
        # A spawned child may still be running when waitpid fails. Do not
        # remove the first-run guard or allow a duplicate launch.
        options = {"profile": "eco", "scene": "coast", "motion": "reduced"}
        with tempfile.TemporaryDirectory() as temp:
            prefs = Path(temp) / "selma0_setup_v1.json"
            real_save = setup.save_preferences
            with mock.patch.object(setup, "HOME", Path(temp)), \
                 mock.patch.object(setup, "PREFS", prefs), \
                 mock.patch.object(setup, "RUNTIME", Path(__file__)), \
                 mock.patch.object(setup, "save_preferences", side_effect=lambda value: real_save(value, prefs)), \
                 mock.patch.object(setup.subprocess, "Popen") as spawn:
                spawn.return_value.wait.side_effect = OSError("synthetic waitpid failure")
                handler, responses = self.handler_for(options)
                handler.do_POST()
                self.assertEqual(responses[0][0], 202)
                self.assertIs(responses[0][1]["ready"], False)
                self.assertEqual(responses[0][1]["status"], "launch_pending")
                self.assertTrue(prefs.is_file())
                handler2, responses2 = self.handler_for(options)
                handler2.do_POST()
                self.assertEqual(responses2[0][0], 409)
                spawn.assert_called_once()

    def test_immediate_child_exit_does_not_mark_setup_complete(self):
        options = {"profile": "eco", "scene": "coast", "motion": "reduced"}
        with tempfile.TemporaryDirectory() as temp:
            prefs = Path(temp) / "selma0_setup_v1.json"
            real_save = setup.save_preferences
            with mock.patch.object(setup, "HOME", Path(temp)), \
                 mock.patch.object(setup, "PREFS", prefs), \
                 mock.patch.object(setup, "RUNTIME", Path(__file__)), \
                 mock.patch.object(setup, "save_preferences", side_effect=lambda value: real_save(value, prefs)), \
                 mock.patch.object(setup.subprocess, "Popen") as spawn:
                for exit_code in (0, 7):
                    with self.subTest(exit_code=exit_code):
                        spawn.return_value.wait.return_value = exit_code
                        handler, responses = self.handler_for(options)
                        handler.do_POST()
                        self.assertEqual(responses[0][0], 503)
                        self.assertIn("incomplete", responses[0][1]["error"])
                        self.assertFalse(prefs.exists(), "immediate exit must permit first-run retry")
                self.assertEqual(spawn.call_count, 2)

    def test_completed_setup_rejects_duplicate_launch(self):
        options = {"profile": "eco", "scene": "coast", "motion": "normal"}
        with tempfile.TemporaryDirectory() as temp:
            prefs = Path(temp) / "selma0_setup_v1.json"
            prefs.write_text('{"version":1}', encoding="utf-8")
            with mock.patch.object(setup, "PREFS", prefs), \
                 mock.patch.object(setup, "RUNTIME", Path(__file__)), \
                 mock.patch.object(setup, "save_preferences") as save, \
                 mock.patch.object(setup.subprocess, "Popen") as spawn:
                handler, responses = self.handler_for(options)
                handler.do_POST()
                self.assertEqual(responses[0][0], 409)
                save.assert_not_called()
                spawn.assert_not_called()
                self.assertEqual(prefs.read_text(encoding="utf-8"), '{"version":1}')




class TestStartupLogSafety(unittest.TestCase):
    """Offline filesystem checks; no Android device or live runtime."""

    def test_symlink_log_rejected_and_first_run_can_retry(self):
        opts = {"profile": "eco", "scene": "coast", "motion": "reduced"}
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            prefs = home / "selma0_setup_v1.json"
            victim = home / "unrelated.txt"
            victim.write_text("unchanged", encoding="utf-8")
            log = home / "selma0_startup_v1.log"
            try:
                log.symlink_to(victim)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable on this host")
            handler, replies = TestStartRecovery.handler_for(opts)
            real_save = setup.save_preferences
            with mock.patch.object(setup, "HOME", home), \
                 mock.patch.object(setup, "PREFS", prefs), \
                 mock.patch.object(setup, "RUNTIME", Path(__file__)), \
                 mock.patch.object(setup, "save_preferences",
                                   side_effect=lambda value: real_save(value, prefs)), \
                 mock.patch.object(setup.subprocess, "Popen") as spawn:
                handler.do_POST()
            self.assertEqual(replies[0][0], 503)
            self.assertIn("incomplete", replies[0][1]["error"])
            self.assertFalse(prefs.exists())
            self.assertEqual(victim.read_text(encoding="utf-8"), "unchanged")
            spawn.assert_not_called()

    def test_hardlinked_log_rejected_without_writing_target(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            victim = home / "unrelated.txt"
            victim.write_bytes(b"unchanged")
            try:
                setup.os.link(victim, home / "selma0_startup_v1.log")
            except (OSError, NotImplementedError):
                self.skipTest("hardlinks unavailable on this host")
            with self.assertRaises(OSError):
                setup.open_startup_log(home / "selma0_startup_v1.log")
            self.assertEqual(victim.read_bytes(), b"unchanged")

    def test_regular_log_appends_and_uses_private_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            log = Path(temp) / "selma0_startup_v1.log"
            log.write_bytes(b"old")
            log.chmod(0o644)
            with setup.open_startup_log(log) as stream:
                stream.write(b"new")
            self.assertEqual(log.read_bytes(), b"oldnew")
            self.assertEqual(log.stat().st_mode & 0o777, 0o600)


class TestLaunchObservation(unittest.TestCase):
    """Read-only, process-local launch observation; no real child or device."""

    def test_untracked_does_not_claim_readiness(self):
        with mock.patch.object(setup, "LAUNCHED_CHILD", None):
            self.assertEqual(setup.observed_launch_state(), "untracked")

    def test_running_child_is_pending_without_restarting(self):
        child = mock.Mock()
        child.poll.return_value = None
        with mock.patch.object(setup, "LAUNCHED_CHILD", child):
            self.assertEqual(setup.observed_launch_state(), "launch_pending")
        child.poll.assert_called_once_with()
        child.wait.assert_not_called()
        child.terminate.assert_not_called()

    def test_late_exit_preserves_preferences_and_does_not_restart(self):
        child = mock.Mock()
        child.poll.return_value = 7
        with tempfile.TemporaryDirectory() as temp:
            prefs = Path(temp) / "selma0_setup_v1.json"
            prefs.write_text("original", encoding="utf-8")
            with mock.patch.object(setup, "LAUNCHED_CHILD", child):
                self.assertEqual(setup.observed_launch_state(), "exited_after_launch")
            self.assertEqual(prefs.read_text(encoding="utf-8"), "original")
        child.wait.assert_not_called()
        child.terminate.assert_not_called()

    def test_poll_observation_failure_is_explicitly_unverified(self):
        child = mock.Mock()
        child.poll.side_effect = OSError("synthetic poll failure")
        with mock.patch.object(setup, "LAUNCHED_CHILD", child):
            self.assertEqual(setup.observed_launch_state(), "observation_unavailable")
        child.wait.assert_not_called()
        child.terminate.assert_not_called()

    def test_launch_status_route_reports_not_ready_without_launch(self):
        handler = object.__new__(setup.WizardHandler)
        handler.path = "/launch-status"
        handler.headers = {"Host": "127.0.0.1:8766"}
        responses = []
        handler.reply = lambda code, payload: responses.append((code, payload))
        child = mock.Mock()
        child.poll.return_value = 9
        with mock.patch.object(setup, "LAUNCHED_CHILD", child):
            handler.do_GET()
        self.assertEqual(responses, [(200, {"status": "exited_after_launch", "ready": False})])
        child.wait.assert_not_called()
        child.terminate.assert_not_called()



if __name__ == "__main__":
    unittest.main()
