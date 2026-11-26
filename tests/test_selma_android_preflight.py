"""Synthetic fixtures for read-only native Android build preflight."""
import sys
from pathlib import Path
import tempfile
import unittest

from tools import selma_android_preflight as pre


class PreflightTests(unittest.TestCase):
    def fixture(self, root: Path):
        project = root / 'SELMA0_ANDROID_NATIVE_V1'
        wrapper = project / 'gradle' / 'wrapper'
        wrapper.mkdir(parents=True)
        (wrapper / 'gradle-wrapper.jar').write_bytes(b'test fixture')
        (wrapper / 'gradle-wrapper.properties').write_text(
            'distributionUrl=https\\://services.gradle.org/distributions/gradle-8.9-bin.zip\n'
            'distributionSha256Sum=' + 'a'*64 + '\n'
        )
        (project / 'gradlew').write_text('test launcher')
        (project / 'gradlew.bat').write_text('test launcher')
        sdk = root / 'sdk'
        platform = sdk / 'platforms' / 'android-35'
        platform.mkdir(parents=True)
        (platform / 'android.jar').write_bytes(b'synthetic jar')
        tools = sdk / 'build-tools' / '35.0.0'
        tools.mkdir(parents=True)
        (tools / 'aapt2').write_bytes(b'test')
        (tools / 'aapt2.exe').write_bytes(b'test')
        return project, sdk

    def test_java_major(self):
        self.assertEqual(17, pre.java_major('openjdk version "17.0.12" 2024-07-16'))
        self.assertEqual(21, pre.java_major('java version "21"'))
        self.assertEqual(8, pre.java_major('java version "1.8.0_412"'))
        self.assertIsNone(pre.java_major('no readable version'))

    def test_valid_toolchain_unix_and_windows(self):
        with tempfile.TemporaryDirectory() as temp:
            project, sdk = self.fixture(Path(temp))
            self.assertEqual([], pre.check(project, sdk, 'openjdk version "17.0.5"'))
            self.assertEqual([], pre.check(project, sdk, 'java version "21.0.1"', windows=True))

    def test_old_jdk_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            project, sdk = self.fixture(Path(temp))
            self.assertIn('too old', str(pre.check(project, sdk, 'java version "1.8.0_123"')))

    def test_missing_sdk_and_wrapper_are_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            project, sdk = self.fixture(Path(temp))
            (project / 'gradle' / 'wrapper' / 'gradle-wrapper.jar').unlink()
            failures = pre.check(project, Path(temp) / 'nonexistent', None)
            self.assertIn('Android SDK missing', str(failures))
            self.assertIn('gradle-wrapper.jar', str(failures))
            self.assertIn('Java executable', str(failures))

    def test_missing_platform_and_build_tools_are_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            project, sdk = self.fixture(Path(temp))
            (sdk / 'platforms' / 'android-35' / 'android.jar').unlink()
            (sdk / 'build-tools' / '35.0.0' / 'aapt2').unlink()
            failures = pre.check(project, sdk, 'openjdk version "17"')
            self.assertIn('platform 35', str(failures))
            self.assertIn('build-tools 35.0.0', str(failures))

    def test_missing_wrapper_checksum_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            project, sdk = self.fixture(Path(temp))
            (project / 'gradle' / 'wrapper' / 'gradle-wrapper.properties').write_text(
                'distributionUrl=https\\://services.gradle.org/distributions/gradle-8.9-bin.zip\n'
            )
            self.assertIn('SHA-256', str(pre.check(project, sdk, 'openjdk version "17.0.1"')))


if __name__ == '__main__':
    unittest.main()
