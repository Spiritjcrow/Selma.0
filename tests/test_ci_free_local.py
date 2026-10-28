"""Offline, disposable regression tests for the no-payment PR #89 validator."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import ci_free_local as ci


class LocalCIFallbackTests(unittest.TestCase):
    def test_unique_json_is_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "good.json").write_text('{"outer":{"a":1,"b":2}}', encoding="utf-8")
            with patch.object(ci, "ROOT", root):
                ci.validate_json()

    def test_reject_duplicate_root_and_nested_json_keys(self):
        for payload in ('{"a":1,"a":2}', '{"deep":{"a":1,"a":2}}'):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "duplicate.json").write_text(payload, encoding="utf-8")
                with patch.object(ci, "ROOT", root):
                    with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                        ci.validate_json()

    def test_reject_non_json_nan_and_infinity(self):
        for literal in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(literal=literal), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "invalid.json").write_text('{"value":' + literal + '}', encoding="utf-8")
                with patch.object(ci, "ROOT", root):
                    with self.assertRaisesRegex(ValueError, "non-JSON"):
                        ci.validate_json()

    def test_reject_symlink_json(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "target.txt"
            target.write_text('{"key":"value"}', encoding="utf-8")
            symlink = root / "linked.json"
            try:
                symlink.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks not available for this operating system")
            with patch.object(ci, "ROOT", root):
                with self.assertRaisesRegex(ValueError, "symlink"):
                    ci.validate_json()

    def test_ignore_excluded_build_and_vendor_json(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "node_modules"
            folder.mkdir()
            (folder / "broken.json").write_text('{"a":', encoding="utf-8")
            (root / "valid.json").write_text("{}", encoding="utf-8")
            with patch.object(ci, "ROOT", root):
                ci.validate_json()

    def test_subprocess_is_bounded_and_does_not_use_shell(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(ci, "ROOT", Path(temp)):
            with self.assertRaises(subprocess.TimeoutExpired):
                ci.run([sys.executable, "-c", "import time; time.sleep(10)"], timeout=0.1)

    def test_nonzero_child_process_stops_validation(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(ci, "ROOT", Path(temp)):
            with self.assertRaises(subprocess.CalledProcessError):
                ci.run([sys.executable, "-c", "import sys; sys.exit(7)"], timeout=3)

    def test_windows_bash_detection_rejects_wsl_system_bash(self):
        with patch.object(
            ci.shutil, "which", side_effect=lambda name: {
                "git": "/fake/Git/cmd/git.exe",
                "bash": "/Windows/System32/bash.exe",
            }.get(name)
        ), patch.object(Path, "is_file", return_value=False):
            self.assertIsNone(ci.find_bash(windows=True))

    def test_missing_bash_has_honest_partial_result(self):
        with patch.object(ci, "find_bash", return_value=None):
            self.assertFalse(ci.validate_shell())

    def test_shell_syntax_and_smoke_are_invoked_with_timeouts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "one.sh").write_text("true\n", encoding="utf-8")
            with patch.object(ci, "ROOT", root), patch.object(
                ci, "find_bash", return_value="/fake/bash"
            ), patch.object(ci, "run") as run_mock:
                self.assertTrue(ci.validate_shell())
                self.assertEqual(2, run_mock.call_count)
                self.assertEqual(60, run_mock.call_args_list[0].kwargs["timeout"])
                self.assertEqual(ci.SMOKE_TIMEOUT_SECONDS, run_mock.call_args_list[1].kwargs["timeout"])
                env = run_mock.call_args_list[1].kwargs["env"]
                self.assertIn("SELMA0_SMOKE_PORT_V1", env)
                self.assertTrue(1 <= int(env["SELMA0_SMOKE_PORT_V1"]) <= 65535)

    def test_android_requires_actual_sdk(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "SELMA0_ANDROID_NATIVE_V1").mkdir()
            with patch.object(ci, "ROOT", root), patch.object(
                ci.shutil, "which", return_value="java"
            ), patch.dict(ci.os.environ, {"ANDROID_HOME": str(root / "missing")}, clear=True):
                with self.assertRaisesRegex(RuntimeError, "Android SDK"):
                    ci.build_android()

    def test_android_build_hashes_fixture_without_loading_whole_apk(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "SELMA0_ANDROID_NATIVE_V1"
            wrapper = project / "gradle/wrapper/gradle-wrapper.jar"
            wrapper.parent.mkdir(parents=True)
            wrapper.write_bytes(b"fixture")
            apk = project / "app/build/outputs/apk/debug/app-debug.apk"
            apk.parent.mkdir(parents=True)
            apk.write_bytes(b"synthetic APK fixture, not installable")
            with patch.object(ci, "ROOT", root), patch.object(
                ci.shutil, "which", return_value="java"
            ), patch.dict(ci.os.environ, {"ANDROID_HOME": str(root)}, clear=True), patch.object(
                ci, "run"
            ) as run_mock:
                capture = io.StringIO()
                with contextlib.redirect_stdout(capture):
                    ci.build_android()
                run_mock.assert_called_once()
                self.assertEqual(ci.ANDROID_TIMEOUT_SECONDS, run_mock.call_args.kwargs["timeout"])
                self.assertIn(hashlib.sha256(apk.read_bytes()).hexdigest(), capture.getvalue())

    def test_revision_requires_git(self):
        with patch.object(ci.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "Git is required"):
                ci.revision()

    def test_revision_records_clean_checkout(self):
        def fake_run(command, **kwargs):
            output = "a" * 40 + "\n" if "rev-parse" in command else ""
            return subprocess.CompletedProcess(command, 0, stdout=output)

        with patch.object(ci.shutil, "which", return_value="git"), patch.object(
            ci.subprocess, "run", side_effect=fake_run
        ):
            self.assertEqual("a" * 40, ci.revision())


if __name__ == "__main__":
    unittest.main()
