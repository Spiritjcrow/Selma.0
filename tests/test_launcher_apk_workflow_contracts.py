"""Contracts for portable Selma Android APK delivery evidence."""

from pathlib import Path
import unittest


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "selma-android-build.yml"
)


class LauncherApkWorkflowContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_checksum_is_portable_after_artifact_download(self):
        self.assertIn(
            "working-directory: SELMA0_ANDROID_NATIVE_V1/app/build/outputs/apk/debug",
            self.workflow,
        )
        self.assertIn(
            "sha256sum app-debug.apk > app-debug.apk.sha256",
            self.workflow,
        )
        self.assertNotIn(
            "sha256sum SELMA0_ANDROID_NATIVE_V1/app/build/outputs/apk/debug/app-debug.apk >",
            self.workflow,
        )


if __name__ == "__main__":
    unittest.main()
