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


if __name__ == "__main__":
    unittest.main()
