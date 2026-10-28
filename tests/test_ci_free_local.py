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
import zipfile
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

    def test_subprocess_uses_current_repository_root(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(ci, "ROOT", Path(temp)):
            ci.run([sys.executable, "-c", "from pathlib import Path; Path('cwd-proof').write_text('ok')"], timeout=3)
            self.assertEqual('ok', (Path(temp) / 'cwd-proof').read_text())

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
                self.assertTrue(run_mock.call_args_list[1].kwargs["cleanup_on_failure"])
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

    def android_fixture(self, root):
        project = root / "SELMA0_ANDROID_NATIVE_V1"
        wrapper = project / "gradle/wrapper/gradle-wrapper.jar"
        wrapper.parent.mkdir(parents=True)
        wrapper.write_bytes(b"test-only wrapper placeholder")
        apk = project / "app/build/outputs/apk/debug/app-debug.apk"
        apk.parent.mkdir(parents=True)
        return apk

    def test_android_build_hashes_fresh_package_and_sidecar(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            apk = self.android_fixture(root)
            apk.write_bytes(b"old stale artifact")
            def fake_gradle(*args, **kwargs):
                with zipfile.ZipFile(apk, "w") as archive:
                    for entry in ("AndroidManifest.xml", "resources.arsc", "classes.dex"):
                        archive.writestr(entry, b"synthetic fixture")
            with patch.object(ci, "ROOT", root), patch.object(
                ci.shutil, "which", return_value="java"
            ), patch.dict(ci.os.environ, {"ANDROID_HOME": str(root)}, clear=True), patch.object(
                ci, "run", side_effect=fake_gradle
            ) as run_mock:
                capture = io.StringIO()
                with contextlib.redirect_stdout(capture):
                    ci.build_android()
                run_mock.assert_called_once()
                self.assertEqual(ci.ANDROID_TIMEOUT_SECONDS, run_mock.call_args.kwargs["timeout"])
                digest = hashlib.sha256(apk.read_bytes()).hexdigest()
                self.assertIn(digest, capture.getvalue())
                self.assertEqual(
                    digest + "  app-debug.apk\n",
                    apk.with_suffix(".apk.sha256").read_text(encoding="ascii"),
                )

    def test_android_noop_cannot_reuse_old_apk(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            apk = self.android_fixture(root)
            apk.write_bytes(b"old stale apk")
            with patch.object(ci, "ROOT", root), patch.object(
                ci.shutil, "which", return_value="java"
            ), patch.dict(ci.os.environ, {"ANDROID_HOME": str(root)}, clear=True), patch.object(ci, "run"):
                with self.assertRaisesRegex(RuntimeError, "newly generated"):
                    ci.build_android()
            self.assertFalse(apk.exists())

    def test_android_rejects_zip_with_missing_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            apk = self.android_fixture(root)
            def fake_gradle(*args, **kwargs):
                with zipfile.ZipFile(apk, "w") as archive:
                    archive.writestr("readme", b"not an APK")
            with patch.object(ci, "ROOT", root), patch.object(
                ci.shutil, "which", return_value="java"
            ), patch.dict(ci.os.environ, {"ANDROID_HOME": str(root)}, clear=True), patch.object(
                ci, "run", side_effect=fake_gradle
            ):
                with self.assertRaisesRegex(RuntimeError, "package components"):
                    ci.build_android()

    def test_android_rejects_nonzip_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            apk = self.android_fixture(root)
            def fake_gradle(*args, **kwargs):
                apk.write_bytes(b"not a zip package")
            with patch.object(ci, "ROOT", root), patch.object(
                ci.shutil, "which", return_value="java"
            ), patch.dict(ci.os.environ, {"ANDROID_HOME": str(root)}, clear=True), patch.object(
                ci, "run", side_effect=fake_gradle
            ):
                with self.assertRaisesRegex(RuntimeError, "valid ZIP"):
                    ci.build_android()

    def test_revision_requires_git(self):
        with patch.object(ci.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "Git is required"):
                ci.revision()

    def test_revision_records_clean_checkout(self):
        def git_reply(*args):
            if "--show-toplevel" in args:
                return str(ci.ROOT)
            if "HEAD^{commit}" in args:
                return "a" * 40
            if "status" in args:
                return ""
            return "tracked"
        with patch.object(ci.shutil, "which", return_value="git"), patch.object(
            ci, "git_stdout", side_effect=git_reply
        ):
            self.assertEqual("a" * 40, ci.revision(expected_sha="a" * 40))

    def test_revision_rejects_parent_git_repository(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "nested"
            root.mkdir()
            with patch.object(ci, "ROOT", root), patch.object(
                ci.shutil, "which", return_value="git"
            ), patch.object(ci, "git_stdout", return_value=str(Path(temp))):
                with self.assertRaisesRegex(RuntimeError, "root of the intended"):
                    ci.revision()

    def test_revision_rejects_dirty_checkout(self):
        def git_reply(*args):
            if "--show-toplevel" in args:
                return str(ci.ROOT)
            if "HEAD^{commit}" in args:
                return "a" * 40
            if "status" in args:
                return "?? untracked_test.py"
            return "tracked"
        with patch.object(ci.shutil, "which", return_value="git"), patch.object(
            ci, "git_stdout", side_effect=git_reply
        ):
            with self.assertRaisesRegex(RuntimeError, "not clean"):
                ci.revision()

    def test_revision_rejects_unexpected_commit(self):
        def git_reply(*args):
            if "--show-toplevel" in args:
                return str(ci.ROOT)
            if "HEAD^{commit}" in args:
                return "a" * 40
            return "tracked"
        with patch.object(ci.shutil, "which", return_value="git"), patch.object(
            ci, "git_stdout", side_effect=git_reply
        ):
            with self.assertRaisesRegex(RuntimeError, "does not match"):
                ci.revision(expected_sha="b" * 40)

    def test_runner_cleans_nonzero_smoke_process_group_only_when_selected(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(ci, "ROOT", Path(temp)), patch.object(
            ci, "terminate_group"
        ) as cleanup:
            with self.assertRaises(subprocess.CalledProcessError):
                ci.run([sys.executable, "-c", "import sys; sys.exit(7)"],
                       timeout=3, cleanup_on_failure=True)
            cleanup.assert_called_once()


if __name__ == "__main__":
    unittest.main()
