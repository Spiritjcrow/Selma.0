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



if __name__ == "__main__":
    unittest.main()
