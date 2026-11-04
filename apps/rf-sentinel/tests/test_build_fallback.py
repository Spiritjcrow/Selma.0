import os
import pathlib
import stat
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/build-android-local.sh"


class BuildFallbackContracts(unittest.TestCase):
    def run_with_versions(self, java_version, gradle_version):
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            tools = base / "bin"
            tools.mkdir()
            sdk_jar = base / "sdk/platforms/android-35/android.jar"
            sdk_jar.parent.mkdir(parents=True)
            sdk_jar.touch()

            java = tools / "java"
            java.write_text(
                "#!/bin/sh\n"
                f"echo '    java.specification.version = {java_version}' >&2\n"
            )
            gradle = tools / "gradle"
            gradle.write_text(
                "#!/bin/sh\n"
                "if [ \"${1:-}\" = \"--version\" ]; then\n"
                f"  echo 'Gradle {gradle_version}'\n"
                "  exit 0\n"
                "fi\n"
                "exit 99\n"
            )
            for executable in (java, gradle):
                executable.chmod(executable.stat().st_mode | stat.S_IXUSR)

            environment = os.environ.copy()
            environment["PATH"] = str(tools) + os.pathsep + environment["PATH"]
            environment["ANDROID_SDK_ROOT"] = str(base / "sdk")
            return subprocess.run(
                ["/bin/bash", str(SCRIPT)],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
            )

    def test_wrong_java_version_is_blocked(self):
        result = self.run_with_versions("21", "8.9")
        self.assertEqual(75, result.returncode)
        self.assertIn("BLOCKED: JDK 17 required; found 21", result.stderr)

    def test_wrong_gradle_version_is_blocked(self):
        result = self.run_with_versions("17", "8.8")
        self.assertEqual(75, result.returncode)
        self.assertIn("BLOCKED: Gradle 8.9 required; found 8.8", result.stderr)

    def run_with_build_tools(self, *present_tools):
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            tools = base / "bin"
            tools.mkdir()
            sdk_jar = base / "sdk/platforms/android-35/android.jar"
            sdk_jar.parent.mkdir(parents=True)
            sdk_jar.touch()
            build_tools = base / "sdk/build-tools/35.0.0"
            build_tools.mkdir(parents=True)
            for name in present_tools:
                (build_tools / name).touch()

            programs = {
                "java": (
                    "#!/bin/sh\n"
                    "echo '    java.specification.version = 17' >&2\n"
                ),
                "gradle": (
                    "#!/bin/sh\n"
                    "if [ \"${1:-}\" = \"--version\" ]; then echo 'Gradle 8.9'; exit 0; fi\n"
                    "exit 99\n"
                ),
                "python3": "#!/bin/sh\nexit 99\n",
            }
            for name, source in programs.items():
                executable = tools / name
                executable.write_text(source)
                executable.chmod(executable.stat().st_mode | stat.S_IXUSR)

            environment = os.environ.copy()
            environment["PATH"] = str(tools) + os.pathsep + environment["PATH"]
            environment["ANDROID_SDK_ROOT"] = str(base / "sdk")
            return subprocess.run(
                ["/bin/bash", str(SCRIPT)],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
            )

    def test_missing_aapt2_is_blocked_before_build(self):
        result = self.run_with_build_tools("apksigner")
        self.assertEqual(75, result.returncode)
        self.assertIn("BLOCKED: Android build-tools 35.0.0 missing aapt2", result.stderr)

    def test_missing_apksigner_is_blocked_before_build(self):
        result = self.run_with_build_tools("aapt2")
        self.assertEqual(75, result.returncode)
        self.assertIn("BLOCKED: Android build-tools 35.0.0 missing apksigner", result.stderr)

    def test_android_gates_run_before_apk_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            tools = base / "bin"
            tools.mkdir()
            sdk_jar = base / "sdk/platforms/android-35/android.jar"
            sdk_jar.parent.mkdir(parents=True)
            sdk_jar.touch()
            build_tools = base / "sdk/build-tools/35.0.0"
            build_tools.mkdir(parents=True)
            (build_tools / "aapt2").touch()
            (build_tools / "apksigner").touch()
            call_log = base / "calls.log"

            programs = {
                "java": (
                    "#!/bin/sh\n"
                    "echo '    java.specification.version = 17' >&2\n"
                ),
                "gradle": (
                    "#!/bin/sh\n"
                    "if [ \"${1:-}\" = \"--version\" ]; then echo 'Gradle 8.9'; exit 0; fi\n"
                    "echo \"gradle:$*\" >> \"$CALL_LOG\"\n"
                ),
                "python3": (
                    "#!/bin/sh\n"
                    "echo \"python:$*\" >> \"$CALL_LOG\"\n"
                    "if [ \"${1:-}\" = \"tools/verify_apk.py\" ]; then\n"
                    "  if [ \"${VERIFY_FAIL:-0}\" = \"1\" ]; then echo '{\"partial\":true}'; exit 1; fi\n"
                    "  echo '{}'\n"
                    "fi\n"
                ),
            }
            for name, source in programs.items():
                executable = tools / name
                executable.write_text(source)
                executable.chmod(executable.stat().st_mode | stat.S_IXUSR)

            environment = os.environ.copy()
            environment["PATH"] = str(tools) + os.pathsep + environment["PATH"]
            environment["ANDROID_SDK_ROOT"] = str(base / "sdk")
            environment["CALL_LOG"] = str(call_log)
            evidence = base / "apk-evidence.json"
            environment["RF_SENTINEL_EVIDENCE_PATH"] = str(evidence)
            result = subprocess.run(
                ["/bin/bash", str(SCRIPT)],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            calls = call_log.read_text().splitlines()
            self.assertEqual(
                [
                    "python:-m unittest discover -s tests -v",
                    "gradle:--offline --no-daemon :app:lintDebug :app:testDebugUnitTest :app:assembleDebug",
                    "python:tools/verify_apk.py app/build/outputs/apk/debug/app-debug.apk",
                ],
                calls,
            )
            self.assertEqual("{}", evidence.read_text().strip())

            environment["VERIFY_FAIL"] = "1"
            failed = subprocess.run(
                ["/bin/bash", str(SCRIPT)],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
            )
            self.assertNotEqual(0, failed.returncode)
            self.assertEqual("{}", evidence.read_text().strip())


if __name__ == "__main__":
    unittest.main()
