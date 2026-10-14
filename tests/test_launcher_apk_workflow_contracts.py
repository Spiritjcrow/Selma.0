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

    def test_checksum_is_verified_before_artifact_upload(self):
        checksum = "sha256sum app-debug.apk > app-debug.apk.sha256"
        verify = "sha256sum --check app-debug.apk.sha256"
        upload = "- name: Upload Selma APK"
        self.assertIn(verify, self.workflow)
        self.assertLess(self.workflow.index(checksum), self.workflow.index(verify))
        self.assertLess(self.workflow.index(verify), self.workflow.index(upload))

    def test_compiled_icon_checks_use_exact_package_qualified_names(self):
        self.assertIn(
            "grep -Fq 'ai.selma.companion:drawable/ic_selma:'",
            self.workflow,
        )
        self.assertIn(
            "grep -Fq 'ai.selma.companion:drawable/ic_selma_home:'",
            self.workflow,
        )
        self.assertNotIn("grep -Fq 'drawable/ic_selma'", self.workflow)

    def test_apk_badging_requires_package_and_target_sdk_35(self):
        badging = '"$AAPT2" dump badging "$APK" > "$RUNNER_TEMP/selma-apk-badging.txt"'
        package = (
            "grep -Fq \"package: name='ai.selma.companion'\" "
            '"$RUNNER_TEMP/selma-apk-badging.txt"'
        )
        target = (
            "grep -Fq \"targetSdkVersion:'35'\" "
            '"$RUNNER_TEMP/selma-apk-badging.txt"'
        )
        self.assertIn(badging, self.workflow)
        self.assertIn(package, self.workflow)
        self.assertIn(target, self.workflow)

    def test_compiled_manifest_requires_selma_home_activity(self):
        manifest = (
            '"$AAPT2" dump xmltree "$APK" --file AndroidManifest.xml '
            '> "$RUNNER_TEMP/selma-apk-manifest.txt"'
        )
        activity = (
            "grep -Fq 'ai.selma.companion.LauncherActivity' "
            '"$RUNNER_TEMP/selma-apk-manifest.txt"'
        )
        home = (
            "grep -Fq 'android.intent.category.HOME' "
            '"$RUNNER_TEMP/selma-apk-manifest.txt"'
        )
        self.assertIn(manifest, self.workflow)
        self.assertIn(activity, self.workflow)
        self.assertIn(home, self.workflow)

    def test_compiled_apk_permissions_remain_least_privilege(self):
        permissions = (
            '"$AAPT2" dump permissions "$APK" '
            '> "$RUNNER_TEMP/selma-apk-permissions.txt"'
        )
        count = (
            'test "$(grep -Fc \'uses-permission:\' '
            '"$RUNNER_TEMP/selma-apk-permissions.txt")" -eq 1'
        )
        internet = (
            "grep -Fq \"uses-permission: name='android.permission.INTERNET'\" "
            '"$RUNNER_TEMP/selma-apk-permissions.txt"'
        )
        self.assertIn(permissions, self.workflow)
        self.assertIn(count, self.workflow)
        self.assertIn(internet, self.workflow)

    def test_apk_signature_is_verified_before_checksum_and_upload(self):
        verifier = 'APKSIGNER="${ANDROID_HOME}/build-tools/35.0.0/apksigner"'
        verify = '"$APKSIGNER" verify --verbose "$APK"'
        checksum = "sha256sum app-debug.apk > app-debug.apk.sha256"
        upload = "- name: Upload Selma APK"
        self.assertIn(verifier, self.workflow)
        self.assertIn(verify, self.workflow)
        self.assertLess(self.workflow.index(verify), self.workflow.index(checksum))
        self.assertLess(self.workflow.index(verify), self.workflow.index(upload))


if __name__ == "__main__":
    unittest.main()
